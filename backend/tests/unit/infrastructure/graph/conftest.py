"""그래프 테스트용 pytest 설정

LLM 환경변수 없이 테스트 가능하도록 mock 설정.
"""

import os
import pytest
from copy import deepcopy
from unittest.mock import patch, MagicMock

# 환경변수 설정 (import 전에 설정해야 함)
os.environ.setdefault("NCP_CLOVASTUDIO_API_KEY", "test-api-key")
os.environ.setdefault("USE_MOCK_GRAPH", "true")


@pytest.fixture(autouse=True)
def mock_llm():
    """LLM Mock (모든 테스트에 자동 적용)"""
    with patch("app.infrastructure.graph.integration.llm.llm", MagicMock()):
        yield


@pytest.fixture
def mock_data():
    """독립적인 테스트 데이터"""
    from app.infrastructure.neo4j.mock.data import MOCK_DATA
    return deepcopy(MOCK_DATA)


@pytest.fixture
def repo(mock_data):
    """테스트용 MockGraphRepository 인스턴스"""
    from app.infrastructure.neo4j.mock.graph_repository import MockGraphRepository
    return MockGraphRepository(data=mock_data)


@pytest.fixture
def mock_get_graph_repo(repo):
    """GraphDeps.get_graph_repo() Mock"""
    with patch(
        "app.infrastructure.graph.tools.mit_merge.GraphDeps.get_graph_repo",
        return_value=repo
    ):
        yield repo
