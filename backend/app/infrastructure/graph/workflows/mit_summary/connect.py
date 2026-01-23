"""MIT Summary 그래프 연결"""

from langgraph.graph import END, START, StateGraph

from app.infrastructure.graph.workflows.mit_summary.nodes import (
    detect_contradictions,
    extract_utterances_from_messages,
    generate_summary,
    retrieve_gt_decisions,
)
from app.infrastructure.graph.workflows.mit_summary.state import MitSummaryState


def build_mit_summary() -> StateGraph:
    """MIT Summary 그래프 빌드

    그래프 흐름:
    START → extractor → gt_fetcher → validator → summarizer → END
    """
    builder = StateGraph(MitSummaryState)

    # 노드 등록 (역할 명사 사용)
    builder.add_node("extractor", extract_utterances_from_messages)
    builder.add_node("gt_fetcher", retrieve_gt_decisions)
    builder.add_node("validator", detect_contradictions)
    builder.add_node("summarizer", generate_summary)

    # 엣지 연결 (선형 파이프라인)
    builder.add_edge(START, "extractor")
    builder.add_edge("extractor", "gt_fetcher")
    builder.add_edge("gt_fetcher", "validator")
    builder.add_edge("validator", "summarizer")
    builder.add_edge("summarizer", END)

    return builder
