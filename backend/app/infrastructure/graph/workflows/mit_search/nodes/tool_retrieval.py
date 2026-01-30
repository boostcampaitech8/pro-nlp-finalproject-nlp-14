"""Neo4j 검색 실행을 위한 Tool retrieval 노드."""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List

from ..state import MitSearchState
from ..tools.search_tools import execute_cypher_search_async
from ..utils.content_validator import IntentAwareContentValidator
from ..utils.confidence_calibrator import CalibratedIntentValidator
from ..utils.result_scorer import SearchResultRelevanceScorer
from ..utils.search_strategy_router import SearchStrategyRouter

logger = logging.getLogger(__name__)


def _normalize_query(query: str) -> str:
    """쿼리를 정규화합니다: 메타키워드 → 동사 → 조사 순서로 제거.
    
    한글 처리 전략:
    1. 복합어 보호: "회의", "예산", "팀" 같은 명사는 먼저 보호
    2. 불필요한 동사/조사 제거
    3. 공백 정리 및 결과 반환
    """
    import re
    
    search_query = query.strip()

    # 단계 0: 보호해야할 한글 복합어 (동사 제거 전에 보호)
    protected_terms = {
        "회의": "__PROTECTED_MEETING__",
        "예산": "__PROTECTED_BUDGET__",
        "팀": "__PROTECTED_TEAM__",
        "일정": "__PROTECTED_SCHEDULE__",
        "회의실": "__PROTECTED_ROOM__",
    }
    keywords = search_query
    protected_map = {}
    for term, placeholder in protected_terms.items():
        if term in keywords:
            protected_map[placeholder] = term
            keywords = keywords.replace(term, placeholder)

    # 단계 1: 메타 키워드 제거
    meta_keywords = ["결정사항", "사항", "내용", "정보", "것", "거"]
    for meta in meta_keywords:
        keywords = keywords.replace(meta, " ")

    # 단계 2: 동사/형용사 제거
    verbs_and_adjectives = [
        "있어", "있나", "있어요", "있습니까", "있습니다",
        "뭐야", "뭐지", "뭐냐", "뭐예요", "뭐네",
        "뭔지", "뭔데", "뭔데요",
        "할려고", "할거야", "할거냐", "할게",
        "되나", "되나요", "되지", "되네",
        "알려줘", "알려주세요", "알려줘요",
        "찾아줘", "찾아주세요", "찾아줘요",
        "보여줘", "보여주세요", "보여줄래",
        "하지", "하면서", "하면",
        "열렸어", "열렸나", "열렸어요",
        "나타내", "의미하", "표현하",
    ]
    for verb in verbs_and_adjectives:
        keywords = keywords.replace(verb, " ")

    # 단계 3: 조사/접속사 제거 (단어 경계 기준으로 정확히)
    stop_words = [
        "연결된", "관련된", "관련", "님", "에게", "과", "은", "는", "이", "가", "을", "를", "와", "랑",
        "나", "너", "그", "저", "그게", "뭐가", "뭐를", "뭐는",
        "?", "!", "야", "네", "어", "요", "언제", "어디", "누가", "누구"
    ]
    for stop_word in stop_words:
        # 단어 경계 기준으로 제거
        keywords = re.sub(r'\b' + re.escape(stop_word) + r'\b', ' ', keywords)

    # 보호된 용어 복원
    normalized = " ".join(keywords.split()).strip()
    for placeholder, original_term in protected_map.items():
        normalized = normalized.replace(placeholder, original_term)

    return normalized


def _generate_cypher_by_strategy(
    strategy: str,
    query_intent: Dict[str, Any],
    entity_types: List[str],
    normalized_keywords: str,
    filters: Dict[str, Any],
    cypher_template: str,
) -> str:
    """선택된 전략에 따라 Cypher 쿼리를 생성합니다."""
    date_filter = ""
    if filters.get("date_range"):
        date_filter = " AND n.created_at >= datetime($start_date) AND n.created_at <= datetime($end_date)"

    if strategy == "team_member_search":
        # 팀원 검색: 같은 팀의 사람들을 찾음
        cypher = f"""MATCH (u:User)-[:MEMBER_OF]->(t:Team)<-[:MEMBER_OF]-(team_member:User)
WHERE u.name CONTAINS $query AND (t)<-[:MEMBER_OF]-(:User {{id: $user_id}})
{date_filter}
RETURN team_member.id AS id, team_member.name AS title, team_member.name AS content, "active" AS status, t.created_at AS created_at, t.id AS team_id, t.name AS team_name, 1.0 AS score,
       team_member.name + '님은 ' + t.name + ' 팀의 멤버입니다.' AS graph_context
ORDER BY team_member.name ASC
LIMIT 20"""
        return cypher

    elif strategy == "user_search":
        cypher = f"""MATCH (u:User)-[:PARTICIPATED_IN]->(m:Meeting)-[:CONTAINS]->(a:Agenda)-[:HAS_DECISION]->(d:Decision)
WHERE u.name CONTAINS $query AND (m)<-[:PARTICIPATED_IN]-(:User {{id: $user_id}})
{date_filter}
RETURN d.id AS id, d.content AS content, d.status AS status, d.created_at AS created_at, m.id AS meeting_id, m.title AS meeting_title, 1.0 AS score,
       u.name + '님이 참여한 ' + m.title + ' 회의의 ' + a.topic + ' 안건에서 도출된 결정사항: ' + d.content AS graph_context
ORDER BY d.created_at DESC
LIMIT 20"""
        return cypher

    elif strategy == "meeting_search":
        cypher = f"""MATCH (u:User {{id: $user_id}})-[:PARTICIPATED_IN]->(m:Meeting)
WHERE ($query = "*" OR m.title CONTAINS $query)
{date_filter}
RETURN m.id AS id, m.title AS title, m.title AS content, m.status AS status, m.created_at AS created_at, m.id AS meeting_id, m.title AS meeting_title, 1.0 AS score,
       '회의: ' + m.title + ' (참여자: ' + u.name + ')' AS graph_context
ORDER BY m.created_at DESC
LIMIT 20"""
        return cypher

    elif strategy == "agenda_search":
        cypher = f"""MATCH (u:User {{id: $user_id}})-[:PARTICIPATED_IN]->(m:Meeting)
MATCH (m)-[:CONTAINS]->(a:Agenda)
WHERE ($query = "*" OR a.topic CONTAINS $query)
{date_filter}
RETURN a.id AS id, a.topic AS title, a.topic AS content, a.status AS status, a.created_at AS created_at, m.id AS meeting_id, m.title AS meeting_title, 1.0 AS score,
       m.title + ' 회의의 안건: ' + a.topic AS graph_context
ORDER BY a.created_at DESC
LIMIT 20"""
        return cypher

    elif strategy == "action_search":
        # Action Item 검색: 제목으로 검색하고 담당자(assignee) 정보 포함
        cypher = f"""MATCH (ai:ActionItem)
WHERE ($query = "*" OR ai.title CONTAINS $query)
{date_filter}
OPTIONAL MATCH (u:User)-[:ASSIGNED_TO]->(ai)
RETURN ai.id AS id, ai.title AS title, ai.title AS content, ai.status AS status, ai.created_at AS created_at, 
       coalesce(u.name, "미배정") AS assignee, u.id AS assignee_id, 1.0 AS score,
       'Action Item: ' + ai.title + ' (담당자: ' + coalesce(u.name, '미배정') + ', 상태: ' + ai.status + ')' AS graph_context
ORDER BY ai.created_at DESC
LIMIT 20"""
        return cypher

    elif strategy == "action_with_team_search":
        # 복합 검색: Action Item 담당자 + 그 담당자의 팀원
        # Multi-hop: ActionItem -> User (담당자) -> Team -> User (팀원)
        cypher = f"""MATCH (ai:ActionItem)
WHERE ($query = "*" OR ai.title CONTAINS $query)
{date_filter}
OPTIONAL MATCH (u:User)-[:ASSIGNED_TO]->(ai)
OPTIONAL MATCH (u)-[:MEMBER_OF]->(t:Team)<-[:MEMBER_OF]-(team_member:User)
WHERE team_member <> u
RETURN DISTINCT ai.id AS action_id, ai.title AS action_title, coalesce(u.name, "미배정") AS assignee, 
       team_member.id AS team_member_id, team_member.name AS team_member_name, 
       t.name AS team_name, u.id AS assignee_id, 1.0 AS score
ORDER BY ai.created_at DESC, team_member.name ASC
LIMIT 50"""
        return cypher

    elif strategy == "composite_search":
        # 복합 검색: FULLTEXT로 Decision/ActionItem 찾고 → 담당자 → 팀원까지 한 번에
        cypher = f"""CALL db.index.fulltext.queryNodes('decision_search', $query) YIELD node, score
MATCH (a:Agenda)-[:HAS_DECISION]->(node)
MATCH (m:Meeting)-[:CONTAINS]->(a)
WHERE (m)<-[:PARTICIPATED_IN]-(:User {{id: $user_id}})
{date_filter}
OPTIONAL MATCH (ai:ActionItem)<-[:HAS_ACTION]-(a)
OPTIONAL MATCH (assignee:User)-[:ASSIGNED_TO]->(ai)
OPTIONAL MATCH (assignee)-[:MEMBER_OF]->(team:Team)<-[:MEMBER_OF]-(teammate:User)
WHERE teammate <> assignee
WITH 
    node.id AS decision_id,
    node.content AS decision_content,
    ai.id AS action_id,
    ai.title AS action_title,
    assignee.name AS assignee_name,
    assignee.id AS assignee_id,
    teammate.id AS teammate_id,
    teammate.name AS teammate_name,
    team.name AS team_name,
    score,
    node.created_at AS created_at
RETURN DISTINCT
    decision_id,
    decision_content,
    action_id,
    action_title,
    assignee_name,
    assignee_id,
    teammate_id,
    teammate_name,
    team_name,
    score
ORDER BY score DESC, created_at DESC
LIMIT 50"""
        return cypher

    elif strategy == "text_to_cypher":
        # LLM이 생성한 Cypher를 그대로 사용
        # cypher_template에 이미 LLM 생성 쿼리가 들어있음
        return cypher_template

    else:  # "fulltext_search"
        cypher = re.sub(
            r"CALL db\.index\.fulltext\.queryNodes\(\'decision_search\',\s*[\"']([^\"']*)[\"']?\)",
            "CALL db.index.fulltext.queryNodes('decision_search', $query)",
            cypher_template,
        )
        return cypher


async def tool_executor_async(state: MitSearchState) -> Dict[str, Any]:
    """Neo4j에 대해 생성된 Cypher 쿼리를 실행.

    Contract:
        reads: mit_search_cypher, mit_search_strategy, mit_search_query, mit_search_filters, user_id
        writes: mit_search_raw_results (점수가 포함된 매칭 레코드 리스트)
        side-effects: Neo4j execute_cypher_search 호출
        failures: Neo4j 오류 → 빈 리스트 반환, 에러 로깅
    """
    
    exec_start = time.time()
    logger.info("[Tool Executor] 시작")

    try:
        cypher = state.get("mit_search_cypher", "")
        strategy = state.get("mit_search_strategy", {})
        filters = state.get("mit_search_filters", {})
        user_id = state.get("user_id", "")

        if not cypher:
            logger.warning("[Tool Executor] Cypher 쿼리 없음")
            return {"mit_search_raw_results": []}

        # 파라미터 준비
        parameters = {
            "query": strategy.get("search_term", ""),
            "user_id": user_id,
        }
        
        # 시간 필터 파라미터 추가
        date_range = filters.get("date_range")
        if date_range:
            parameters["start_date"] = date_range.get("start")
            parameters["end_date"] = date_range.get("end")

        logger.info(f"[Tool Executor] 실행 중: {strategy.get('strategy')} (검색어: {strategy.get('search_term')})")
        logger.info(f"[Tool Executor] 파라미터: {parameters}")
        logger.debug(f"[Tool Executor] Cypher:\n{cypher}")        
        # 실행 정보 출력
        print(f"\n[Cypher 실행] 전략: {strategy.get('strategy')}")
        print(f"[파라미터] query='{parameters.get('query')}', user_id='{parameters.get('user_id')}'")
        # Cypher 실행 (비동기)
        db_start = time.time()
        results = await execute_cypher_search_async(
            cypher_query=cypher,
            parameters=parameters
        )
        db_time = (time.time() - db_start) * 1000

        # Text-to-Cypher 결과가 없으면 entity_search 기반 fallback 시도
        fallback_used = False
        if not results and strategy.get("strategy") == "text_to_cypher":
            intent = state.get("mit_search_query_intent", {})
            primary_entity = intent.get("primary_entity")

            if primary_entity:
                fallback_strategy = {
                    "strategy": "user_search",
                    "search_term": primary_entity,
                    "reasoning": "text_to_cypher 결과 없음 → user_search fallback",
                }
                fallback_cypher = _generate_cypher_by_strategy(
                    strategy=fallback_strategy["strategy"],
                    query_intent=intent,
                    entity_types=filters.get("entity_types", []),
                    normalized_keywords=primary_entity,
                    filters=filters,
                    cypher_template="",
                )

                logger.info(
                    "[Tool Executor] fallback 실행: user_search",
                    extra={"primary_entity": primary_entity},
                )

                fallback_params = {"query": primary_entity, "user_id": user_id}
                if date_range:
                    fallback_params["start_date"] = date_range.get("start")
                    fallback_params["end_date"] = date_range.get("end")

                results = await execute_cypher_search_async(
                    cypher_query=fallback_cypher,
                    parameters=fallback_params,
                )
                fallback_used = True

                # ✅ P1: Fallback 사용 시 신뢰도 추가 조정
                print(f"\n[신뢰도 조정] Fallback 사용 감지 → 신뢰도 패널티 적용")
                logger.info("[Tool Executor] Fallback 사용으로 신뢰도 패널티 적용")

        total_time = (time.time() - exec_start) * 1000

        logger.info(f"[Tool Executor] 완료: {len(results)}개 결과 반환 ({total_time:.0f}ms)", extra={
            "count": len(results),
            "strategy": strategy.get('strategy'),
            "search_term": strategy.get('search_term'),
            "duration_ms": total_time,
            "fallback_used": fallback_used,
        })

        # ✅ P1: Fallback 여부를 상태에 저장 (이후 노드에서 사용)
        return {
            "mit_search_raw_results": results,
            "mit_search_fallback_used": fallback_used,
        }

    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        return {"mit_search_raw_results": []}


def tool_executor(state: MitSearchState) -> Dict[str, Any]:
    """동기 테스트용 래퍼."""
    return asyncio.run(tool_executor_async(state))


def tool_result_scorer_async(state: MitSearchState) -> Dict[str, Any]:
    """검색 결과의 관련성을 점수로 평가합니다.

    Contract:
        reads: mit_search_raw_results, mit_search_query_intent, mit_search_fallback_used
        writes: mit_search_result_quality
        side-effects: 결과 점수 계산 및 로깅
    """

    logger.info("[Result Scorer] 시작")

    try:
        results = state.get("mit_search_raw_results", [])
        intent = state.get("mit_search_query_intent", {})
        query = state.get("mit_search_query", "")
        fallback_used = state.get("mit_search_fallback_used", False)

        # Intent-Aware 내용 검증으로 alignment 점수 추가
        content_validator = IntentAwareContentValidator()
        intent_type = intent.get("intent_type")

        enriched_results = []
        for result in results:
            enriched = content_validator.enrich_result_with_intent_alignment(
                result.copy(),
                intent_type
            )
            enriched_results.append(enriched)

        scorer = SearchResultRelevanceScorer()

        # 점수 계산
        quality_report = scorer.score_results(
            results=enriched_results,
            query=query,
            expected_entity=intent.get("primary_entity"),
            search_focus=intent.get("search_focus")
        )

        result_count = quality_report.get("result_count", len(results))

        # ✅ P1: Fallback 사용 시 최종 신뢰도 조정
        original_confidence = intent.get("confidence", 0.5)
        if fallback_used:
            calibrator = CalibratedIntentValidator()
            final_confidence = calibrator.apply_confidence_penalty(
                confidence=original_confidence,
                penalty_reason="Fallback strategy used (zero results from primary)",
                penalty_amount=0.3
            )
            quality_report["confidence_after_fallback"] = final_confidence
            quality_report["fallback_impact"] = round(original_confidence - final_confidence, 2)

            print(
                f"\n[최종신뢰도] 원래: {original_confidence:.2f} → "
                f"Fallback 페널티: {quality_report['fallback_impact']:.2f} → "
                f"최종: {final_confidence:.2f}"
            )
            logger.info(
                "[Result Scorer] Fallback으로 인한 신뢰도 조정",
                extra={
                    "original": original_confidence,
                    "after_fallback": final_confidence,
                    "penalty": quality_report["fallback_impact"],
                },
            )

        logger.info(
            f"[Result Scorer] 평가 완료: {quality_report['assessment']} "
            f"({quality_report['quality_score']}/100)",
            extra={**quality_report, "result_count": result_count}
        )

        print(
            f"\n[결과평가] 품질: {quality_report['assessment']} "
            f"({quality_report['quality_score']}/100) "
            f"- {result_count}개 결과"
        )

        return {"mit_search_result_quality": quality_report}

    except Exception as e:
        logger.error(f"Result scoring failed: {e}", exc_info=True)
        return {
            "mit_search_result_quality": {
                "quality_score": 0.0,
                "assessment": "평가실패",
                "error": str(e),
                "result_count": len(state.get("mit_search_raw_results", [])),
            }
        }


def tool_result_scorer(state: MitSearchState) -> Dict[str, Any]:
    """동기 테스트용 래퍼."""
    return asyncio.run(tool_result_scorer_async(state))

