import json
from datetime import datetime
from http import HTTPStatus
from typing import Any, Optional

from attrs import asdict, define, field


@define(kw_only=True)
class SmartReviewException(Exception):
    exception_timestamp: float = field(default=datetime.now().timestamp())
    exception_message: str = field(init=True, repr=True)
    exception_status: int = field(default=HTTPStatus.INTERNAL_SERVER_ERROR.value)
    exception_component: Optional[str] = field(default=None, init=True, repr=True)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), indent=4)

    def __repr__(self) -> str:
        return json.dumps(self.to_dict(), indent=4)


@define(kw_only=True)
class SmartReviewGithubException(SmartReviewException):
    exception_status: int = field(default=HTTPStatus.BAD_REQUEST.value)
    exception_component: str = field(default="GitHub", init=True, repr=True)


@define(kw_only=True)
class SmartReviewLLMException(SmartReviewException):
    exception_status: int = field(default=HTTPStatus.BAD_REQUEST.value)
    exception_component: str = field(default="LLM", init=True, repr=True)


@define(kw_only=True)
class SmartReviewSystemException(SmartReviewException):
    exception_status: int = field(default=HTTPStatus.INTERNAL_SERVER_ERROR.value)
    exception_component: str = field(default="System", init=True, repr=True)
