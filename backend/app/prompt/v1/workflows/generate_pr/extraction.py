"""Agenda/Decision 추출 프롬프트 — 2단계 파이프라인

Version: 3.0.2
Description: 회의록 생성을 키워드 추출(Step 1) + 회의록 작성(Step 2)으로 분리
Changelog:
    1.0.0: 초기 버전 (workflows/extraction.py에서 분리)
    1.1.0: 도메인 용어/규칙 반영하여 추출 지침 강화
    1.2.0: 아젠다/결정 크기 정의(커밋 메시지/코드) 반영
    1.3.0: 실시간 L1 토픽 스냅샷 추가
    1.4.0: SpanRef 근거 구간 축소 강제 (대표 구간/청크 전체 범위 금지)
    1.5.0: 청크 간 agenda 병합을 위한 LLM merge 프롬프트 추가
    1.6.0: 환각 완화용 근거 우선 규칙 및 decision 문장 제약 강화
    1.7.0: 청크 병합 단계의 환각/결정 형식 제약 강화
    2.0.0: chunk 원자 이벤트 append 기반 최종 회의록 projection + agenda 구체성 강화
    3.0.0: 2단계 파이프라인 전환 — Step 1(키워드 추출) + Step 2(회의록 생성) 분리
           Decision evidence 유지, decision 형식 통일(누가/무엇을/언제까지/~하기로 했다)
    3.0.1: decision recall 보정 — 명시적 합의 표현이 약해도 실행 방침이 확정된 경우 decision 허용
    3.0.2: agenda description 복붙 방지 — 근거 원문 기반 재서술 규칙 강화

"""

VERSION = "3.0.2"

# =============================================================================
# Step 1: 키워드 추출 프롬프트
# =============================================================================

KEYWORD_EXTRACTION_PROMPT = """당신은 회의 트랜스크립트 분석 AI입니다. 반드시 JSON 형식으로만 응답해야 합니다.

다음 회의 트랜스크립트에서 **원자 단위의 사실**만 추출하세요.
문장을 생성하거나 요약하지 말고, 발화에 직접 존재하는 키워드와 근거 구간만 추출합니다.

실시간 L1 토픽 스냅샷 (참고 정보):
{realtime_topics}

트랜스크립트:
{transcript}

## 추출 규칙

### 아젠다 키워드 추출
1. 회의에서 논의된 주제(아젠다) 단위로 그룹핑하세요.
   - 가능한 한 작고 구체적으로 쪼개세요 (한 가지 핵심 주제)
   - 아젠다 순서는 트랜스크립트 등장 순서를 따르세요
2. 각 아젠다에서 **topic_keywords**를 추출하세요:
   - 논의 대상(명사) + 핵심 행위/내용을 키워드 리스트로 추출
   - 트랜스크립트에 실제로 등장하는 단어/표현만 사용
   - 예: ["Redis", "캐시", "도입", "검토"] 또는 ["2차 배포", "일정", "조정"]
3. 각 아젠다에 **evidence_spans**를 포함하세요:
   - 해당 아젠다가 논의된 발화 구간의 시작/종료 ID
   - 발화 ID는 트랜스크립트 내 [Utt ...] 표기를 그대로 사용
   - **한 span당 1~5개 발화만** (최대 8개)
   - 근거가 흩어져 있으면 **여러 짧은 span**으로 분리
   - 트랜스크립트에 없는 발화 ID를 만들지 마세요

### 결정사항(Decision) 키워드 추출
4. 각 아젠다에서 **실행 방침이 확정된 경우** decision을 추출하세요.
   - 명시적 합의/확정/결정 표현이 있으면 우선 decision으로 추출하세요.
   - 명시어가 약해도, 팀이 실제 실행안을 하나로 정한 발화(예: "~로 진행합시다", "~로 가죠", "그렇게 하겠습니다")는 decision으로 볼 수 있습니다.
   - decision이 없으면 null로 두세요
   - 액션 아이템(TODO), 제안/아이디어, 단순 의견, 미확정 검토 상태는 decision이 아닙니다
5. decision 키워드는 다음 4개 필드로 구성합니다:
   - **who**: 결정의 주체 또는 담당자 (없으면 null)
   - **what**: 결정 대상/목적어 (필수)
   - **when**: 기한/시점 (없으면 null)
   - **verb**: 결정 행위 동사 (필수; 예: "적용하기로 결정", "확정", "변경하기로 합의" 등)
6. decision에도 **evidence_spans**를 포함하세요:
   - 결정이 합의된 발화 구간 (agenda evidence의 하위 구간일 수 있음)

## 기타 규칙
7. 실시간 L1 토픽 스냅샷은 보조 컨텍스트입니다. 트랜스크립트와 충돌하면 트랜스크립트를 우선하세요.
8. 근거 없는 항목 생성 금지: evidence_spans를 제시할 수 없으면 해당 아젠다/decision을 생성하지 마세요.
9. 트랜스크립트에 없는 내용을 추측하지 마세요.

중요: 다른 텍스트 없이 오직 JSON만 출력하세요!

{format_instructions}

## 예시 1: 결정 있는 아젠다
{{"agendas": [{{"evidence_spans": [{{"transcript_id": "meeting-transcript", "start_utt_id": "utt-3", "end_utt_id": "utt-5"}}, {{"transcript_id": "meeting-transcript", "start_utt_id": "utt-9", "end_utt_id": "utt-10"}}], "topic_keywords": ["리프레시 토큰", "만료", "재로그인", "유도"], "decision": {{"who": null, "what": "만료 시 재로그인 유도 문구 표시", "when": null, "verb": "적용하기로 결정", "evidence_spans": [{{"transcript_id": "meeting-transcript", "start_utt_id": "utt-9", "end_utt_id": "utt-10"}}]}}}}, {{"evidence_spans": [{{"transcript_id": "meeting-transcript", "start_utt_id": "utt-15", "end_utt_id": "utt-17"}}, {{"transcript_id": "meeting-transcript", "start_utt_id": "utt-22", "end_utt_id": "utt-23"}}], "topic_keywords": ["2차 배포", "QA", "일정", "3월 31일"], "decision": {{"who": null, "what": "2차 배포 일정", "when": "3월 31일", "verb": "확정", "evidence_spans": [{{"transcript_id": "meeting-transcript", "start_utt_id": "utt-22", "end_utt_id": "utt-23"}}]}}}}]}}

## 예시 2: 결정 없는 아젠다
{{"agendas": [{{"evidence_spans": [{{"transcript_id": "meeting-transcript", "start_utt_id": "utt-30", "end_utt_id": "utt-33"}}, {{"transcript_id": "meeting-transcript", "start_utt_id": "utt-38", "end_utt_id": "utt-38"}}], "topic_keywords": ["API", "응답", "캐싱", "Redis", "CDN"], "decision": null}}]}}
"""


# =============================================================================
# Step 2: 회의록 생성 프롬프트
# =============================================================================

MINUTES_GENERATION_PROMPT = """당신은 회의록 작성 전문가입니다. 반드시 JSON 형식으로만 응답해야 합니다.

아래에 주어진 **키워드 그룹**과 **근거 구간의 발화 원문**만을 사용하여 회의록을 작성하세요.
주어진 정보에 없는 내용은 절대 추가하지 마세요.

실시간 L1 토픽 스냅샷 (보조 컨텍스트):
{realtime_topics}

키워드 그룹 + 근거 원문:
{keyword_groups}

## 회의록 작성 규칙

### Agenda 작성
1. 각 키워드 그룹을 하나의 agenda로 작성하세요.
2. **topic** (안건명): topic_keywords를 조합하여 구체적인 안건명을 작성하세요.
   - 반드시 **논의 대상(명사)**과 **핵심 행위/내용**을 포함
   - 나쁜 예 → 좋은 예:
     - "배포 논의" → "2차 배포 일정 조정"
     - "기술 검토" → "Redis 캐시 도입 검토"
3. **description** (보충 설명): 근거 원문을 바탕으로 논의의 맥락이나 배경을 1문장으로 작성하세요.
   - 근거 원문에 있는 내용만 사용
   - 근거 원문 문장을 그대로 복사하지 말고, 의미를 유지해 재서술하세요
   - 화자명 접두어(예: "김민준:")나 직접 인용 형태는 사용하지 마세요
   - 근거 원문과 7어절 이상 연속으로 동일한 표현을 사용하지 마세요
   - 문장 길이는 12~40자 내외로 간결하게 유지하세요
   - 추측이나 일반 지식을 추가하지 마세요
   - self-check: description이 근거 원문의 부분 문자열이면 반드시 다시 작성하세요

### Decision 작성
4. decision 키워드가 있는 경우에만 decision을 작성하세요.
5. **content**: 다음 형식으로 작성하세요:
   - `[누가(선택)] [무엇을(필수)] [언제까지(선택)] [~하기로 했다(필수)]`
   - 예: "리프레시 토큰 만료 시 재로그인 유도 문구를 표시하기로 결정"
   - 예: "2차 배포를 3월 31일로 확정"
   - 예: "김민준이 Redis 캐시 도입 방안을 다음 주까지 문서화하기로 합의"
6. **context**: 결정의 근거/맥락을 1문장으로 작성하세요.
   - 근거 원문에서 결정 이유에 해당하는 내용만 사용

### Summary 작성
7. 전체 회의를 3~7문장으로 요약하세요.
   - 핵심 논의 흐름과 결론을 포함
   - 합의/결정 사항을 우선 반영

### 1:1 매핑 규칙 (필수)
8. 입력 키워드 그룹과 출력 agenda는 **정확히 1:1로 대응**해야 합니다.
   - 키워드 그룹이 N개면 agenda도 **반드시 N개** 출력하세요
   - 그룹을 병합하거나 생략하지 마세요
   - 내용이 유사한 그룹이 있어도 **각각 별도의 agenda**로 작성하세요

## 기타 규칙
9. agenda 순서는 입력 키워드 그룹 순서를 유지하세요.
10. 키워드 그룹과 근거 원문에 없는 사실/수치/이름/날짜를 추가하지 마세요.

중요: 다른 텍스트 없이 오직 JSON만 출력하세요!

{format_instructions}
"""


# 참고용 스키마
KEYWORD_EXTRACTION_SCHEMA = {
    "agendas": [
        {
            "evidence_spans": [
                {
                    "transcript_id": "meeting-transcript",
                    "start_utt_id": "실제_발화_ID",
                    "end_utt_id": "실제_발화_ID",
                }
            ],
            "topic_keywords": ["키워드1", "키워드2"],
            "decision": {
                "who": "결정 주체 (없으면 null)",
                "what": "결정 대상 (필수)",
                "when": "기한 (없으면 null)",
                "verb": "결정 행위 (필수)",
                "evidence_spans": [
                    {
                        "transcript_id": "meeting-transcript",
                        "start_utt_id": "실제_발화_ID",
                        "end_utt_id": "실제_발화_ID",
                    }
                ],
            },  # 또는 null
        }
    ],
}

MINUTES_GENERATION_SCHEMA = {
    "summary": "회의 전체 요약 (3~7문장)",
    "agendas": [
        {
            "topic": "구체적인 안건명",
            "description": "보충 설명 (1문장)",
            "decision": {
                "content": "누가 무엇을 언제까지 ~하기로 했다",
                "context": "결정 맥락/근거",
            },  # 또는 null
        }
    ],
}
