"""Clova Studio LLM 클라이언트 (스트리밍 지원)"""

import logging
from collections.abc import AsyncGenerator

from langchain_community.chat_models import ChatClovaX
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class ClovaStudioLLMClient:
    """Clova Studio LLM 클라이언트"""

    def __init__(
        self,
        api_key: str,
        model: str = "HCX-003",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        self._llm = ChatClovaX(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        logger.info(
            "ClovaStudioLLMClient 초기화: model=%s, temperature=%s, max_tokens=%s",
            self.model,
            self.temperature,
            self.max_tokens,
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """LLM 스트리밍 응답"""
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        logger.info("LLM 스트리밍 시작: prompt=%s...", prompt[:100])

        async for chunk in self._llm.astream(messages):
            if chunk.content:
                yield chunk.content

        logger.info("LLM 스트리밍 완료")
