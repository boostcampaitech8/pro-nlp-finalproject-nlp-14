"""Topic Embedding - CLOVA Studio API 기반 토픽 요약 임베딩

토픽 요약을 벡터로 변환하여 시맨틱 서치를 지원합니다.
CLOVA Studio Embedding API(v2)를 httpx로 직접 호출하여 서버 메모리 부담 없이 임베딩을 생성합니다.
"""

import asyncio
import logging

import httpx
import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ============================================================================
# Embedding Configuration
# ============================================================================

# CLOVA Studio Embedding API v2 사용
CLOVA_EMBEDDING_ENDPOINT = (
    "https://clovastudio.stream.ntruss.com/v1/api-tools/embedding/v2"
)
EMBEDDING_MODEL = "bge-m3"
EMBEDDING_DIMENSION = 1024


async def _call_clova_embedding(text: str) -> list[float] | None:
    """Clova Studio Embedding API v2 호출.

    Args:
        text: 임베딩할 텍스트

    Returns:
        임베딩 벡터 (list[float]) 또는 None (실패 시)
    """
    settings = get_settings()
    api_key = settings.ncp_clovastudio_api_key

    if not api_key:
        logger.warning("NCP_CLOVASTUDIO_API_KEY not configured")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {"text": text}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                CLOVA_EMBEDDING_ENDPOINT,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            status = result.get("status") or {}
            code = status.get("code")
            if code and str(code) != "20000":
                logger.warning(f"Clova Embedding API returned error code: {code}")
                return None

            embedding = (result.get("result") or {}).get("embedding")
            if isinstance(embedding, list) and embedding:
                return embedding

            logger.warning(f"Unexpected Clova Embedding response format: {result}")
            return None

    except httpx.HTTPStatusError as e:
        logger.error(f"Clova Embedding API HTTP error: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Clova Embedding API error: {e}")
        return None


def _call_clova_embedding_sync(text: str) -> list[float] | None:
    """Clova Studio Embedding API 동기 호출 (테스트/fallback용)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # 이벤트 루프가 없으면 새로 생성
        return asyncio.run(_call_clova_embedding(text))

    # 이벤트 루프가 있으면 새 스레드에서 실행
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, _call_clova_embedding(text))
        return future.result()


class TopicEmbedder:
    """토픽 요약 임베딩 생성기.

    CLOVA Studio Embedding API를 사용하여 토픽 요약 텍스트를 벡터로 변환합니다.
    API 기반으로 서버 메모리를 사용하지 않습니다.

    Example:
        embedder = TopicEmbedder()
        vec = await embedder.embed_text_async("예산 2억 확정, Q2 출시 결정")
        if vec is not None:
            print(f"Embedding shape: {vec.shape}")  # (1024,)
    """

    def __init__(self):
        """TopicEmbedder 초기화."""
        settings = get_settings()
        self._api_key = settings.ncp_clovastudio_api_key

    @property
    def is_available(self) -> bool:
        """임베딩 API 사용 가능 여부."""
        return bool(self._api_key)

    async def embed_text_async(self, text: str) -> np.ndarray | None:
        """텍스트를 임베딩 벡터로 변환 (비동기).

        Args:
            text: 임베딩할 텍스트 (토픽 요약)

        Returns:
            numpy array (1024,) 또는 None (실패 시)
        """
        if not self._api_key:
            logger.debug("Embedding API key not available, returning None")
            return None

        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None

        embedding = await _call_clova_embedding(text)
        if embedding is not None:
            return np.array(embedding, dtype=np.float32)
        return None

    def embed_text(self, text: str) -> np.ndarray | None:
        """텍스트를 임베딩 벡터로 변환 (동기).

        Args:
            text: 임베딩할 텍스트 (토픽 요약)

        Returns:
            numpy array (1024,) 또는 None (실패 시)
        """
        if not self._api_key:
            logger.debug("Embedding API key not available, returning None")
            return None

        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None

        embedding = _call_clova_embedding_sync(text)
        if embedding is not None:
            return np.array(embedding, dtype=np.float32)
        return None

    async def embed_batch_async(self, texts: list[str]) -> list[np.ndarray]:
        """여러 텍스트를 배치로 임베딩 (비동기).

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            numpy array 리스트 (각각 1024 차원)
        """
        if not self._api_key or not texts:
            return []

        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return []

        # 병렬로 API 호출
        tasks = [_call_clova_embedding(t) for t in valid_texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        embeddings = []
        for result in results:
            if isinstance(result, list):
                embeddings.append(np.array(result, dtype=np.float32))
            else:
                # 실패한 경우 영벡터
                embeddings.append(self.zero_vector())

        return embeddings

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """여러 텍스트를 배치로 임베딩 (동기).

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            numpy array 리스트 (각각 1024 차원)
        """
        if not self._api_key or not texts:
            return []

        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return []

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.embed_batch_async(valid_texts))

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, self.embed_batch_async(valid_texts))
            return future.result()

    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """두 벡터 간 코사인 유사도 계산.

        Args:
            vec1: 첫 번째 벡터
            vec2: 두 번째 벡터

        Returns:
            코사인 유사도 (-1 ~ 1, 보통 0 ~ 1)
        """
        if vec1 is None or vec2 is None:
            return 0.0

        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    @staticmethod
    def zero_vector() -> np.ndarray:
        """빈 임베딩 벡터 반환 (fallback용).

        Returns:
            영벡터 (1024,)
        """
        return np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)
