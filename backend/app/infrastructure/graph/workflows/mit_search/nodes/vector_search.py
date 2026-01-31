"""벡터 기반 검색 노드 - Speculative RAG 구현"""

import logging
from typing import Any

from app.core.config import get_settings
from app.core.neo4j import get_neo4j_driver
from app.infrastructure.graph.integration.embeddings import get_embeddings_model
from app.infrastructure.graph.workflows.mit_search.state import MitSearchState
from neo4j import READ_ACCESS

logger = logging.getLogger(__name__)


async def vector_search_async(state: MitSearchState) -> dict[str, Any]:
    """쿼리 임베딩을 통한 벡터 검색 (Cypher와 병렬 실행)

    Speculative RAG 전략:
    - Cypher 생성 중간에 벡터 검색 선제적 실행
    - 빠른 후보 결과 확보 (200ms 내)
    - 신뢰도 높으면 Cypher 결과 대신 사용 가능

    Args:
        state: MIT Search 상태

    Returns:
        벡터 검색 결과와 임베딩 메타데이터
    """
    logger.info("[Vector Search] 벡터 검색 시작")

    try:
        # 쿼리 임베딩
        embeddings_model = get_embeddings_model()
        query = state.get("mit_search_query", "")

        if not query:
            logger.warning("[Vector Search] 쿼리 없음")
            return {
                "vector_search_results": [],
                "vector_confidence": 0.0,
                "vector_embedding": None,
            }

        # 임베딩 생성
        query_embedding = embeddings_model.embed_query(query)
        if hasattr(query_embedding, "tolist"):
            query_embedding = query_embedding.tolist()

        # 이미 리스트인 경우 첫 번째 요소가 리스트인지 확인 (이중 리스트 방지)
        if isinstance(query_embedding, list) and len(query_embedding) > 0 and isinstance(query_embedding[0], list):
            query_embedding = query_embedding[0]

        logger.info(f"[Vector Search] 쿼리 임베딩 완료: {len(query_embedding)} 차원")

        settings = get_settings()
        index_name = settings.neo4j_vector_index_name
        top_k = settings.neo4j_vector_top_k

        if not index_name:
            logger.warning("[Vector Search] vector index name not configured")
            return {
                "vector_search_results": [],
                "vector_confidence": 0.0,
                "vector_embedding": query_embedding,
            }

        driver = get_neo4j_driver()

        async with driver.session(default_access_mode=READ_ACCESS) as session:
            # 인덱스 존재 확인
            index_check = await session.run(
                "SHOW INDEXES WHERE name = $index_name AND type = 'VECTOR'",
                index_name=index_name,
            )
            index_records = await index_check.data()
            index_row = index_records[0] if index_records else None
            if not index_row:
                logger.warning(f"[Vector Search] vector index not found: {index_name}")
                return {
                    "vector_search_results": [],
                    "vector_confidence": 0.0,
                    "vector_embedding": query_embedding,
                }

            query = """
            CALL db.index.vector.queryNodes($index_name, $k, $embedding)
            YIELD node, score
            RETURN node.id AS id,
                                     coalesce(node.title, node.name, node.summary) AS title,
                   node.created_at AS created_at,
                   score,
                                     coalesce(node.summary, node.title, node.name, '') AS graph_context
            ORDER BY score DESC
            LIMIT $k
            """

            result = await session.run(
                query,
                index_name=index_name,
                k=top_k,
                embedding=query_embedding,
            )
            vector_results = await result.data()

        vector_confidence = vector_results[0]["score"] if vector_results else 0.0

        logger.info(
            f"[Vector Search] 완료: {len(vector_results)}개 결과, "
            f"신뢰도 {vector_confidence:.2f}"
        )

        return {
            "vector_search_results": vector_results,
            "vector_confidence": vector_confidence,
            "vector_embedding": query_embedding,
        }

    except Exception as e:
        logger.error(f"[Vector Search] 에러: {str(e)}", exc_info=True)
        return {
            "vector_search_results": [],
            "vector_confidence": 0.0,
            "vector_embedding": None,
        }
