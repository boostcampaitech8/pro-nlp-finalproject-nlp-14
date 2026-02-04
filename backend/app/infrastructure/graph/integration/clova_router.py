"""Clova Studio Router API 클라이언트

Clova Studio의 Router API를 호출하여 쿼리를 도메인별로 분류하고
콘텐츠 필터링 및 세이프티 체크를 수행합니다.

API 문서: https://api.ncloud-docs.com/docs/clovastudio-router
"""

import logging
import uuid
from typing import Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ClovaRouterRequest(BaseModel):
    """Clova Router API 요청 모델"""

    query: str
    chatHistory: list[dict] = Field(default_factory=list)


class ClovaRouterDomainResult(BaseModel):
    """도메인 분류 결과"""

    result: str  # 도메인명 (예: "simple_answer")
    called: bool  # 도메인 분류 수행 여부


class ClovaRouterContentResult(BaseModel):
    """콘텐츠 필터 결과"""

    result: list[str]  # 필터링된 항목 리스트
    called: bool  # 콘텐츠 필터 수행 여부


class ClovaRouterSafetyResult(BaseModel):
    """세이프티 필터 결과"""

    result: list[str]  # 세이프티 필터 항목 리스트
    called: bool  # 세이프티 필터 수행 여부


class ClovaRouterUsage(BaseModel):
    """토큰 사용량"""

    promptTokens: int
    completionTokens: int
    totalTokens: int


class ClovaRouterResultData(BaseModel):
    """Router 결과 데이터"""

    domain: ClovaRouterDomainResult
    blockedContent: ClovaRouterContentResult
    safety: ClovaRouterSafetyResult
    usage: ClovaRouterUsage


class ClovaRouterStatus(BaseModel):
    """Router 응답 상태"""

    code: str
    message: str


class ClovaRouterResponse(BaseModel):
    """Clova Router API 응답 모델"""

    status: ClovaRouterStatus
    result: ClovaRouterResultData


class ClovaRouterClient:
    """Clova Studio Router API 클라이언트

    Clova Studio의 Router API를 호출하여 쿼리를 도메인별로 분류합니다.

    Usage:
        >>> async with ClovaRouterClient(router_id="...", version=1, api_key="...") as client:
        ...     response = await client.route("안녕하세요")
        ...     print(response["result"]["domain"]["result"])
        "greeting"

    Attributes:
        router_id: Clova Studio Router ID
        version: Router 버전 (default: 1)
        api_key: NCP API 키
        endpoint: API 엔드포인트 URL
    """

    def __init__(self, router_id: str, version: int, api_key: str):
        """Clova Router 클라이언트 초기화

        Args:
            router_id: Clova Studio에서 생성한 Router ID
            version: Router 버전 (1 이상)
            api_key: NCP Clova Studio API 키
        """
        self.router_id = router_id
        self.version = version
        self.api_key = api_key
        self.endpoint = (
            f"https://clovastudio.stream.ntruss.com/v1/routers/"
            f"{router_id}/versions/{version}/route"
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Context manager 진입 - HTTP 클라이언트 초기화"""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        logger.debug(f"Clova Router 클라이언트 초기화: {self.endpoint}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료 - HTTP 클라이언트 정리"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.debug("Clova Router 클라이언트 종료")

    async def route(
        self, query: str, chat_history: Optional[list[dict]] = None
    ) -> dict:
        """쿼리 라우팅 실행

        Args:
            query: 사용자 쿼리
            chat_history: 대화 히스토리 (선택)
                형식: [{"role": "user", "content": "..."}, ...]

        Returns:
            Clova Router API 응답
            {
                "status": {"code": "20000", "message": "OK"},
                "result": {
                    "domain": {"result": "greeting", "called": True},
                    "blockedContent": {"result": [], "called": True},
                    "safety": {"result": [], "called": True},
                    "usage": {"promptTokens": 10, "completionTokens": 5, "totalTokens": 15}
                }
            }

        Raises:
            RuntimeError: 클라이언트가 초기화되지 않음
            httpx.HTTPError: HTTP 요청 실패
            ValueError: API 응답 오류 (status.code != "20000")
        """
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use 'async with ClovaRouterClient(...)' context manager."
            )

        payload = {"query": query, "chatHistory": chat_history or []}

        # 요청마다 고유한 Request ID 생성
        request_id = str(uuid.uuid4()).replace("-", "")
        headers = {"X-NCP-CLOVASTUDIO-REQUEST-ID": request_id}

        logger.debug(f"Clova Router 호출: query={query[:50]}..., request_id={request_id}")

        try:
            response = await self._client.post(self.endpoint, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()

            # 상태 코드 확인
            status = data.get("status", {})
            if status.get("code") != "20000":
                error_msg = status.get("message", "Unknown error")
                raise ValueError(f"Clova Router API error: {error_msg}")

            logger.debug(
                f"Clova Router 응답: domain={data.get('result', {}).get('domain', {}).get('result')}"
            )

            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise


async def create_clova_router_client(
    router_id: str, version: int, api_key: str
) -> ClovaRouterClient:
    """Clova Router 클라이언트 팩토리 함수

    Args:
        router_id: Router ID
        version: Router 버전
        api_key: API 키

    Returns:
        초기화된 ClovaRouterClient 인스턴스
    """
    return ClovaRouterClient(router_id=router_id, version=version, api_key=api_key)
