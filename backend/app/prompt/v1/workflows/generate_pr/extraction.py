"""Agenda/Decision 추출 프롬프트

Version: 1.7.0
Description: 회의록에서 Agenda와 Decision을 추출하는 프롬프트
Changelog:
    1.0.0: 초기 버전 (workflows/extraction.py에서 분리)
    1.1.0: 도메인 용어/규칙 반영하여 추출 지침 강화
    1.2.0: 아젠다/결정 크기 정의(커밋 메시지/코드) 반영
    1.3.0: 실시간 L1 토픽 스냅샷 추가
    1.4.0: SpanRef 근거 구간 축소 강제 (대표 구간/청크 전체 범위 금지)
    1.5.0: 청크 간 agenda 병합을 위한 LLM merge 프롬프트 추가
    1.6.0: 환각 완화용 근거 우선 규칙 및 decision 문장 제약 강화
    1.7.0: 청크 병합 단계의 환각/결정 형식 제약 강화

"""

VERSION = "1.7.0"

# =============================================================================
# Agenda/Decision 추출 프롬프트
# =============================================================================

AGENDA_EXTRACTION_PROMPT = """당신은 회의록 분석 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.

다음 회의 트랜스크립트를 분석하여 아젠다와 결정사항을 추출하세요.

실시간 L1 토픽 스냅샷 (참고 정보):
{realtime_topics}

트랜스크립트:
{transcript}

분석 지침:
1. 회의에서 논의된 주요 주제(아젠다)를 식별하세요
   - 아젠다 = 커밋 메시지처럼 "한 작업에 대한 한 가지 왜/의미"를 설명하는 작은 단위
   - 가능한 한 작고 구체적으로 쪼개세요 (한 문장, 한 가지 핵심)
   - 큰 주제는 여러 개의 작은 아젠다로 분리하세요 (아젠다 수가 많아져도 됨)
   - 유사한 표현은 하나로 병합하세요
   - 아젠다 순서는 트랜스크립트 등장 순서를 따르세요
   - 트랜스크립트에 없는 내용은 추측하지 마세요
2. 각 아젠다에서 이 회의에서 "합의된 결정"만 추출하세요 (한 안건당 최대 1개)
   - 명시적 합의/확정/결정이 없으면 decision을 null로 두세요
   - 여러 안이 오간 경우 최종 합의된 결과만 남기세요
   - 보류/연기/추가조사로 합의된 것도 결정으로 기록하세요
   - 결정은 아젠다의 결과물(코드)처럼 구체적이고 단일한 결과로 작성하세요 (한 문장 권장)
   - decision.content에는 목적어를 반드시 포함하세요. (예: "A 기능을", "배포 일정을")
   - 주어는 있으면 좋지만 필수는 아닙니다.
3. 결정에는 상태나 승인 정보를 넣지 말고, 결정 내용(content)과 근거/맥락(context)만 기록하세요
4. 행동 항목(Action Item), 제안/아이디어, 단순 의견/질문/가설은 decision으로 만들지 마세요
5. 전체 회의를 3-7문장으로 요약하세요
6. 실시간 L1 토픽 스냅샷은 보조 컨텍스트입니다. 트랜스크립트와 충돌하면 트랜스크립트를 우선하세요.
7. 스냅샷/트랜스크립트에 근거 없는 아젠다나 결정사항은 생성하지 마세요.
8. 각 아젠다와 결정에 evidence 배열을 포함하세요.
   - evidence 항목은 start_utt_id, end_utt_id를 사용합니다.
   - 발화 ID는 트랜스크립트 내 [Utt ...] 표기를 그대로 사용하세요.
   - 트랜스크립트에 없는 발화 ID를 만들지 마세요.
   - 대표 구간(청크 전체 범위)을 근거로 쓰지 마세요.
   - 근거 범위는 가능한 좁게 작성하세요 (권장 1~5개 발화, 최대 10개 발화).
   - 필요하면 start_utt_id == end_utt_id로 단일 발화를 지정하세요.
9. 근거 없는 항목 생성 금지:
   - 근거(evidence)를 제시할 수 없는 agenda는 생성하지 마세요.
   - 근거(evidence)를 제시할 수 없는 decision은 null로 두세요.

중요: 다른 텍스트 없이 오직 JSON만 출력하세요!

{format_instructions}

예시:
{{"summary": "이번 회의에서는 로그인 이슈 해결과 배포 일정에 대해 논의했습니다.", "agendas": [{{"topic": "로그인 실패 원인 정리", "description": "리프레시 토큰 만료 처리 방식 확인", "evidence": [{{"transcript_id": "meeting-transcript", "start_utt_id": "실제_발화_ID_1", "end_utt_id": "실제_발화_ID_3"}}], "decision": {{"content": "만료 시 재로그인 유도 문구를 고정하기", "context": "CS 문의 증가 원인으로 확인됨", "evidence": [{{"transcript_id": "meeting-transcript", "start_utt_id": "실제_발화_ID_2", "end_utt_id": "실제_발화_ID_3"}}]}}}}, {{"topic": "2차 배포 날짜 확정", "description": "테스트 기간을 고려한 일정 조정", "evidence": [{{"transcript_id": "meeting-transcript", "start_utt_id": "실제_발화_ID_5", "end_utt_id": "실제_발화_ID_7"}}], "decision": {{"content": "2차 배포를 3월 31일로 확정", "context": "QA 일정과 리소스를 반영", "evidence": [{{"transcript_id": "meeting-transcript", "start_utt_id": "실제_발화_ID_6", "end_utt_id": "실제_발화_ID_7"}}]}}}}]}}
"""


# =============================================================================
# 최종 요약 정제 프롬프트
# =============================================================================

SUMMARY_REFINEMENT_PROMPT = """당신은 회의록 요약 전문가입니다. 여러 청크에서 추출된 부분 요약들을 하나의 일관된 최종 요약으로 통합하세요.

실시간 L1 토픽 스냅샷 (회의 흐름 참고):
{realtime_topics}

청크별 부분 요약들:
{chunk_summaries}

추출된 아젠다 목록:
{agenda_list}

지침:
1. 부분 요약들의 중복 내용을 제거하고 핵심만 통합하세요
2. 회의 전체 흐름이 자연스럽게 읽히도록 작성하세요
3. 실시간 토픽의 흐름 순서를 참고하여 시간순으로 정리하세요
4. 3-7문장으로 작성하세요
5. 추출된 아젠다와 결정사항을 반영하되, 아젠다 목록을 그대로 나열하지 마세요
6. 구체적인 결정/합의 사항이 있다면 반드시 포함하세요

출력 형식:
- 다른 텍스트 없이 요약 텍스트만 출력하세요
- JSON이 아닌 일반 텍스트로 출력하세요
"""


# =============================================================================
# 청크 아젠다 병합 프롬프트
# =============================================================================

AGENDA_MERGE_PROMPT = """당신은 회의록 정제 전문가입니다. 여러 청크에서 추출된 agenda 목록을 보고, 의미적으로 중복되는 agenda를 병합 그룹으로 묶으세요.

실시간 L1 토픽 스냅샷 (참고):
{realtime_topics}

청크별 agenda 후보 목록(JSON):
{chunk_agendas}

지침:
1. 입력의 각 agenda는 `agenda_id`로 식별됩니다.
2. 의미적으로 같은 논의를 다루는 agenda들은 같은 그룹으로 묶으세요.
3. 서로 다른 논의는 절대 합치지 마세요.
4. 출력의 모든 agenda_id는 입력에서 정확히 하나의 그룹에만 포함되어야 합니다.
5. 근거(evidence)는 이 단계에서 생성/수정하지 마세요. (병합 판단만 수행)
6. 그룹별로 최종 표기용 topic/description/decision 문구를 제안하세요.
7. 결정이 없다면 merged_decision_content를 null로 두세요.
8. source agenda들에 없는 고유명사/날짜/수치/시스템명을 새로 만들지 마세요.
9. merged_decision_content를 만들 때는 목적어를 반드시 포함하고, 확정된 단일 결과만 작성하세요.
10. source agenda들 사이에서 결정이 상충하거나 불명확하면 merged_decision_content를 null로 두세요.

중요: 다른 텍스트 없이 JSON만 출력하세요.

{format_instructions}

예시:
{{
  "merged_agendas": [
    {{
      "source_agenda_ids": ["a0", "a3"],
      "merged_topic": "실시간 번역 기능 도입",
      "merged_description": "실시간 번역/통역 기능의 범위와 도입 방식을 논의",
      "merged_decision_content": "실시간 번역 기능을 1차 범위에 포함하기로 함",
      "merged_decision_context": "사용자 요구 빈도와 구현 난이도를 고려"
    }},
    {{
      "source_agenda_ids": ["a1"],
      "merged_topic": "마이크 버튼 동작 문제",
      "merged_description": "마이크 버튼 입력이 반영되지 않는 이슈 분석",
      "merged_decision_content": null,
      "merged_decision_context": null
    }}
  ]
}}
"""


# Agenda 추출 결과 스키마 (참고용)
AGENDA_EXTRACTION_SCHEMA = {
    "summary": "회의 전체 요약",
    "agendas": [
        {
            "topic": "작고 구체적인 아젠다 주제 (한 가지 핵심)",
            "description": "아젠다 설명 (1문장 권장)",
            "evidence": [
                {
                    "transcript_id": "meeting-transcript",
                    "start_utt_id": "실제_발화_ID_1",
                    "end_utt_id": "실제_발화_ID_3",
                }
            ],
            "decision": {
                "content": "이 회의에서 합의된 결정 내용",
                "context": "결정 맥락/근거/제약",
                "evidence": [
                    {
                        "transcript_id": "meeting-transcript",
                        "start_utt_id": "실제_발화_ID_2",
                        "end_utt_id": "실제_발화_ID_3",
                    }
                ],
            },  # 또는 null
        }
    ],
}
