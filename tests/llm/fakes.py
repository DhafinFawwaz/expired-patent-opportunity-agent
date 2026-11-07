from collections.abc import Callable, Iterator, Sequence
from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import BaseModel


class ScriptedChatModel(GenericFakeChatModel):
    """Answers with scripted messages; structured calls come back as tool calls."""

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return self


def tool_reply(schema: type[BaseModel], args: dict[str, object]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": schema.__name__, "args": args, "id": "call-1", "type": "tool_call"}],
        usage_metadata={"input_tokens": 120, "output_tokens": 40, "total_tokens": 160},
    )


def scripted(*replies: AIMessage | str) -> ScriptedChatModel:
    script: Iterator[AIMessage | str] = iter(list(replies))
    return ScriptedChatModel(messages=script)
