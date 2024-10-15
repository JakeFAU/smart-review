from setuptools import find_packages, setup

setup(
    name="smart-review",
    version="1.0.0",
    packages=find_packages("src"),
    package_dir={"": "src"},
    install_requires=[
        "attrs",
        "openai",
        "google-auth",
        "google-cloud-aiplatform",
        "pyGithub",
        "requests",
        "setuptools",
    ],
    extras_require={
        "dev": [
            "ruff",
            "isort",
            "bandit",
            "pre-commit",
            "mypy",
            "types-requests",
            "python-dotenv",
        ],
        "test": [
            "pytest",
            "pytest-cov",
            "pytest-mock",
            "pytest-asyncio",
            "pytest-env",
            "tox",
        ],
    },
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "smart-review = smart_review.app:main",
        ],
    },
)
