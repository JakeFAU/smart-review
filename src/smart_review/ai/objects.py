import logging

from abc import ABC
from datetime import datetime
from enum import Enum
from typing import List

from attrs import define, field

logger = logging.getLogger(__name__)


class ResponseTypeEnum(str, Enum):
    """The type of response from the LLM."""

    POSITIVE_REVIEW = "positive_review"
    ADDITIONAL_FILES = "additional_files"
    NEGATIVE_REVIEW = "negative_review"


@define
class ReviewResponse(ABC):
    """A response to a pull request review."""

    review_message: str = field(init=True)
    timestamp: float = field(factory=datetime.now().timestamp, init=False)
    review_type: ResponseTypeEnum = field(init=True)


@define
class AdditionalFilesResponse(ReviewResponse):
    """A response that requests additional files."""

    review_type: ResponseTypeEnum = field(default=ResponseTypeEnum.ADDITIONAL_FILES, init=False)
    additional_file_paths: List[str]


@define
class LineReview(ReviewResponse):
    """A review of a line of code."""

    line_no: int = field(init=True)


@define
class FileReview(ReviewResponse):
    """A review of a file."""

    file_path: str = field(init=True)
    reviews: List[LineReview] = field(default=[], init=True)


@define
class NegativeReview(ReviewResponse):
    """A negative review response."""

    review_type: ResponseTypeEnum = field(default=ResponseTypeEnum.NEGATIVE_REVIEW, init=False)
    reviews: List[FileReview] = field(default=[], init=True)
