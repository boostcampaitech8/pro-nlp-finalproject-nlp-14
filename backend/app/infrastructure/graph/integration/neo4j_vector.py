"""Neo4j vector index/embedding utilities."""

import logging
from typing import Any

from app.core.config import get_settings
from app.core.neo4j import get_neo4j_driver
from app.infrastructure.graph.integration.embeddings import get_embeddings_model
from neo4j import AsyncResult

logger = logging.getLogger(__name__)


def _build_meeting_text(record: dict[str, Any]) -> str:
    parts = [
        record.get("title") or "",
        record.get("description") or "",
        record.get("summary") or "",
        record.get("transcript") or "",
    ]
    text = "\n".join(p.strip() for p in parts if p and p.strip())
    return text.strip()


async def ensure_meeting_vector_index(dimensions: int) -> None:
    settings = get_settings()
    index_name = settings.neo4j_vector_index_name

    if not index_name:
        logger.warning("[Neo4j Vector] index name not configured")
        return

    driver = get_neo4j_driver()
    async with driver.session() as session:
        exists: AsyncResult = await session.run(
            "SHOW INDEXES WHERE name = $index_name AND type = 'VECTOR'",
            index_name=index_name,
        )
        rows = await exists.data()
        if rows:
            options = rows[0].get("options") or {}
            index_config = options.get("indexConfig") or {}
            current_dim = index_config.get("vector.dimensions")
            if current_dim is not None and int(current_dim) != int(dimensions):
                logger.warning(
                    "[Neo4j Vector] index dimension mismatch: %s (current=%s, expected=%s)",
                    index_name,
                    current_dim,
                    dimensions,
                )
                # Drop existing index with wrong dimensions
                drop_query = f"DROP INDEX {index_name} IF EXISTS"
                await session.run(drop_query)
                logger.info(f"[Neo4j Vector] dropped incorrect index: {index_name}")
            else:
                logger.info(f"[Neo4j Vector] index exists with correct dimensions: {index_name}")
                return

        # Create new index with correct dimensions (use string interpolation for parameters)
        create_query = f"""
        CREATE VECTOR INDEX {index_name} IF NOT EXISTS
        FOR (m:Meeting) ON (m.embedding)
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {dimensions},
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """
        await session.run(create_query)
        logger.info(f"[Neo4j Vector] index created with {dimensions} dimensions: {index_name}")


async def backfill_meeting_embeddings(batch_size: int = 100, max_items: int | None = None) -> int:
    logger.info("[Neo4j Vector] backfill meeting embeddings start")

    embeddings_model = get_embeddings_model()
    sample = embeddings_model.embed_query("샘플")
    if hasattr(sample, "tolist"):
        sample = sample.tolist()
    dimensions = len(sample)

    await ensure_meeting_vector_index(dimensions)

    driver = get_neo4j_driver()
    total = 0
    skip = 0

    while True:
        if max_items is not None and total >= max_items:
            break

        async with driver.session() as session:
            query = """
            MATCH (m:Meeting)
            WHERE m.embedding IS NULL OR size(m.embedding) = 0
            RETURN m.id AS id,
                   m.title AS title,
                   m.description AS description,
                   m.summary AS summary,
                   m.transcript AS transcript
            SKIP $skip
            LIMIT $limit
            """
            result = await session.run(query, skip=skip, limit=batch_size)
            records = await result.data()

        if not records:
            break

        texts = [_build_meeting_text(r) for r in records]
        embeddings = embeddings_model.encode(texts, batch_size=min(32, batch_size))
        if hasattr(embeddings, "tolist"):
            embeddings = embeddings.tolist()

        rows = []
        for record, embedding in zip(records, embeddings, strict=False):
            if hasattr(embedding, "tolist"):
                embedding = embedding.tolist()
            if not embedding:
                embedding = [0.0] * dimensions
            rows.append({"id": record["id"], "embedding": embedding})

        async with driver.session() as session:
            update_query = """
            UNWIND $rows AS row
            MATCH (m:Meeting {id: row.id})
            SET m.embedding = row.embedding,
                m.embedding_updated_at = datetime()
            """
            await session.run(update_query, rows=rows)

        total += len(rows)
        skip += batch_size
        logger.info(f"[Neo4j Vector] backfilled {total} meetings")

    logger.info(f"[Neo4j Vector] backfill completed: {total} meetings")
    return total
