#!/usr/bin/env python3
"""LLM-as-a-Judge 평가 스크립트 (generate_pr 파이프라인)

이 스크립트는 generate_pr 파이프라인의 출력을 평가합니다.
- 입력: JSONL 파일 (extraction_output + utterances)
- 평가 모델: gpt-4o (OpenAI API)
- 평가 항목: Factuality, Comprehensiveness, Structural Consistency, Evidence Accuracy, Clarity
- 출력: JSON 파일 (평가 점수 및 근거)

사용법:
    python evaluate_pr.py --input data.jsonl --output results.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

# .env 파일 로드
load_dotenv()

# =============================================================================
# 설정
# =============================================================================

EVALUATION_CONFIG = {
    "model": "gpt-4o",
    "temperature": 0,  # 재현성 확보
    "max_tokens": 512,
    "response_format": {"type": "json_object"},
}

# Rubric 기준 (rubric.md 기반, LLM이 이해하기 쉽게 재구성)
RUBRIC_CRITERIA = {
    "factuality": """
[Factuality (사실성)]
모델이 회의록을 작성할 때 원문에 없는 내용을 지어내지 않았는지 평가합니다.

점수 기준:
- 5점 (완벽): 모든 결정사항이 원문에 명확한 근거를 두고 있으며, 사실 왜곡이 전혀 없음
- 4점 (우수): 내용은 사실이나, 미미한 뉘앙스 차이가 있음
- 3점 (보통): 주요 내용은 맞으나, 날짜/숫자/고유명사 등 세부 사항에서 오류가 1~2건 존재
- 2점 (미흡): 원문 내용을 과도하게 해석하여 화자의 의도와 다른 결론 도출
- 1점 (실패): 원문에 전혀 없는 내용을 창조 (심각한 할루시네이션)

평가 시 주의사항:
- 원문 발화와 추출된 Decision/Agenda를 정밀하게 대조
- 추정이나 외부 지식으로 판단하지 말고, 실제 발화에 근거가 있는지만 확인
""",
    "comprehensiveness": """
[Comprehensiveness (완전성)]
중요한 안건이나 결정사항을 빠뜨리지 않았는지 평가합니다.

점수 기준:
- 5점 (완벽): 회의에서 내린 모든 주요 결정 사항이 빠짐없이 추출됨
- 4점 (우수): 주요 결정의 80% 이상 포함
- 3점 (보통): 주요 결정의 50~80% 포함
- 2점 (미흡): 주요 결정의 50% 미만만 포함
- 1점 (실패): 핵심 결정이 거의 누락됨

평가 시 주의사항:
- 원문 전체를 읽고 주요 결정사항 파악
- 추출된 Agenda/Decision과 비교하여 누락된 중요 사항 확인
""",

    "structural_consistency": """
[Structural Consistency (구조적 일관성)]
Agenda와 Decision 구조가 논리적으로 연결되었는지 평가합니다.

점수 기준:
- 5점 (완벽): Decision이 상위 Agenda에 논리적으로 완벽히 부합하며, 하나의 Decision이 독립적인 단일 의사결정 단위로 깔끔하게 분리됨
- 4점 (우수): Agenda와의 연관성은 명확하나, Decision의 단위가 다소 아쉬움 (예: 두 개의 관련 결정이 하나로 묶임)
- 3점 (보통): Decision이 Agenda와 관련은 있으나 분류가 다소 모호하거나, 서로 다른 성격의 결정사항들이 하나로 뭉뚱그려져 있음
- 2점 (미흡): Agenda와의 연관성이 낮아 맥락 파악이 어렵거나, 내용이 너무 포괄적이어서 구체적인 실행 단위 식별 어려움
- 1점 (실패): Decision이 해당 Agenda와 전혀 상관없거나, 의미 있는 단위로 구분되지 않음

평가 시 주의사항:
- Agenda의 topic과 Decision의 content가 논리적으로 연결되는지 확인
- Decision이 지나치게 세분화되거나 과도하게 병합되지 않았는지 검토
""",
    "evidence_accuracy": """
[Evidence Accuracy (근거 정확성)]
발화 원문 추출 기능이 정확한지 평가합니다.

점수 기준:
- 5점 (완벽): 추출된 Evidence(발화 구간)만 읽어도 해당 Decision을 도출할 수 있을 만큼 정확한 구간 인용
- 4점 (우수): 핵심 발화는 완벽하게 포함되어 있으나, 전후의 사소한 잡담이나 연결어구 등 불필요한 문장이 약간(5% 이하) 포함됨
- 3점 (보통): 불필요한 대화가 많이 섞여 문맥 파악을 방해하거나(Too broad), 핵심 문장의 일부가 잘려 문맥 추론이 필요함(Too narrow)
- 2점 (미흡): 불필요한 대화가 많이 섞이면서 동시에 핵심 문장도 잘림 (근거로서 불충분)
- 1점 (실패): 제시된 Evidence가 해당 Decision과 전혀 무관한 발화

평가 시 주의사항:
- Evidence로 제시된 발화 구간이 Decision을 뒷받침하는지 확인
- 핵심 발화가 누락되지 않았는지, 불필요한 발화가 과도하게 포함되지 않았는지 검토
""",
    "clarity": """
[Clarity (명확성)]
결정사항이 명확하게 서술되었는지 평가합니다.

점수 기준:
- 5점 (완전 명확): Decision만 읽어도 무엇이 결정되었는지 명확히 이해 가능
- 4점 (대부분 명확): 대부분 명확하나 일부 모호함
- 3점 (절반 모호): 절반 정도가 모호하거나 추가 맥락이 필요
- 2점 (대부분 모호): 대부분 모호하여 원문 없이는 이해 어려움
- 1점 (파악 불가): 무엇이 결정된 건지 전혀 파악 불가

평가 시 주의사항:
- Decision의 content, context만 읽고 이해 가능한지 판단
- 누가(who), 무엇을(what), 언제까지(when), 왜(why) 요소가 적절히 포함되었는지 확인
""",
}


# =============================================================================
# 유틸리티 함수
# =============================================================================


def format_utterances(utterances: list[dict[str, Any]]) -> str:
    """발화 목록을 읽기 쉬운 텍스트로 포맷"""
    lines = []
    for utt in utterances:
        utt_id = utt.get("id", "")
        speaker = utt.get("speaker_name", "Unknown")
        text = utt.get("text", "")
        lines.append(f"[{utt_id}] {speaker}: {text}")
    return "\n".join(lines)


def extract_evidence_text(
    evidence_spans: list[dict[str, Any]], utterances: list[dict[str, Any]]
) -> str:
    """Evidence span을 utterances에서 역참조하여 텍스트 추출"""
    if not evidence_spans:
        return "(Evidence 없음)"

    evidence_texts = []
    for span in evidence_spans:
        start_id = span.get("start_utt_id", "")
        end_id = span.get("end_utt_id", "")

        # utterances 순서대로 start_id부터 end_id까지 추출
        in_span = False
        span_texts = []
        for utt in utterances:
            if utt["id"] == start_id:
                in_span = True
            if in_span:
                speaker = utt.get("speaker_name", "Unknown")
                text = utt.get("text", "")
                span_texts.append(f"{speaker}: {text}")
            if utt["id"] == end_id:
                break

        if span_texts:
            evidence_texts.append("\n".join(span_texts))

    return "\n---\n".join(evidence_texts)


def format_agenda_for_prompt(
    agenda: dict[str, Any], utterances: list[dict[str, Any]]
) -> str:
    """Agenda 데이터를 프롬프트용 텍스트로 포맷"""
    topic = agenda.get("topic", "")
    description = agenda.get("description", "")
    evidence = agenda.get("evidence", [])

    agenda_evidence = extract_evidence_text(evidence, utterances)

    result = "[Agenda]\n"
    result += f"Topic: {topic}\n"
    result += f"Description: {description}\n"
    result += f"Evidence:\n{agenda_evidence}\n"

    decision = agenda.get("decision")
    if decision:
        content = decision.get("content", "")
        context = decision.get("context", "")
        decision_evidence = extract_evidence_text(
            decision.get("evidence", []), utterances
        )

        result += "\n[Decision]\n"
        result += f"Content: {content}\n"
        result += f"Context: {context}\n"
        result += f"Evidence:\n{decision_evidence}\n"
    else:
        result += "\n[Decision]\n(결정사항 없음)\n"

    return result


# =============================================================================
# 평가 로직
# =============================================================================


def evaluate_single_criterion(
    client: OpenAI,
    criterion: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    """단일 평가 항목에 대해 LLM 평가 수행

    Args:
        client: OpenAI 클라이언트
        criterion: 평가 항목명 (factuality, comprehensiveness 등)
        record: 평가할 레코드 (extraction_output + utterances)

    Returns:
        {"score": int, "rationale": str}
    """
    extraction = record["extraction_output"]
    utterances = record["utterances"]

    # 프롬프트 구성
    system_prompt = f"""당신은 회의록 평가 전문가입니다.

{RUBRIC_CRITERIA[criterion]}

[평가 원칙]
- 점수는 반드시 1~5의 정수로만 부여
- 근거는 핵심만 1~2문장으로 간결하게 작성
- 질문과 응답에 드러난 정보만 사용하고 추정하지 말 것

[응답 형식]
다음 JSON 형식으로만 응답하세요:
{{"score": 4, "rationale": "..."}}
"""

    # 원문 발화 포맷
    utterances_text = format_utterances(utterances)

    # Agenda/Decision 포맷
    agendas_text = []
    for i, agenda in enumerate(extraction.get("agendas", [])):
        agendas_text.append(f"\n=== Agenda {i+1} ===\n")
        agendas_text.append(format_agenda_for_prompt(agenda, utterances))

    user_prompt = f"""[원문 발화]
{utterances_text}

[추출된 회의록]
Summary: {extraction.get('summary', '')}

{''.join(agendas_text)}

위 내용을 평가해주세요.
"""

    try:
        response = client.chat.completions.create(
            model=EVALUATION_CONFIG["model"],
            temperature=EVALUATION_CONFIG["temperature"],
            max_tokens=EVALUATION_CONFIG["max_tokens"],
            response_format=EVALUATION_CONFIG["response_format"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        result = json.loads(response.choices[0].message.content)

        # 점수 검증 (1~5 범위)
        score = result.get("score", 3)
        if not isinstance(score, int) or score < 1 or score > 5:
            print(f"  ⚠️  경고: {criterion} 점수 범위 오류 ({score}), 3점으로 대체")
            score = 3

        return {
            "score": score,
            "rationale": result.get("rationale", ""),
        }

    except Exception as e:
        print(f"  ❌ {criterion} 평가 실패: {e}")
        return {
            "score": 0,
            "rationale": f"평가 실패: {str(e)}",
            "error": True,
        }


def evaluate_record(
    client: OpenAI,
    record: dict[str, Any],
    record_id: str,
) -> dict[str, Any]:
    """하나의 레코드에 대해 모든 평가 항목 수행

    Args:
        client: OpenAI 클라이언트
        record: 평가할 레코드
        record_id: 레코드 식별자

    Returns:
        {
            "record_id": str,
            "scores": {criterion: int, ...},
            "rationales": {criterion: str, ...},
            "overall_score": float,
            "errors": list[str]
        }
    """
    criteria = [
        "factuality",
        "comprehensiveness",
        "structural_consistency",
        "evidence_accuracy",
        "clarity",
    ]

    scores = {}
    rationales = {}
    errors = []

    print(f"\n평가 중: {record_id}")

    for criterion in criteria:
        print(f"  - {criterion}...", end=" ", flush=True)
        result = evaluate_single_criterion(client, criterion, record)

        if result.get("error"):
            errors.append(f"{criterion}: {result['rationale']}")
            print("❌")
        else:
            scores[criterion] = result["score"]
            rationales[criterion] = result["rationale"]
            print(f"✓ ({result['score']}점)")

    # 전체 평균 점수 계산 (에러 제외)
    valid_scores = [s for s in scores.values() if s > 0]
    overall_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

    return {
        "record_id": record_id,
        "scores": scores,
        "rationales": rationales,
        "overall_score": round(overall_score, 2),
        "errors": errors if errors else None,
    }


# =============================================================================
# 메인 로직
# =============================================================================


def load_jsonl(filepath: Path) -> list[dict[str, Any]]:
    """JSONL 파일 로드"""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"⚠️  라인 {line_num} 파싱 실패: {e}")
    return records


def save_results(results: list[dict[str, Any]], output_path: Path):
    """평가 결과를 JSON 파일로 저장"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def print_summary(results: list[dict[str, Any]]):
    """평가 결과 요약 출력"""
    print("\n" + "=" * 70)
    print("평가 결과 요약")
    print("=" * 70)

    if not results:
        print("평가된 레코드 없음")
        return

    # 평균 점수 계산
    criteria = [
        "factuality",
        "comprehensiveness",
        "structural_consistency",
        "evidence_accuracy",
        "clarity",
    ]

    avg_scores = {}
    for criterion in criteria:
        scores = [
            r["scores"].get(criterion, 0)
            for r in results
            if r["scores"].get(criterion, 0) > 0
        ]
        avg_scores[criterion] = sum(scores) / len(scores) if scores else 0.0

    overall_avg = sum(avg_scores.values()) / len(avg_scores) if avg_scores else 0.0

    print(f"\n총 평가 레코드: {len(results)}")
    print(f"전체 평균 점수: {overall_avg:.2f} / 5.0\n")

    print("항목별 평균 점수:")
    for criterion in criteria:
        print(f"  - {criterion:25s}: {avg_scores[criterion]:.2f}")

    # 에러 통계
    error_count = sum(1 for r in results if r.get("errors"))
    if error_count > 0:
        print(f"\n⚠️  에러 발생 레코드: {error_count}개")


def main():
    parser = argparse.ArgumentParser(
        description="LLM-as-a-Judge 평가 스크립트 (generate_pr)"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        required=True,
        help="입력 JSONL 파일 경로",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="출력 JSON 파일 경로",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="OpenAI API 키 (기본: 환경변수 OPENAI_API_KEY)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="평가할 레코드 수 제한 (테스트용)",
    )

    args = parser.parse_args()

    # API 키 확인
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OpenAI API 키가 필요합니다.")
        print("   --api-key 옵션으로 제공하거나, OPENAI_API_KEY 환경변수를 설정하세요.")
        sys.exit(1)

    # 입력 파일 확인
    if not args.input.exists():
        print(f"❌ 입력 파일을 찾을 수 없습니다: {args.input}")
        sys.exit(1)

    # OpenAI 클라이언트 초기화
    client = OpenAI(api_key=api_key)

    print(f"🤖 평가 모델: {EVALUATION_CONFIG['model']}")
    print(f"📂 입력 파일: {args.input}")
    print(f"📂 출력 파일: {args.output}")

    # JSONL 파일 로드
    print("\n📥 JSONL 파일 로딩 중...")
    records = load_jsonl(args.input)

    if args.limit:
        records = records[: args.limit]
        print(f"   (제한: 처음 {args.limit}개만 평가)")

    print(f"   총 {len(records)}개 레코드 로드됨")

    if not records:
        print("❌ 평가할 레코드가 없습니다.")
        sys.exit(1)

    # 평가 수행
    results = []
    for i, record in enumerate(records):
        record_id = record.get("record_id", f"record-{i+1}")
        result = evaluate_record(client, record, record_id)
        results.append(result)

    # 결과 저장
    print("\n💾 결과 저장 중...")
    save_results(results, args.output)
    print(f"   ✓ 저장 완료: {args.output}")

    # 요약 출력
    print_summary(results)

    print("\n✅ 평가 완료!")


if __name__ == "__main__":
    main()
