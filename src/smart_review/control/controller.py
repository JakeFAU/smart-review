import logging
from enum import Enum, auto
from typing import Optional

from attrs import define, field, validators
from google.auth.credentials import Credentials

from smart_review.ai.base import BaseLLMClient, ResponseTypeEnum
from smart_review.ai.openai import OpenAILLMClient
from smart_review.exceptions import SmartReviewLLMException, SmartReviewSystemException
from smart_review.gitops.github import GitHubClient

logger = logging.getLogger(__name__)


class LLMType(Enum):
    """Type of LLM."""

    OPENAI = auto()
    GOOGLE = auto()


@define
class AuthenticationInformation:
    """Information required for authentication."""

    github_token: str = field(init=True, repr=False, validator=validators.instance_of(str))
    openai_key: Optional[str] = field(
        default=None,
        init=True,
        repr=False,
        validator=validators.optional(validators.instance_of(str)),
    )
    credentials: Optional[Credentials] = field(
        default=None,
        init=True,
        repr=False,
    )

    _llm_type: LLMType = field(init=False, repr=True, validator=validators.instance_of(LLMType))

    def __attrs_post_init__(self) -> None:
        if self.openai_key is None and self.credentials is None:
            raise SmartReviewSystemException(
                exception_message="Either OpenAI key or Google credentials must be provided."
            )
        if self.openai_key is not None and self.credentials is not None:
            raise SmartReviewSystemException(
                exception_message="Only one of OpenAI key or Google credentials must be provided."
            )
        if self.openai_key is not None:
            self._llm_type = LLMType.OPENAI
        else:
            self._llm_type = LLMType.GOOGLE


@define
class Options:
    pr_number: int = field(init=True, repr=True, validator=validators.instance_of(int))
    github_owner: str = field(init=True, repr=True, validator=validators.instance_of(str))
    github_repo: str = field(init=True, repr=True, validator=validators.instance_of(str))
    max_tokens: Optional[int] = field(
        default=None,
        init=True,
        repr=True,
        validator=validators.optional(validators.ge(1)),
    )
    temperature: Optional[float] = field(
        default=None,
        init=True,
        repr=True,
        validator=validators.optional(validators.and_(validators.ge(0.0), validators.le(1.0))),
    )
    top_p: Optional[float] = field(
        default=None,
        init=True,
        repr=True,
        validator=validators.optional(validators.and_(validators.ge(0.0), validators.le(1.0))),
    )
    top_k: Optional[int] = field(
        default=None,
        init=True,
        repr=True,
        validator=validators.optional(validators.ge(1)),
    )
    frequency_penalty: Optional[float] = field(
        default=None,
        init=True,
        repr=True,
        validator=validators.optional(validators.and_(validators.ge(0.0), validators.le(1.0))),
    )
    presence_penalty: Optional[float] = field(
        default=None,
        init=True,
        repr=True,
        validator=validators.optional(validators.and_(validators.ge(0.0), validators.le(1.0))),
    )
    prompt_template: Optional[str] = field(
        default=None,
        init=True,
        repr=True,
        validator=validators.optional(validators.instance_of(str)),
    )
    max_recursion: int = field(
        init=True,
        repr=True,
        validator=validators.ge(0),
        default=5,
    )


@define(kw_only=True)
class Controller:
    """Controller class to interact with the LLM and GitHub."""

    llm_client: Optional[BaseLLMClient] = field(default=None, init=False, repr=False)
    github_client: Optional[GitHubClient] = field(default=None, init=False, repr=False)
    options: Options = field(init=True, repr=False)
    auth_info: AuthenticationInformation = field(init=True, repr=False)

    def __attrs_post_init__(self) -> None:
        # set up the github client, we always need this
        logger.debug("Setting up GitHub client.")
        self.github_client = GitHubClient(
            api_key=self.auth_info.github_token,
            owner=self.options.github_owner,
            repo=self.options.github_repo,
            pr_number=self.options.pr_number,
        )
        # now we can setup the LLM client
        assert self.github_client is not None
        logger.debug("Setting up LLM client.")
        if self.auth_info._llm_type == LLMType.OPENAI:
            assert self.auth_info.openai_key is not None
            self.llm_client = OpenAILLMClient(
                github_client=self.github_client,
                openai_api_key=self.auth_info.openai_key,
            )
        else:
            raise NotImplementedError("Google LLM client is not implemented yet.")

    def perform_review(self) -> None:
        """Perform the review."""
        logger.debug("Performing the review.")
        assert self.llm_client is not None
        assert self.github_client is not None
        diff_text = self.github_client.diff_text
        context = self.github_client.context
        project_description = self.github_client.repository.description
        relevant_files = ""
        recursion_limit = self.options.max_recursion
        # Make sure blank strings dont show up as None
        if not diff_text:
            diff_text = ""
        if not context:
            context = ""
        if not project_description:
            project_description = ""
        if not relevant_files:
            relevant_files = ""
        if not recursion_limit:
            recursion_limit = 5
        type, response = self.llm_client.review_pr(
            diff_text=diff_text,
            context=context,
            project_description=project_description,
            relevant_files=relevant_files,
            recursion_limit=recursion_limit,
        )
        if type == ResponseTypeEnum.POSITIVE_REVIEW:
            logger.info("Positive review created.")
            logger.debug(f"Positive review: {response}")
        elif type == ResponseTypeEnum.NEGATIVE_REVIEW:
            logger.info("Negative review created.")
            logger.debug(f"Negative review: {response}")
        else:
            raise SmartReviewLLMException(exception_message="Unknown response type from LLM.")


if __name__ == "__main__":
    # load environment variables
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Setup logging
    logging.basicConfig(level=logging.DEBUG)

    # Set up the authentication information
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    github_owner: str = os.getenv("GITHUB_OWNER", "")
    github_repo: str = os.getenv("GITHUB_REPO", "")

    auth_info = AuthenticationInformation(
        github_token=github_token,
        openai_key=openai_api_key,
    )
    options = Options(
        pr_number=1,
        github_owner=github_owner,
        github_repo=github_repo,
    )

    # Create the controller
    controller = Controller(options=options, auth_info=auth_info)

    # Perform the review
    controller.perform_review()
