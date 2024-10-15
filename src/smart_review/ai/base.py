import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple

from attrs import define, field
from github.PullRequestReview import PullRequestReview

from smart_review.exceptions import SmartReviewGithubException
from smart_review.gitops.github import GitHubClient
from smart_review.ai.objects import NegativeReview, ResponseTypeEnum

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
Review the following pull request diffs and provide feedback. Focus on code quality, potential bugs, and adherence to best practices.
If the changes fail to meet any standards, provide a detailed explanation and suggest improvements.

# Pull Request Diffs:
{diff}

# Context:
{context}

# Code Quality Checklist:
1. Is the code readable and maintainable?
2. Are there any potential bugs or logical errors?
3. Does the code follow the languages coding standards and best practices?
4. Are there any performance issues or inefficiencies?
5. Is there sufficient documentation and comments?

# Additional Information:
- Project Description: {project_description}
- Relevant Files: {relevant_files}

# Response Format
Based on the above template your response should be one of three JSON objects:

1. Positive Review:
{{
    "message": "The code changes look good.",  # Or any other positive message
    "review_type": "positive_review"
}}

2. Negative Review:
{{
    "message": "The code changes need improvement.",  # Or any other negative message
    "review_type": "negative_review",
    "reviews": [
        {{
            "file": "path/to/file.py",
            "comments": [
                {{
                    "line": 10,
                    "message": "This line of code is not clear." # Or a more detailed message
                }}
            ]
        }}
    ]
}}

3. Additional Files:
{{
    "message": "Please provide the following files to help with the review.",
    "review_type": "additional_files",
    "additional_files": ["path/to/file.py"]
}}

If your response is for additional files, they will be retrieved from the repository and the review will be repeated.
There is a recursive limit to prevent infinite loops.

RECURSIONS REMAINING: {recursion_limit}

When the recursion's remaining value is 0, the review will no longer request additional files, so you might as well
return a positive or negative review.
"""


@define
class BaseLLMClient(ABC):
    """Base class to interact with an LLM client."""

    github_client: GitHubClient = field(init=True, repr=False)
    prompt_template: str = field(default=PROMPT_TEMPLATE, repr=False)

    @abstractmethod
    def _talk_to_llm(self, prompt: str) -> dict[str, Any]:
        """Talk to the LLM and get a response."""
        pass

    def _generate_prompt(
        self,
        diff_text: str,
        context: str,
        project_description: str,
        relevant_files: str,
        recursion_limit: int,
    ) -> str:
        """Generate a prompt for the LLM."""
        logger.debug("Reviewing a pull request.")

        # Print the template and values
        logger.debug("Prompt template: %s", repr(PROMPT_TEMPLATE))
        logger.debug(
            "Variables: diff=%s, context=%s, project_description=%s, relevant_files=%s, recursion_limit=%d",
            repr(diff_text),
            repr(context),
            repr(project_description),
            repr(relevant_files),
            recursion_limit,
        )

        # Format the template with the provided values
        prompt = PROMPT_TEMPLATE.format(
            diff=diff_text,
            context=context,
            project_description=project_description,
            relevant_files=relevant_files,
            recursion_limit=recursion_limit,
        )

        # Print the formatted prompt
        logger.debug("Generated prompt: %s", prompt)

        return prompt

    def review_pr(
        self,
        diff_text: str,
        context: str,
        project_description: str,
        relevant_files: str,
        recursion_limit: int = 5,
    ) -> Tuple[ResponseTypeEnum, PullRequestReview]:
        """Review a pull request and provide feedback."""
        logger.debug("Reviewing a pull request.")
        prompt = self._generate_prompt(
            diff_text, context, project_description, relevant_files, recursion_limit
        )
        logger.debug("Sending prompt to LLM.")
        start_time = time.time()
        response = self._talk_to_llm(prompt)
        logger.debug(f"Got response from LLM in {time.time() - start_time} seconds.")

        # figure out the type of response
        review_type = response.get("review_type")
        if review_type == ResponseTypeEnum.POSITIVE_REVIEW.value:
            assert "message" in response
            return (
                ResponseTypeEnum.POSITIVE_REVIEW,
                self.github_client.create_positive_review(response["message"]),
            )
        elif review_type == ResponseTypeEnum.NEGATIVE_REVIEW.value:
            assert "message" in response
            assert "reviews" in response
            reviews = response["reviews"]
            review = NegativeReview(review_message=response["message"], reviews=reviews)
            return (
                ResponseTypeEnum.NEGATIVE_REVIEW,
                self.github_client.create_negative_review(review),
            )
        elif review_type == ResponseTypeEnum.ADDITIONAL_FILES:
            assert "message" in response
            assert "additional_files" in response
            additional_file_paths = response["additional_files"]
            repository_files = self.github_client.repository_files
            files = []
            for path in additional_file_paths:
                if path not in repository_files:
                    logger.error(f"File {path} not found.")
                else:
                    files.append(repository_files[path])
            # lets create a nice string of the content of the files and their name with newlines
            additional_files = self.files_to_string({f.path: f.content for f in files})

            return self.review_pr(
                diff_text=diff_text,
                context=context,
                project_description=project_description,
                relevant_files=additional_files,
                recursion_limit=recursion_limit - 1,
            )
        else:
            logger.error("Unexpected review type from LLM: %s", review_type)
            raise SmartReviewGithubException(exception_message="Unexpected review type from LLM.")

    @classmethod
    def files_to_string(cls, files: Dict[str, str]) -> str:
        """Convert a dictionary of files to a string."""
        return "\n".join([f"{path}\n{content}" for path, content in files.items()])
