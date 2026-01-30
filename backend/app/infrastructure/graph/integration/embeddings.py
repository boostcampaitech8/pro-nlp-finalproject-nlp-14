"""임베딩 모델 관리자"""

import logging

logger = logging.getLogger(__name__)

# BGE 임베딩 싱글톤
_embeddings_model = None


def get_embeddings_model():
    """BGE 임베딩 모델을 싱글톤으로 로드"""
    global _embeddings_model

    if _embeddings_model is not None:
        return _embeddings_model

    try:
        from FlagEmbedding import FlagModel

        model_name = "BAAI/bge-m3"
        logger.info(f"임베딩 모델 '{model_name}' 로드 중...")

        _embeddings_model = FlagModel(
            model_name,
            query_instruction_for_retrieval="주어진 질문에 대한 관련 문서를 검색합니다.",
            use_fp16=True,
        )

        logger.info(f"임베딩 모델 '{model_name}' 로드 완료 (싱글톤)")
        return _embeddings_model

    except ImportError:
        logger.warning("FlagEmbedding 패키지가 설치되지 않았습니다. 설치: pip install FlagEmbedding")
        # Fallback: 더미 모델 반환
        return DummyEmbeddingsModel()
    except Exception as e:
        logger.error(f"임베딩 모델 로드 실패: {str(e)}", exc_info=True)
        return DummyEmbeddingsModel()


class DummyEmbeddingsModel:
    """더미 임베딩 모델 (FlagEmbedding 없을 때 fallback)"""

    def embed_query(self, text: str):
        """더미 임베딩 반환 (1536 차원)"""
        # 간단한 해시 기반 더미 임베딩
        import hashlib
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        import random
        random.seed(hash_val % (2**32))
        return [random.random() for _ in range(1536)]

    def encode(self, sentences, batch_size=32):
        """문장 배치 임베딩"""
        return [self.embed_query(s) for s in sentences]
