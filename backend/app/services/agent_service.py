"""Agent 서비스 (LLM 스트리밍)"""

import logging
from collections.abc import AsyncGenerator

from app.infrastructure.agent import ClovaStudioLLMClient

logger = logging.getLogger(__name__)


class AgentService:
    """LLM 스트리밍 응답을 제공하는 서비스"""

    def __init__(self, llm_client: ClovaStudioLLMClient):
        self.llm_client = llm_client

    async def process_streaming(
        self,
        user_input: str,
        system_prompt: str | None = None,
    ) -> AsyncGenerator[str, None]:
        logger.info("Agent 처리 시작: user_input=%s...", user_input[:100])

        async for token in self.llm_client.stream(user_input, system_prompt):
            yield token

        logger.info("Agent 처리 완료")
