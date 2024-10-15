import json
import logging
from http import HTTPStatus
from typing import Any, Optional

import openai
from attrs import define, field

from smart_review.ai.base import BaseLLMClient
from smart_review.exceptions import SmartReviewLLMException

logger = logging.getLogger(__name__)

SYSTEM_MESSAGE: str = (
    "You are an AI code reviewer. Please provide feedback on the changes in the pull request."
)


@define(kw_only=True)
class OpenAILLMClient(BaseLLMClient):  # type: ignore[misc]
    openai_api_key: str = field(init=True)
    openai_model: str = field(default="gpt-4o-mini", init=True)
    openai_max_tokens: Optional[int] = field(default=None, init=True)
    openai_temperature: Optional[float] = field(default=None, init=True)
    openai_top_p: Optional[float] = field(default=None, init=True)
    openai_frequency_penalty: Optional[float] = field(default=None, init=True)
    openai_presence_penalty: Optional[float] = field(default=None, init=True)

    _client: Optional[openai.OpenAI] = field(init=False, repr=False, default=None)

    def __attrs_post_init__(self) -> None:
        logger.debug("Creating OpenAI client.")
        self._client = openai.OpenAI(api_key=self.openai_api_key)

    def _talk_to_llm(self, prompt: str) -> dict[str, Any]:
        try:
            logger.info(f"Sending prompt to OpenAI: {prompt}")
            assert self._client is not None
            response = self._client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_MESSAGE},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.openai_max_tokens,
                temperature=self.openai_temperature,
                top_p=self.openai_top_p,
                frequency_penalty=self.openai_frequency_penalty,
                presence_penalty=self.openai_presence_penalty,
                response_format={"type": "json_object"},
            )
            # lets get the first response to make things easier
            logger.debug(f"Response from OpenAI: {response}")
            message = response.choices[0].message
            response_jsn_string = message.content
            if not response_jsn_string:
                return {}
            response_jsn = json.loads(response_jsn_string)
            return response_jsn  # type: ignore[no-any-return]
        except openai.APITimeoutError as e:
            logger.error(f"OpenAI API Timeout Error: {e}")
            raise SmartReviewLLMException(
                exception_message="OpenAI API Timeout Error",
                exception_status=HTTPStatus.REQUEST_TIMEOUT.value,
            )
        except openai.APIError as e:
            logger.error(f"OpenAI API Error: {e}")
            raise SmartReviewLLMException(
                exception_message="OpenAI API Error",
                exception_status=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            )
        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Error: {e}")
            raise SmartReviewLLMException(
                exception_message="Invalid JSON response from OpenAI",
                exception_status=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            )
        except Exception as e:
            logger.error(f"Unexpected Error: {e}")
            raise SmartReviewLLMException(
                exception_message="Unexpected Error",
                exception_status=HTTPStatus.INTERNAL_SERVER_ERROR.value,
            )
