"""Neo4j 설정"""

import os

from dotenv import load_dotenv

load_dotenv()

# Neo4j 연결 설정
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Mock 설정 (기본값: 실제 Neo4j 사용, 테스트에서만 Mock)
USE_MOCK_GRAPH = os.getenv("USE_MOCK_GRAPH", "false").lower() == "true"
