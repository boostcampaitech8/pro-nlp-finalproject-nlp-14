#!/usr/bin/env python
"""Neo4j 스키마 초기화

make neo4j-init 또는 직접 실행으로 제약조건과 인덱스를 생성.
IF NOT EXISTS 구문으로 이미 존재하면 스킵.

사용법:
    cd backend && uv run python -m neo4j.init_schema
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

# .env 파일 로드 (.env)
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Neo4j 연결 설정
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Cypher 스크립트 경로 (현재 디렉토리)
SCHEMA_DIR = Path(__file__).parent


def init_neo4j_schema() -> bool:
    """Neo4j 스키마 초기화 (제약조건 + 인덱스)

    Returns:
        bool: 성공 여부
    """
    logger.info("Neo4j 스키마 초기화 시작...")
    logger.info(f"연결: {NEO4J_URI}")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        # 연결 테스트
        driver.verify_connectivity()
        logger.info("Neo4j 연결 성공")

        # constraints.cypher 실행
        constraints_file = SCHEMA_DIR / "constraints.cypher"
        if constraints_file.exists():
            _execute_cypher_file(driver, constraints_file)
            logger.info("제약조건 생성 완료")
        else:
            logger.warning(f"constraints.cypher 파일 없음: {constraints_file}")

        # indexes.cypher 실행
        indexes_file = SCHEMA_DIR / "indexes.cypher"
        if indexes_file.exists():
            _execute_cypher_file(driver, indexes_file)
            logger.info("인덱스 생성 완료")
        else:
            logger.warning(f"indexes.cypher 파일 없음: {indexes_file}")

        logger.info("Neo4j 스키마 초기화 완료")
        return True

    except Exception as e:
        logger.error(f"Neo4j 스키마 초기화 실패: {e}")
        return False

    finally:
        driver.close()


def _execute_cypher_file(driver, file_path: Path) -> None:
    """Cypher 파일의 각 문장 실행"""
    content = file_path.read_text()

    # 주석 제거 및 세미콜론으로 분리
    statements = []
    for line in content.split(";"):
        line = line.strip()
        # 빈 줄과 주석만 있는 경우 스킵
        if line and not line.startswith("//"):
            # 줄 단위 주석 제거
            clean_lines = [l for l in line.split("\n") if not l.strip().startswith("//")]
            statement = "\n".join(clean_lines).strip()
            if statement:
                statements.append(statement)

    with driver.session() as session:
        for stmt in statements:
            logger.debug(f"실행: {stmt[:50]}...")
            session.run(stmt)


if __name__ == "__main__":
    success = init_neo4j_schema()
    sys.exit(0 if success else 1)
