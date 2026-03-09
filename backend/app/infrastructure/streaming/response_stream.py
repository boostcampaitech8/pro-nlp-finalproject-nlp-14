"""스트리밍 응답 시스템 - Streaming Response Generator"""

import asyncio
import logging
from datetime import datetime
from typing import AsyncIterator

logger = logging.getLogger(__name__)


class StreamingResponseGenerator:
    """실시간 응답 스트리밍 (사용자 UX 개선)
    
    전략:
    1. Planner 상태 스트리밍
    2. 검색 결과 스트리밍
    3. 답변 생성 토큰 스트리밍
    
    예상 효과:
    - 실제 지연: 동일
    - 체감 지연: 50% 감소 (진행상황 표시)
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.start_time = datetime.now()
        self.events = []
        self.collected_answer = ""

    async def stream_planning_start(self) -> str:
        """Planner 시작 스트림"""
        event = {
            "type": "planning_start",
            "timestamp": datetime.now(),
            "message": "🔍 쿼리를 분석 중입니다..."
        }
        self.events.append(event)
        logger.info(f"[Streaming] Planning Start: {event['message']}")
        return self._format_sse(event)

    async def stream_planning_complete(self, planning_info: dict) -> str:
        """Planner 완료 스트림"""
        event = {
            "type": "planning_complete",
            "timestamp": datetime.now(),
            "strategy": planning_info.get("strategy"),
            "message": f"✅ 검색 전략 결정됨: {planning_info.get('strategy', 'unknown')}"
        }
        self.events.append(event)
        logger.info(f"[Streaming] Planning Complete: {event['message']}")
        return self._format_sse(event)

    async def stream_search_start(self) -> str:
        """검색 시작 스트림"""
        event = {
            "type": "search_start",
            "timestamp": datetime.now(),
            "message": "🔎 데이터베이스를 검색 중입니다..."
        }
        self.events.append(event)
        logger.info(f"[Streaming] Search Start: {event['message']}")
        return self._format_sse(event)

    async def stream_search_results(self, results_count: int) -> str:
        """검색 결과 스트림"""
        event = {
            "type": "search_results",
            "timestamp": datetime.now(),
            "result_count": results_count,
            "message": f"📊 {results_count}개의 결과를 찾았습니다"
        }
        self.events.append(event)
        logger.info(f"[Streaming] Search Results: {event['message']}")
        return self._format_sse(event)

    async def stream_answer_generation_start(self) -> str:
        """답변 생성 시작 스트림"""
        event = {
            "type": "answer_generation_start",
            "timestamp": datetime.now(),
            "message": "✨ 최종 답변을 작성 중입니다..."
        }
        self.events.append(event)
        logger.info(f"[Streaming] Answer Generation Start: {event['message']}")
        return self._format_sse(event)

    async def stream_answer_tokens(
        self, tokens: AsyncIterator[str]
    ) -> AsyncIterator[str]:
        """답변 생성 토큰 스트리밍 (실시간 출력)

        Args:
            tokens: LLM으로부터의 토큰 스트림

        Yields:
            SSE 형식의 토큰
        """
        logger.info("[Streaming] Answer Tokens Streaming Start")
        collected_answer = ""

        async for token in tokens:
            collected_answer += token
            event = {
                "type": "answer_token",
                "timestamp": datetime.now(),
                "token": token,
            }
            self.events.append(event)
            yield self._format_sse(event)
            # 과도한 스트리밍 방지 (최소 단위)
            await asyncio.sleep(0.01)

        logger.info(f"[Streaming] Answer Complete: {len(collected_answer)} chars")
        # async generator에서는 return value를 사용할 수 없음
        # 수집된 답변은 self.collected_answer로 저장
        self.collected_answer = collected_answer

    async def stream_completion(self) -> str:
        """응답 완료 스트림"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        event = {
            "type": "completion",
            "timestamp": datetime.now(),
            "elapsed_seconds": elapsed,
            "message": f"✅ 완료! (소요시간: {elapsed:.1f}초)"
        }
        self.events.append(event)
        logger.info(f"[Streaming] Completion: {event['message']}")
        return self._format_sse(event)

    def _format_sse(self, event: dict) -> str:
        """이벤트를 SSE(Server-Sent Events) 형식으로 변환"""
        import json
        data = json.dumps(event, default=str)
        return f"data: {data}\n\n"

    def get_event_summary(self) -> dict:
        """이벤트 히스토리 요약"""
        return {
            "total_events": len(self.events),
            "total_time": (datetime.now() - self.start_time).total_seconds(),
            "events": self.events,
            "user_id": self.user_id
        }


class StreamingResponseBuilder:
    """스트리밍 응답 빌더 - 오케스트레이션과 통합"""

    def __init__(self, user_id: str):
        self.generator = StreamingResponseGenerator(user_id)
        self.user_id = user_id

    async def stream_full_workflow(
        self,
        planning_info: dict,
        search_results: list,
        answer_tokens: AsyncIterator[str],
    ) -> AsyncIterator[str]:
        """완전한 워크플로우 스트리밍

        1. Planner 진행상황
        2. 검색 결과
        3. 답변 생성 토큰
        4. 완료

        Args:
            planning_info: Planner 결과
            search_results: 검색 결과
            answer_tokens: LLM 토큰 스트림

        Yields:
            SSE 형식의 이벤트
        """
        try:
            # 1. Planning 스트림
            yield await self.generator.stream_planning_start()
            await asyncio.sleep(0.1)  # UI 업데이트 시간 확보
            yield await self.generator.stream_planning_complete(planning_info)

            # 2. 검색 스트림
            await asyncio.sleep(0.1)
            yield await self.generator.stream_search_start()
            await asyncio.sleep(0.1)
            yield await self.generator.stream_search_results(len(search_results))

            # 3. 답변 토큰 스트림
            await asyncio.sleep(0.1)
            yield await self.generator.stream_answer_generation_start()
            await asyncio.sleep(0.1)

            async for token_event in self.generator.stream_answer_tokens(answer_tokens):
                yield token_event

            # 4. 완료
            await asyncio.sleep(0.1)
            yield await self.generator.stream_completion()

        except Exception as e:
            logger.error(f"[Streaming] 스트리밍 에러: {str(e)}", exc_info=True)
            error_event = {
                "type": "error",
                "timestamp": datetime.now(),
                "message": f"오류 발생: {str(e)}"
            }
            yield self.generator._format_sse(error_event)

    def get_summary(self) -> dict:
        """스트리밍 요약"""
        return self.generator.get_event_summary()
