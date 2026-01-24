import os

from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

NCP_CLOVASTUDIO_API_KEY = os.getenv("NCP_CLOVASTUDIO_API_KEY")

# Orchestration 설정
MAX_RETRY = 3  # 최대 재시도 횟수

# Neo4j 설정
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jpassword")

# Mock 설정 (Neo4j 실제 연결 전까지 True)
USE_MOCK_GRAPH = os.getenv("USE_MOCK_GRAPH", "true").lower() == "true"
