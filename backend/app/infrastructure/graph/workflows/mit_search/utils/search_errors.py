"""검색 시스템 에러 분류 및 추적"""

from enum import Enum
from typing import Optional, Dict, Any
import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


class SearchErrorType(Enum):
    """검색 단계별 에러 분류"""
    INTENT_ANALYSIS_FAILED = "의도 분석 실패"
    NO_MATCHING_STRATEGY = "적용 전략 없음"
    CYPHER_SYNTAX_ERROR = "Cypher 문법 에러"
    CYPHER_EXECUTION_ERROR = "Cypher 실행 에러"
    NO_RESULTS = "검색 결과 없음 (정상)"
    LOW_RELEVANCE = "결과 있지만 관련성 낮음"
    LLM_TIMEOUT = "LLM 타임아웃"
    UNKNOWN = "알 수 없는 에러"


@dataclass
class SearchMetadata:
    """검색 과정의 메타데이터"""
    query: str
    intent_type: Optional[str] = None
    intent_confidence: Optional[float] = None
    strategy: Optional[str] = None
    cypher: Optional[str] = None
    error_type: Optional[SearchErrorType] = None
    error_message: Optional[str] = None
    result_count: int = 0
    result_quality_score: Optional[float] = None
    execution_time_ms: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """메타데이터를 딕셔너리로 변환"""
        return {
            "query": self.query,
            "intent": self.intent_type,
            "confidence": self.intent_confidence,
            "strategy": self.strategy,
            "error": self.error_type.value if self.error_type else None,
            "error_msg": self.error_message,
            "results": self.result_count,
            "quality": self.result_quality_score,
            "time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat()
        }


class SearchError(Exception):
    """검색 시스템 기본 에러"""
    
    def __init__(
        self,
        error_type: SearchErrorType,
        message: str,
        metadata: Optional[SearchMetadata] = None
    ):
        self.error_type = error_type
        self.message = message
        self.metadata = metadata
        super().__init__(f"[{error_type.name}] {message}")
        
        # 자동 로깅
        if metadata:
            logger.warning(
                f"Search Error: {error_type.value}",
                extra=metadata.to_dict()
            )
        else:
            logger.warning(f"Search Error: {error_type.value} - {message}")


def log_search_step(step_name: str, metadata: SearchMetadata) -> None:
    """검색 각 단계를 로깅"""
    logger.info(
        f"[{step_name}]",
        extra={
            "step": step_name,
            **metadata.to_dict()
        }
    )


def log_search_error(
    step_name: str,
    error_type: SearchErrorType,
    message: str,
    metadata: SearchMetadata
) -> None:
    """검색 에러를 구조화된 형식으로 로깅"""
    metadata.error_type = error_type
    metadata.error_message = message
    
    logger.error(
        f"[{step_name}] {error_type.value}",
        extra=metadata.to_dict()
    )
