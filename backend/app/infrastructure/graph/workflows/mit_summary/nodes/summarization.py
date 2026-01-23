"""요약 생성 노드"""

import logging
from datetime import datetime

from langchain_community.chat_models import ChatClovaX
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.infrastructure.graph.config import NCP_CLOVASTUDIO_API_KEY
from app.infrastructure.graph.schema.models import SummaryOutput, Utterance
from app.infrastructure.graph.workflows.mit_summary.state import MitSummaryState

logger = logging.getLogger(__name__)

# Summary 전용 LLM (낮은 temperature로 정확성 향상)
summary_llm = ChatClovaX(
    temperature=0.1,
    max_tokens=1024,
    model="HCX-003",
    api_key=NCP_CLOVASTUDIO_API_KEY,
)


async def generate_summary(state: MitSummaryState) -> MitSummaryState:
    """LLM으로 회의 요약 생성 (하이퍼클로바X)

    Contract:
        reads: mit_summary_utterances_raw, mit_summary_contradictions, mit_summary_metadata
        writes: mit_summary_result, mit_summary_text
        side-effects: LLM API 호출 (HyperCLOVA X)
        failures: SUMMARY_GENERATION_FAILED -> errors 기록

    구현 전략:
    1. messages에서 추출한 발화를 시간순으로 정렬
    2. 발화 텍스트를 LLM 입력 형식으로 포매팅
    3. 하이퍼클로바X 호출 (temperature 낮게)
    4. 구조화된 응답 파싱 -> SummaryOutput
    5. 자연어 응답 생성 (contradictions 포함)
    """
    logger.info("요약 생성 시작")

    utterances = state.get("mit_summary_utterances_raw", [])
    contradictions = state.get("mit_summary_contradictions", [])
    metadata = state.get("mit_summary_metadata", {})

    if not utterances:
        logger.warning("요약할 발화 없음")
        return MitSummaryState(
            mit_summary_text="요약할 내용이 없습니다.",
            mit_summary_result=SummaryOutput(
                overall="요약할 내용이 없습니다.", key_points=[]
            ),
        )

    try:
        # 발화 텍스트 포매팅
        formatted_text = _format_utterances_for_llm(utterances)
        logger.debug(f"포매팅된 발화 길이: {len(formatted_text)} 문자")

        # LLM 호출로 요약 생성
        parser = PydanticOutputParser(pydantic_object=SummaryOutput)

        prompt = ChatPromptTemplate.from_template(
            "당신은 회의 내용을 정확하고 간결하게 요약하는 AI 비서입니다.\n\n"
            "다음은 회의 발화 기록입니다:\n\n"
            "{utterances}\n\n"
            "위 회의 내용을 다음 형식으로 요약해주세요:\n"
            "1. overall: 전체 회의 내용을 3-5문장으로 요약\n"
            "2. key_points: 가장 중요한 포인트 3-5개 (리스트)\n"
            "3. topics: 토픽별 요약 (선택적)\n"
            "4. decisions_mentioned: 회의 중 언급된 결정사항이나 합의 내용\n\n"
            "중요: 반드시 JSON 형식으로만 응답하세요!\n\n"
            "{format_instructions}"
        )

        chain = prompt | summary_llm | parser

        logger.info("LLM 호출 시작 (HyperCLOVA X)")
        summary_result = chain.invoke(
            {
                "utterances": formatted_text,
                "format_instructions": parser.get_format_instructions(),
            }
        )

        # contradictions 추가
        if contradictions:
            summary_result.contradictions = contradictions

        # metadata 추가
        summary_result.summary_metadata = {
            **metadata,
            "generated_at": datetime.utcnow().isoformat(),
            "llm_model": "HCX-003",
            "utterance_count": len(utterances),
        }

        logger.info("요약 생성 성공")

        # 자연어 응답 생성
        summary_text = _build_natural_language_response(summary_result)

        # 자체 평가
        evaluation_passed, evaluation_reason = _self_evaluate_summary(
            summary_result, utterances
        )

        logger.info(f"자체 평가: {evaluation_passed} - {evaluation_reason}")

        return MitSummaryState(
            mit_summary_result=summary_result,
            mit_summary_text=summary_text,
            mit_summary_self_evaluation_passed=evaluation_passed,
            mit_summary_self_evaluation_reason=evaluation_reason,
            tool_results=summary_text,  # Orchestration에서 사용
        )

    except Exception as e:
        logger.exception("요약 생성 실패")
        return MitSummaryState(
            mit_summary_errors={
                "generate_summary": f"SUMMARY_GENERATION_FAILED: {str(e)}"
            }
        )


def _format_utterances_for_llm(utterances: list[Utterance]) -> str:
    """발화 목록을 LLM 입력 형식으로 변환

    형식:
    [00:00:15] 홍길동: 안녕하세요. 회의를 시작하겠습니다.
    [00:00:23] 김철수: 네, 오늘 안건은 예산 관련입니다.
    ...
    """
    lines = []
    for utt in sorted(utterances, key=lambda u: u.start_time):
        timestamp_str = _format_timestamp(utt.start_time)
        lines.append(f"[{timestamp_str}] {utt.speaker_name}: {utt.text}")

    return "\n".join(lines)


def _format_timestamp(seconds: float) -> str:
    """초를 [HH:MM:SS] 형식으로 변환"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _build_natural_language_response(summary: SummaryOutput) -> str:
    """SummaryOutput을 자연어 응답으로 변환

    설계 결정:
    - 전체 요약 + 핵심 포인트를 자연스러운 문장으로 조합
    - 모순이 감지되면 경고 추가
    - 마크다운 형식 지원 (UI에서 렌더링)
    """
    parts = []

    # 전체 요약
    parts.append(f"## 📋 회의 요약\n\n{summary.overall}")

    # 핵심 포인트
    if summary.key_points:
        parts.append("\n## 🔑 핵심 포인트\n")
        for i, point in enumerate(summary.key_points, 1):
            parts.append(f"{i}. {point}")

    # 토픽별 요약
    if summary.topics:
        parts.append("\n## 📌 토픽별 요약\n")
        for topic in summary.topics:
            parts.append(f"**{topic['topic']}**\n{topic['summary']}\n")

    # 언급된 결정사항
    if summary.decisions_mentioned:
        parts.append("\n## ✅ 언급된 결정사항\n")
        for decision in summary.decisions_mentioned:
            parts.append(f"- {decision}")

    # 모순 경고
    if summary.contradictions:
        parts.append("\n## ⚠️ 모순 감지\n")
        parts.append(
            f"기존 GT와 모순되는 내용이 {len(summary.contradictions)}건 감지되었습니다.\n"
        )
        for i, contradiction in enumerate(summary.contradictions, 1):
            severity_emoji = {
                "low": "🟡",
                "medium": "🟠",
                "high": "🔴",
            }.get(contradiction.severity, "⚪")
            parts.append(
                f"{i}. {severity_emoji} **{contradiction.gt_decision.agenda_topic}**\n"
                f"   - 발화: \"{contradiction.utterance_text[:100]}...\"\n"
                f"   - 기존 결정: \"{contradiction.gt_decision.content[:100]}...\"\n"
                f"   - 사유: {contradiction.reason}\n"
            )

    return "\n".join(parts)


def _self_evaluate_summary(
    summary: SummaryOutput, utterances: list[Utterance]
) -> tuple[bool, str]:
    """요약 결과를 자체 평가

    평가 기준:
    1. overall_summary 존재 및 최소 길이
    2. key_points 개수
    3. 입력 대비 요약 비율

    Returns:
        (passed, reason) 튜플
    """
    # 기본 필드 존재 확인
    if not summary.overall:
        return False, "overall_summary가 비어있음"

    # 최소 길이 확인 (50자)
    if len(summary.overall) < 50:
        return False, f"overall_summary 너무 짧음 ({len(summary.overall)}자 < 50자)"

    # key_points 개수 확인
    if not summary.key_points or len(summary.key_points) < 2:
        return (
            False,
            f"key_points 부족 ({len(summary.key_points) if summary.key_points else 0}개 < 2개)",
        )

    # key_points 각 항목 길이 확인
    for i, point in enumerate(summary.key_points):
        if len(point) < 10:
            return False, f"key_points[{i}] 너무 짧음 ({len(point)}자)"

    # 입력 대비 요약 비율 확인 (너무 긴 경우 요약이 아님)
    total_input_length = sum(len(u.text) for u in utterances)
    summary_length = len(summary.overall) + sum(len(p) for p in summary.key_points)

    if total_input_length > 0:
        compression_ratio = summary_length / total_input_length
        if compression_ratio > 0.8:  # 요약이 원문의 80% 이상이면 실패
            return False, f"압축률 부족 (요약/원문 = {compression_ratio:.2f} > 0.8)"

    # 모든 조건 통과
    return True, "모든 품질 기준 충족"
