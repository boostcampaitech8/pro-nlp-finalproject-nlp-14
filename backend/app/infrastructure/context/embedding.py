"""Topic Embedding - BGE-M3 기반 토픽 요약 임베딩

토픽 요약을 벡터로 변환하여 시맨틱 서치를 지원합니다.
BGE-M3 모델을 싱글톤으로 로드하여 메모리 효율성을 높입니다.
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ============================================================================
# Embedding Configuration
# ============================================================================

EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_USE_FP16 = True
EMBEDDING_DIMENSION = 1024

# BGE-M3 싱글톤 (한 번만 로드)
_embedding_model: Any | None = None
_embedding_load_attempted: bool = False


def _get_embedding_model():
    """BGE-M3 임베딩 모델을 싱글톤으로 로드.

    Returns:
        BGEM3FlagModel 인스턴스 또는 None (로드 실패 시)
    """
    global _embedding_model, _embedding_load_attempted

    if _embedding_load_attempted:
        return _embedding_model

    _embedding_load_attempted = True

    try:
        from FlagEmbedding import BGEM3FlagModel

        _embedding_model = BGEM3FlagModel(
            model_name_or_path=EMBEDDING_MODEL,
            use_fp16=EMBEDDING_USE_FP16,
        )
        logger.info(f"BGE-M3 embedding model '{EMBEDDING_MODEL}' loaded (singleton)")
        return _embedding_model
    except ImportError:
        logger.warning(
            "FlagEmbedding not installed. Install: pip install FlagEmbedding"
        )
        return None
    except Exception as e:
        logger.error(f"Failed to load BGE-M3 embedding model: {e}")
        return None


class TopicEmbedder:
    """토픽 요약 임베딩 생성기.

    BGE-M3 모델을 사용하여 토픽 요약 텍스트를 1024차원 벡터로 변환합니다.
    싱글톤 패턴으로 모델을 공유하여 메모리 효율성을 높입니다.

    Example:
        embedder = TopicEmbedder()
        vec = embedder.embed_text("예산 2억 확정, Q2 출시 결정")
        if vec is not None:
            print(f"Embedding shape: {vec.shape}")  # (1024,)
    """

    def __init__(self):
        """TopicEmbedder 초기화."""
        self._model = _get_embedding_model()

    @property
    def is_available(self) -> bool:
        """임베딩 모델 사용 가능 여부."""
        return self._model is not None

    def embed_text(self, text: str) -> np.ndarray | None:
        """텍스트를 임베딩 벡터로 변환.

        Args:
            text: 임베딩할 텍스트 (토픽 요약)

        Returns:
            numpy array (1024,) 또는 None (모델 미사용 시)
        """
        if not self._model:
            logger.debug("Embedding model not available, returning None")
            return None

        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None

        try:
            # BGE-M3는 dict 형태로 dense_vecs 반환
            result = self._model.encode(
                [text],
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            embedding = result["dense_vecs"][0]
            return np.array(embedding, dtype=np.float32)
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """여러 텍스트를 배치로 임베딩.

        Args:
            texts: 임베딩할 텍스트 리스트

        Returns:
            numpy array 리스트 (각각 1024 차원)
        """
        if not self._model or not texts:
            return []

        # 빈 텍스트 필터링
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return []

        try:
            result = self._model.encode(
                valid_texts,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            return [np.array(v, dtype=np.float32) for v in result["dense_vecs"]]
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            return []

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
