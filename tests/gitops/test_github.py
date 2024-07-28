import github.Branch
import github.Commit
import github.ContentFile
import github.File
import github.PullRequest
import github.PullRequestComment
import github.PullRequestReview
import github.Repository
import pytest
from unittest.mock import patch, MagicMock, create_autospec
import github
from src.smart_review.gitops.github import GitHubClient, NegativeInformation
from src.smart_review.exceptions import SmartReviewGithubException


@pytest.fixture
def mock_pr():
    mock_pr = MagicMock(spec=github.PullRequest.PullRequest, instance=True)
    mock_pr.get_commits.return_value = [MagicMock(spec=github.Commit.Commit, instance=True)]
    mock_pr.create_review.return_value = MagicMock(
        spec=github.PullRequestReview.PullRequestReview, instance=True
    )
    mock_pr.create_review_comment.return_value = MagicMock(
        spec=github.PullRequestComment.PullRequestComment, instance=True
    )
    return mock_pr


@pytest.fixture
def mock_repo(mock_pr):
    mock_repo = MagicMock(spec=github.Repository.Repository, instance=True)
    mock_repo.get_pull.return_value = mock_pr
    mock_repo.get_contents.return_value = MagicMock(
        spec=github.ContentFile.ContentFile, instance=True
    )
    mock_repo.get_branch.side_effect = [
        MagicMock(spec=github.Branch.Branch, instance=True),
        MagicMock(spec=github.Branch.Branch, instance=True),
    ]
    mock_repo.get_contents.return_value = [MagicMock(spec=github.File.File, instance=True)]
    return mock_repo


@pytest.fixture
def mock_github(mock_repo):
    mock_github = create_autospec(github.Github, instance=True)
    mock_github.api_key = "fake_api"
    mock_github.repo_name = "repo"
    mock_github.owner = "owner"
    mock_github.get_repo.return_value = mock_repo

    return mock_github


def test_negative_information():
    negative_info = NegativeInformation(
        body="body",
        commit=MagicMock(spec=github.Commit.Commit, instance=True),
        line_no=1,
        path="path",
    )
    assert negative_info.body == "body"
    assert isinstance(negative_info.commit, github.Commit.Commit)
    assert negative_info.line_no == 1
    assert negative_info.path == "path"


def test_github_client_constructor(mock_github):
    github_client = GitHubClient(
        api_key="fake_api",
        repo="repo",
        owner="owner",
        pr_number=1,
    )
    assert github_client.api_key == "fake_api"
    assert github_client.repo == "repo"
    assert github_client.owner == "owner"
    assert github_client.pr_number == 1


@pytest.fixture
def mock_github_client(mock_github):
    mock_client = GitHubClient(
        api_key="fake_api",
        repo="repo",
        owner="owner",
        pr_number=1,
    )
    mock_client._client = mock_github
    return mock_client


def test_client_repository(mock_github_client, mock_repo):
    assert mock_github_client.repository == mock_repo
    mock_github_client._client.get_repo.assert_called_once_with("owner/repo")


def test_client_pull_request(mock_github_client, mock_pr):
    assert mock_github_client.pull_request == mock_pr
    mock_github_client.repository.get_pull.assert_called_once_with(1)


def test_client_destination_branch(mock_github_client, mock_pr, mock_repo):
    mock_pr.base.ref = "main"
    branch = mock_github_client.destination_branch
    mock_repo.get_branch.assert_called_with("main")
    assert branch == mock_repo.get_branch.return_value


def test_client_source_branch(mock_github_client, mock_pr, mock_repo):
    mock_pr.head.ref = "feature"
    branch = mock_github_client.source_branch
    mock_repo.get_branch.assert_called_with("feature")
    assert branch == mock_repo.get_branch.return_value


@patch("requests.get")
def test_get_diff_text(mock_get, mock_github_client, mock_pr, mock_repo):
    mock_pr.head.ref = "feature"
    mock_pr.base.ref = "main"
    mock_comparison = MagicMock()
    mock_comparison.diff_url = "http://diff.url"
    mock_repo.compare.return_value = mock_comparison

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "diff text"
    mock_get.return_value = mock_response

    diff_text = mock_github_client.diff_text
    mock_repo.compare.assert_called_once_with("feature", "main")
    mock_get.assert_called_once_with("http://diff.url", headers={"Authorization": "fake_api"})
    assert diff_text == "diff text"


@patch("requests.get")
def test_get_diff_text_error(mock_get, mock_github_client, mock_pr, mock_repo):
    mock_pr.head.ref = "feature"
    mock_pr.base.ref = "main"
    mock_comparison = MagicMock()
    mock_comparison.diff_url = "http://diff.url"
    mock_repo.compare.return_value = mock_comparison

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"
    mock_get.return_value = mock_response

    with pytest.raises(SmartReviewGithubException):
        _ = mock_github_client.diff_text


def test_get_pr_files(mock_github_client, mock_pr):
    mock_file = MagicMock(spec=github.File.File, instance=True)
    mock_file.filename = "file.py"
    mock_pr.get_files.return_value = [mock_file]

    pr_files = mock_github_client.pr_files
    mock_pr.get_files.assert_called_once()
    assert pr_files == {"file.py": mock_file}


def test_get_repository_files(mock_github_client, mock_repo):
    mock_content_file = MagicMock(spec=github.ContentFile.ContentFile, instance=True)
    mock_content_file.path = "file.py"
    mock_repo.get_contents.return_value = [mock_content_file]

    repository_files = mock_github_client.repository_files
    mock_repo.get_contents.assert_called_once_with("")
    assert repository_files == {"file.py": mock_content_file}


def test_get_pr_commits(mock_github_client, mock_pr):
    mock_commit = MagicMock(spec=github.Commit.Commit, instance=True)
    mock_pr.get_commits.return_value = [mock_commit]

    pr_commits = mock_github_client.pr_commits
    mock_pr.get_commits.assert_called_once()
    assert pr_commits == [mock_commit]


@patch("requests.get")
def test_get_pr_file_contents(mock_get, mock_github_client):
    mock_file = MagicMock(spec=github.File.File, instance=True)
    mock_file.contents_url = "http://file.url"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"body": "file content"}'
    mock_get.return_value = mock_response

    content = mock_github_client.get_pr_file_contents(mock_file)
    mock_get.assert_called_once_with("http://file.url", headers={"Authorization": "fake_api"})
    assert content == "file content"


def test_create_positive_review(mock_github_client, mock_pr):
    mock_review = MagicMock(spec=github.PullRequestReview.PullRequestReview, instance=True)
    mock_pr.create_review.return_value = mock_review

    review = mock_github_client.create_positive_review("Looks good!")
    mock_pr.create_review.assert_called_once_with(
        body="## Smart Review\n\nLooks good!", event="APPROVE"
    )
    assert review == mock_review


def test_create_negative_review_comment(mock_github_client, mock_pr):
    mock_commit = MagicMock(spec=github.Commit.Commit, instance=True)
    negative_info = NegativeInformation(
        body="Needs change", commit=mock_commit, line_no=10, path="file.py"
    )
    mock_comment = MagicMock(spec=github.PullRequestComment.PullRequestComment, instance=True)
    mock_pr.create_review_comment.return_value = mock_comment

    comment = mock_github_client.create_negative_review_comment(negative_info)
    mock_pr.create_review_comment.assert_called_once_with(
        body="## Smart Review\n\nNeeds change",
        path="file.py",
        line=10,
        commit=mock_commit,
        as_suggestion=False,
    )
    assert comment == mock_comment


def test_create_negative_review(mock_github_client, mock_pr):
    mock_commit = MagicMock(spec=github.Commit.Commit, instance=True)
    negative_info = [
        NegativeInformation(body="Needs change", commit=mock_commit, line_no=10, path="file.py"),
    ]
    mock_comment = MagicMock(spec=github.PullRequestComment.PullRequestComment, instance=True)
    mock_pr.create_review_comment.return_value = mock_comment
    mock_review = MagicMock(spec=github.PullRequestReview.PullRequestReview, instance=True)
    mock_pr.create_review.return_value = mock_review

    review = mock_github_client.create_negative_review("Needs changes overall", negative_info)
    mock_pr.create_review_comment.assert_called_once_with(
        body="## Smart Review\n\nNeeds change",
        path="file.py",
        line=10,
        commit=mock_commit,
        as_suggestion=False,
    )
    mock_pr.create_review.assert_called_once_with(
        body="## Smart Review\n\nNeeds changes overall", event="REQUEST_CHANGES"
    )
    assert review == mock_review
