#!/usr/bin/env python3
"""Neo4j Meeting 벡터 인덱스/임베딩 빌드."""

import asyncio
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.graph.integration.neo4j_vector import backfill_meeting_embeddings


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    await backfill_meeting_embeddings()


if __name__ == "__main__":
    asyncio.run(main())
