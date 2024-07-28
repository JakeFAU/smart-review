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

    _llm_client: BaseLLMClient = field(
        init=False, repr=False, validator=validators.instance_of(BaseLLMClient)
    )
    _github_client: GitHubClient = field(
        init=False, repr=False, validator=validators.instance_of(GitHubClient)
    )
    _options: Options = field(init=True, repr=False, validator=validators.instance_of(Options))

    _auth_info: AuthenticationInformation = field(
        init=True,
        repr=False,
        validator=validators.instance_of(AuthenticationInformation),
    )

    @classmethod
    def create_controller(
        cls, auth_info: AuthenticationInformation, options: Options
    ) -> "Controller":
        """Create a controller."""
        return Controller(_auth_info=auth_info, _options=options)  # type: ignore[call-arg]

    def __attrs_post_init__(self) -> None:
        # set up the github client, we always need this
        logger.debug("Setting up GitHub client.")
        self._github_client = GitHubClient(
            api_key=self._auth_info.github_token,
            owner=self._options.github_owner,
            repo=self._options.github_repo,
            pr_number=self._options.pr_number,
        )
        # now we can setup the LLM client
        logger.debug("Setting up LLM client.")
        if self._auth_info._llm_type == LLMType.OPENAI:
            assert self._auth_info.openai_key is not None
            self._llm_client = OpenAILLMClient(
                github_client=self._github_client,
                openai_api_key=self._auth_info.openai_key,
            )
        else:
            raise NotImplementedError("Google LLM client is not implemented yet.")

    def perform_review(self) -> None:
        """Perform the review."""
        logger.debug("Performing the review.")
        type, response = self._llm_client.review_pr(
            diff_text=self._github_client.diff_text,
            context=self._github_client.context,
            project_description=self._github_client.repository.description,
            relevant_files="",  # we don't have any relevant files yet
            recursion_limit=self._options.max_recursion,
        )
        if type == ResponseTypeEnum.POSITIVE_REVIEW:
            logger.info("Positive review created.")
        elif type == ResponseTypeEnum.NEGATIVE_REVIEW:
            logger.info("Negative review created.")
        else:
            raise SmartReviewLLMException(exception_message="Unknown response type from LLM.")
