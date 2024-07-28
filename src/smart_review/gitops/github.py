import json
import logging
from typing import Dict, List

import github
import requests  # type: ignore[import-untyped]
from attrs import define, field, validators
from github.Branch import Branch
from github.Commit import Commit
from github.ContentFile import ContentFile
from github.File import File
from github.PullRequest import PullRequest
from github.PullRequestComment import PullRequestComment
from github.PullRequestReview import PullRequestReview
from github.Repository import Repository

from smart_review.exceptions import SmartReviewGithubException

logger = logging.getLogger(__name__)


@define
class NegativeInformation:
    """Information for a negative review."""

    body: str = field(init=True, repr=True, validator=validators.instance_of(str))
    commit: Commit = field(init=True, repr=False, validator=validators.instance_of(Commit))
    line_no: int = field(init=True, repr=False, validator=validators.instance_of(int))
    path: str = field(init=True, repr=False, validator=validators.instance_of(str))


@define
class GitHubClient:
    """
    GitHubClient is a class that is used to communicate with the GitHub API.
    """

    # these must be passed in
    api_key: str = field(init=True, repr=False, validator=validators.instance_of(str))
    repo: str = field(init=True, repr=False, validator=validators.instance_of(str))
    owner: str = field(init=True, repr=False, validator=validators.instance_of(str))
    pr_number: int = field(
        init=True,
        repr=False,
        validator=validators.and_(validators.instance_of(int), validators.ge(1)),
    )

    # these are "private" and will be lazy loaded
    _client: github.Github = field(init=False, repr=False)
    _repository: Repository = field(init=False, repr=False)
    _pull_request: PullRequest = field(init=False, repr=False)
    _destination_branch: Branch = field(init=False, repr=False)
    _source_branch: Branch = field(init=False, repr=False)
    _diff_text: str = field(init=False, repr=False)
    _pr_files: Dict[str, File] = field(init=False, repr=False)
    _repository_files: Dict[str, ContentFile] = field(init=False, repr=False)
    _pr_commits: List[Commit] = field(init=False, repr=False)
    _context: str = field(init=False, repr=False)

    def __attrs_post_init__(self):
        logger.debug("Creating GitHub client.")
        self._client = github.Github(self.api_key)

    def _get_repository(self) -> Repository:
        logger.debug(f"Getting repository {self.owner}/{self.repo}")
        return self._client.get_repo(f"{self.owner}/{self.repo}")

    @property
    def repository(self) -> Repository:
        if not self._repository:
            self._repository = self._get_repository()
        return self._repository

    def _get_pull_request(self) -> PullRequest:
        logger.debug(f"Getting pull request {self.pr_number}")
        return self._get_repository().get_pull(self.pr_number)

    @property
    def pull_request(self) -> PullRequest:
        if not self._pull_request:
            self._pull_request = self._get_pull_request()
        return self._pull_request

    def _get_destination_branch(self) -> Branch:
        logger.debug(f"Getting destination branch for PR {self.pr_number}")
        branch_ref = self.pull_request.base.ref
        return self.repository.get_branch(branch_ref)

    @property
    def destination_branch(self) -> Branch:
        if not self._destination_branch:
            self._destination_branch = self._get_destination_branch()
        return self._destination_branch

    def _get_source_branch(self) -> Branch:
        logger.debug(f"Getting source branch for PR {self.pr_number}")
        branch_ref = self.pull_request.head.ref
        return self.repository.get_branch(branch_ref)

    @property
    def source_branch(self) -> Branch:
        if not self._source_branch:
            self._source_branch = self._get_source_branch()
        return self._source_branch

    def _get_diff_text(self) -> str:
        # get the branch names
        source_branch = self.source_branch
        destination_branch = self.destination_branch
        # get the diff
        logger.debug(f"Getting diff between {source_branch.name} and {destination_branch.name}")
        comparison = self.repository.compare(source_branch.name, destination_branch.name)
        # get the url
        diff_url = comparison.diff_url
        # we need the headers
        headers = {"Authorization": self.api_key}
        # get the diff
        logger.debug(f"Getting diff from {diff_url}")
        response = requests.get(diff_url, headers=headers)
        if response.status_code != 200:
            raise SmartReviewGithubException(
                exception_message=f"Could not get the diff of the PR. Response: {response.text}"
            )
        return response.text

    @property
    def diff_text(self) -> str:
        if not self._diff_text:
            self._diff_text = self._get_diff_text()
        return self._diff_text

    def _get_pr_files(self) -> Dict[str, File]:
        logger.debug(f"Getting files for PR {self.pr_number}")
        files = self.pull_request.get_files()
        return {file.filename: file for file in files}

    @property
    def pr_files(self) -> Dict[str, File]:
        if not self._pr_files:
            self._pr_files = self._get_pr_files()
        return self._pr_files

    def _get_repository_files(self) -> Dict[str, ContentFile]:
        logger.debug(f"Getting files for repository {self.owner}/{self.repo}")
        files = self.repository.get_contents("")
        if isinstance(files, ContentFile):
            return {files.path: files}
        return {file.path: file for file in files}

    @property
    def repository_files(self) -> Dict[str, ContentFile]:
        if not self._repository_files:
            self._repository_files = self._get_repository_files()
        return self._repository_files

    def _get_pr_commits(self) -> List[Commit]:
        logger.debug(f"Getting commits for PR {self.pr_number}")
        return list(self.pull_request.get_commits())

    @property
    def pr_commits(self) -> List[Commit]:
        logger.debug(f"Getting commits for PR {self.pr_number}")
        if not self._pr_commits:
            self._pr_commits = self._get_pr_commits()
        return self._pr_commits

    @property
    def latest_commit(self) -> Commit:
        logger.debug(f"Getting latest commit for PR {self.pr_number}")
        return self.pr_commits[-1]

    def get_pr_file_contents(self, file: File) -> str:
        logger.debug(f"Getting contents of file {file.filename}")
        url = file.contents_url
        # we need the headers
        headers = {"Authorization": self.api_key}
        # get the content
        logger.debug(f"Getting content from {url}")
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise SmartReviewGithubException(
                exception_message=f"Could not get the content of the file {file.filename}. Response: {response.text}"
            )
        response_jsn = json.loads(response.text)
        return response_jsn.get("body", "")

    def _get_pr_context(self) -> str:
        logger.debug(f"Getting context for PR {self.pr_number}")
        context: str = ""
        for file_name, file in self.pr_files.items():
            try:
                content = self.get_pr_file_contents(file)
                context += f"## {file_name}\n\n{content}\n\n"
            except Exception as e:
                logger.error(f"Could not get content of file {file_name}. Error: {e}")
        return context

    @property
    def context(self) -> str:
        if not self._context:
            self._context = self._get_pr_context()
        return self._context

    def create_positive_review(self, message: str) -> PullRequestReview:
        """Create a positive review."""
        logger.debug("Creating a positive review.")
        # create the review comment
        review_comment = f"## Smart Review\n\n{message}"
        # create the review
        review = self.pull_request.create_review(body=review_comment, event="APPROVE")
        return review

    def create_negative_review_comment(
        self, negative_info: NegativeInformation
    ) -> PullRequestComment:
        """Create a negative review comment."""
        logger.debug("Creating a negative review comment.")
        # create the review comment
        review_body = f"## Smart Review\n\n{negative_info.body}"
        # create the review comment
        comment = self.pull_request.create_review_comment(
            body=review_body,
            path=negative_info.path,
            line=negative_info.line_no,
            commit=negative_info.commit,
            as_suggestion=False,
        )
        return comment

    def create_negative_review(
        self, message: str, negative_info: List[NegativeInformation]
    ) -> PullRequestReview:
        """Create a negative review."""
        logger.debug("Creating a negative review.")
        # create the review comment
        review_comment = f"## Smart Review\n\n{message}"
        for info in negative_info:
            self.create_negative_review_comment(info)
        # create the review
        review = self.pull_request.create_review(body=review_comment, event="REQUEST_CHANGES")
        return review
