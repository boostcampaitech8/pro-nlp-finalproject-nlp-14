"""KG (Knowledge Graph) Repository 패키지

Neo4j 기반 Knowledge Graph 저장소.
"""

from app.repositories.kg.interface import IKGRepository
from app.repositories.kg.mock_repository import MockKGRepository
from app.repositories.kg.repository import KGRepository
from app.repositories.kg.sync_repository import KGSyncRepository


def create_kg_repository() -> IKGRepository:
    """KG Repository 팩토리

    환경 설정에 따라 실제/Mock 저장소 반환.

    Returns:
        IKGRepository 구현체
    """
    from app.core.config import get_settings

    if get_settings().use_mock_graph:
        return MockKGRepository()

    from app.core.neo4j import get_neo4j_driver

    return KGRepository(get_neo4j_driver())


def create_kg_sync_repository() -> KGSyncRepository | None:
    """KG Sync Repository 팩토리

    환경 설정에 따라 실제 저장소 반환 또는 None.
    Mock 모드에서는 None 반환 (동기화 건너뜀).

    Returns:
        KGSyncRepository 또는 None
    """
    from app.core.config import get_settings

    if get_settings().use_mock_graph:
        return None

    from app.core.neo4j import get_neo4j_driver

    return KGSyncRepository(get_neo4j_driver())


__all__ = [
    "IKGRepository",
    "KGRepository",
    "MockKGRepository",
    "KGSyncRepository",
    "create_kg_repository",
    "create_kg_sync_repository",
]
