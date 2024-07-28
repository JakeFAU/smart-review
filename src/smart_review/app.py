import argparse
import logging

from smart_review.control.controller import (
    AuthenticationInformation,
    Controller,
    Options,
)
from smart_review.exceptions import SmartReviewSystemException

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smart Review CLI")

    auth_group = parser.add_argument_group("authentication")
    auth_group.description = (
        "Authentication information (one of openai-token or vertex-credentials is required)"
    )
    auth_group.add_argument("--github-token", type=str, help="GitHub API token")
    llm_tokens = auth_group.add_mutually_exclusive_group(required=True)
    llm_tokens.add_argument("--openai-token", type=str, help="OpenAI API token")
    llm_tokens.add_argument("--vertex-credentials", type=str, help="Vertex AI credentials")

    github_group = parser.add_argument_group("github")
    github_group.add_argument("--github-owner", type=str, help="GitHub owner", required=True)
    github_group.add_argument("--github-repo", type=str, help="GitHub repo", required=True)
    github_group.add_argument(
        "--github-pr-number", type=int, help="GitHub PR number", required=True
    )

    llm_group = parser.add_argument_group("llm")
    llm_group.add_argument("--max-tokens", type=int, help="OpenAI max tokens")
    llm_group.add_argument("--temperature", type=float, help="OpenAI temperature")
    llm_group.add_argument("--top-p", type=float, help="OpenAI top p")
    llm_group.add_argument("--top-k", type=int, help="OpenAI top k")
    llm_group.add_argument("--frequency-penalty", type=float, help="OpenAI frequency penalty")
    llm_group.add_argument("--presence-penalty", type=float, help="OpenAI presence penalty")
    llm_group.add_argument("--max-recursion", type=int, help="Max recursion depth", default=3)

    logger.debug("Parsing arguments.")
    args = parser.parse_args()

    logger.debug("Creating Auth Information")
    auth_info = AuthenticationInformation(
        github_token=args.github_token,
        openai_key=args.openai_token,
        credentials=args.vertex_credentials,
    )
    # i dont want to print the values, but we can log that they exist
    logger.debug(
        f"Auth Information: github_token={args.github_token is not None}, openai_key={args.openai_token is not None}, credentials={args.vertex_credentials is not None}"
    )
    logger.debug("Creating Options")
    options = Options(
        pr_number=args.github_pr_number,
        github_owner=args.github_owner,
        github_repo=args.github_repo,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        frequency_penalty=args.frequency_penalty,
        presence_penalty=args.presence_penalty,
        max_recursion=args.max_recursion,
    )
    # lets log the required options
    logger.debug(
        f"Options: pr_number={options.pr_number}, github_owner={options.github_owner}, github_repo={options.github_repo}, max_recursion={options.max_recursion}"
    )
    # create the controller
    logger.debug("Creating Controller")
    controller = Controller.create_controller(auth_info=auth_info, options=options)
    logger.debug("Controller created.")
    # run the controller
    try:
        controller.perform_review()
    except Exception as e:
        logger.error(f"Error: {e}")
        raise SmartReviewSystemException(exception_message="Error during review.") from e
    logger.debug("Review completed.")


if __name__ == "__main__":
    main()
