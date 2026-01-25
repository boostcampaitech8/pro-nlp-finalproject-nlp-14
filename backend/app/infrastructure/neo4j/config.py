"""Neo4j 설정"""

from app.core.config import get_settings

_settings = get_settings()

# Neo4j 연결 설정
NEO4J_URI = _settings.neo4j_uri
NEO4J_USER = _settings.neo4j_user
NEO4J_PASSWORD = _settings.neo4j_password

# Mock 설정 (기본값: 실제 Neo4j 사용, 테스트에서만 Mock)
USE_MOCK_GRAPH = _settings.use_mock_graph
