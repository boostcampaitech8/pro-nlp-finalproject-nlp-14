# MitHub Context Engineering

> 목적: 다자간 실시간 회의에서 AI 에이전트의 컨텍스트 관리 전략을 정의한다.
> 대상: 에이전트 개발자
> 범위: 계층적 메모리 시스템, 실시간 컨텍스트 주입, 에이전트 호출 전략
> 관련 문서: [MitHub Agent Overview](./mithub-agent-overview.md), [MitHub LangGraph Architecture](./mithub-langgraph-architecture.md)

---

## 0. 현재 구현 상태 (2025-01)

### 0.1 구현 완료

| 모듈 | 파일 | 상태 | 설명 |
|------|------|------|------|
| **ContextManager** | `backend/app/infrastructure/context/manager.py` | 완료 | L0/L1 계층적 메모리 관리 |
| **ContextBuilder** | `backend/app/infrastructure/context/builder.py` | 완료 | 호출 유형별 컨텍스트 조합 |
| **TopicDetector** | `backend/app/infrastructure/context/topic_detector.py` | 완료 | 키워드 기반 토픽 전환 감지 |
| **SpeakerContext** | `backend/app/infrastructure/context/speaker_context.py` | 완료 | 화자별 통계 및 역할 추론 |
| **Worker 통합** | `backend/worker/src/main.py` | 완료 | RealtimeWorker에 ContextManager 통합 |
| **테스트 스크립트** | `backend/app/infrastructure/context/run_test.py` | 완료 | 대화형/배치/검증 테스트 |

### 0.2 미구현 (설계만 존재)

| 기능 | 상태 | 설명 |
|------|------|------|
| **LLM 기반 토픽 감지** | Stub | 키워드 기반만 구현, LLM 정밀 감지 미구현 |
| **LLM 기반 요약 생성** | Stub | 요약 텍스트 placeholder, 실제 LLM 호출 미구현 |
| **DB 영속화** | Stub | `_sync_to_db()`, `restore_from_db()` placeholder |
| **재귀적 요약** | 설계됨 | 토픽 내 25턴 초과 시 누적 요약 (아래 섹션 참조) |

---

## 1. First Principles: 회의 컨텍스트의 본질

### 1.1 핵심 질문

컨텍스트 엔지니어링을 설계하기 전, 근본적인 질문에 답해야 한다:

1. **회의에서 "컨텍스트"란 무엇인가?**
   - 발화된 텍스트 그 자체 (transcript)
   - 발화자 간의 관계와 역할
   - 논의 중인 주제의 흐름 (topic flow)
   - 과거 결정사항과의 연관성
   - 암묵적 배경지식 (조직 내 컨텍스트)

2. **에이전트가 언제 컨텍스트를 필요로 하는가?**
   - 실시간 팩트체크 요청 시
   - 과거 결정과 모순 감지 시
   - 요약 요청 시
   - 액션 아이템 추출 시
   - 참여자의 질문에 답변 시

3. **컨텍스트의 유효 수명(TTL)은 얼마인가?**
   - 직전 발화: 수 초 (즉시 반응 필요)
   - 현재 토픽: 수 분 (논의 맥락 유지)
   - 현재 회의: 수 시간 (회의 전체 흐름)
   - 조직 지식: 영구적 (GT 누적)

### 1.2 제약 조건

```
┌─────────────────────────────────────────────────────────────────┐
│                      LLM Context Window                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 기준 모델: HyperCLOVA X (HCX-003) - 8K tokens            │   │
│  │                                                          │   │
│  │ 긴 컨텍스트 = 느린 응답 + 높은 비용 + 정확도 저하        │   │
│  │ "Lost in the Middle" 현상                                │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**토큰 예산 (HCX-003 8K 기준):**
| 용도 | 예산 | 비고 |
|------|------|------|
| 시스템 프롬프트 | ~1,000 | 고정 |
| L0 (최근 발화) | ~3,000 | 최대 25턴 |
| L1 (요약) | ~1,000 | 토픽당 ~200 |
| 응답 여유 | ~3,000 | - |

**핵심 트레이드오프:**
- 많은 컨텍스트 → 풍부한 이해 vs 느린 응답/비용 증가
- 적은 컨텍스트 → 빠른 응답 vs 맥락 손실

**결론:** 모든 transcript를 넣을 수 없다. 선별적 압축이 필수다.

---

## 2. 제안된 계층 메모리 시스템 평가

### 2.1 L0/L1 방법론 개요

| 계층 | 이름 | 내용 | 업데이트 주기 |
|------|------|------|---------------|
| L0 | Active Context | 현재 토픽의 Raw Transcript | 실시간 (발화마다) |
| L1 | Topic History | 완료된 토픽들의 요약 리스트 | 토픽 종료 시 (턴 기반) |

### 2.2 강점 분석

**a) 정보 수명에 따른 자연스러운 분리**
```
시간 축 →
│
│  L0 (Raw)     ████████████░░░░░░░░░░░░░░░░░░░░  (최근 25턴만)
│  L1 (Summary) ░░░░░░░░░░░░████████████████████  (전체 요약)
│
└────────────────────────────────────────────────→ 회의 진행
```

**b) 토큰 효율성**
- L0: ~3,000-5,000 tokens (25턴 × 평균 150 tokens)
- L1: ~500-1,000 tokens (압축된 요약)
- 총합: ~3,500-6,000 tokens (전체 transcript 대비 80% 절약)

**c) 응답 지연 최소화**
- 실시간 질문 시 L0만으로 즉각 응답 가능
- 맥락 필요 시 L1 참조

### 2.3 잠재적 문제점 및 보완

| 문제점 | 원인 | 보완 방안 |
|--------|------|-----------|
| **25턴 경계에서 중요 정보 손실** | 고정된 window size | 토픽 기반 가변 window |
| **15분 업데이트 간 요약 공백** | 고정된 주기 | 토픽 전환 감지 시 즉시 업데이트 |
| **다자간 발화 순서 혼란** | 화자 식별 누락 | 화자별 sub-context 유지 |
| **L1 요약의 정보 손실** | 과도한 압축 | 키워드/엔티티 별도 추출 |

### 2.4 개선된 설계안

```
┌────────────────────────────────────────────────────────────────┐
│             Topic-Segmented Memory Hierarchy                   │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  L0: Active Context (Current Topic)                            │
│  ├── 현재 진행 중인 토픽의 Raw Utterances                      │
│  ├── 토픽 변경 감지 시 L1으로 Flush & Reset                    │
│  └── 최대 N턴 유지 (토픽이 너무 길어질 경우 Chunking)          │
│                                                                │
│  L1: Topic History (Segmented Summaries)                       │
│  ├── List[TopicSegment]                                        │
│  │   ├── Topic A Summary (Token friendly)                      │
│  │   ├── Topic B Summary                                       │
│  │   └── ...                                                   │
│  └── 전체 문맥 파악 용이 (Hierarchical)                        │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 3. 실시간 회의 컨텍스트 엔지니어링

### 3.1 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Real-time Worker                             │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐           │
│  │  LiveKit     │───▶│  STT         │───▶│  Segment     │           │
│  │  Audio       │    │  (Clova)     │    │  Buffer      │           │
│  └──────────────┘    └──────────────┘    └──────┬───────┘           │
│                                                  │                   │
│                                                  ▼                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Context Manager                             │  │
│  │  ┌────────────┐  ┌────────────┐                               │  │
│  │  │    L0      │  │    L1      │                               │  │
│  │  │  Raw Win   │  │  Summary   │                               │  │
│  │  └────────────┘  └────────────┘                               │  │
│  │         │              │                                       │  │
│  │         └──────────────┘                                       │  │
│  │                        ▼                                       │  │
│  │              ┌─────────────────┐                               │  │
│  │              │ Context Builder │                               │  │
│  │              └─────────────────┘                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                 │                                    │
│                                 ▼                                    │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Agent Orchestrator                          │  │
│  │                    (LangGraph)                                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                 │                                    │
│                                 ▼                                    │
│                          Response / TTS                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Context Manager 설계

> **설계 원칙:**
> - **DB가 SSOT**: L0/L1 상태는 DB(PostgreSQL)에 저장하여 워커 재시작/스케일아웃에 대응
> - **인메모리는 캐시**: 성능을 위해 인메모리 캐시 사용, 주기적으로 DB와 동기화
> - **UTC 기준**: 모든 datetime은 timezone-aware (UTC) 사용

```python
# 개념적 구조 (구현 가이드)

from datetime import datetime, timezone

class ContextManager:
    """실시간 회의 컨텍스트 관리자 (Topic-Segmented)

    책임:
    1. STT 수신 및 L0(현재 토픽) 버퍼링
    2. 주기적(N턴)으로 토픽 변경 감지
    3. 토픽 변경 시: 현재 버퍼 요약 -> L1(TopicSegment) 저장 -> 버퍼 초기화
    """

    def __init__(self, meeting_id: str, config: ContextConfig):
        # L0: 현재 진행 중인 토픽의 발화들
        self.l0_buffer: list[Utterance] = []
        self.current_topic: str = "Intro"

        # L1: 완료된 토픽 세그먼트들의 리스트
        self.l1_segments: list[TopicSegment] = []  # 순서 보장 중요

    async def add_utterance(self, utterance: Utterance):
        self.l0_buffer.append(utterance)
        
        # N턴마다 토픽 변경 감지 시도 (예: 5턴)
        if len(self.l0_buffer) % 5 == 0:
            if await self._detect_topic_change():
                await self._segment_and_summarize()
```

### 3.3 L0 -> L1 전환 (Segmentation) 전략

**토픽 변경 감지 시퀀스:**
1. 새로운 발화가 들어올 때마다 L0 버퍼에 누적
2. 매 N턴(예: 5-10턴)마다 Lightweight LLM으로 `Topic Change Check` 수행
3. **Change Detected**:
   - 현재 L0 버퍼의 내용을 요약하여 `TopicSegment` 생성
   - `l1_segments` 리스트에 추가
   - L0 버퍼 비우기 (단, 문맥 연결을 위해 마지막 2-3턴은 남겨둘 수 있음 - Sliding overlap)
   - `current_topic` 업데이트
4. **No Change**:
   - 계속 L0 버퍼에 누적
   - 단, L0 버퍼가 너무 커지면(Max Tokens 초과), 강제로 Chunking 하여 L1으로 보냄 (Hard Limit)

### 3.3.1 재귀적 요약 (Recursive Summarization)

토픽 전환 없이 25턴이 초과되는 경우, **재귀적 요약** 방식으로 정보 손실을 최소화한다.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    재귀적 요약 (Recursive Summarization)                  │
└──────────────────────────────────────────────────────────────────────────┘

  [Turn 1~25]
       │
       ▼
  ┌─────────────────────────────────┐
  │ 첫 번째 요약 생성               │
  │ Summary_1 = summarize(Turn 1~25)│
  └─────────────────────────────────┘
       │
       ▼
  [Turn 26~50]
       │
       ▼
  ┌─────────────────────────────────────────────────────┐
  │ 재귀적 요약                                         │
  │ Summary_2 = summarize(Summary_1 + Turn 26~50)       │
  │                                                     │
  │ 입력:                                               │
  │   - 이전 요약 (Summary_1)                           │
  │   - 새 발화 (Turn 26~50)                            │
  │ 출력:                                               │
  │   - 통합 요약 (Summary_2) <- 기존 세그먼트 업데이트 │
  └─────────────────────────────────────────────────────┘
       │
       ▼
  [Turn 51~75]
       │
       ▼
  ┌─────────────────────────────────────────────────────┐
  │ Summary_3 = summarize(Summary_2 + Turn 51~75)       │
  └─────────────────────────────────────────────────────┘
       │
       ▼
      ...
```

**기존 방식 vs 재귀적 요약 비교:**

| 방식 | 동작 | 장점 | 단점 |
|------|------|------|------|
| **기존** | 25턴마다 독립적인 세그먼트 생성 | 단순 구현 | 같은 토픽에 여러 세그먼트, 맥락 단절 |
| **재귀적** | 이전 요약 + 새 발화를 통합 요약 | 맥락 유지, 세그먼트 수 최소화 | LLM 호출 시 입력 토큰 증가 |

**구현 로직:**

```python
async def _update_l1(self, reason: str) -> None:
    """L1 업데이트 수행 (재귀적 요약 지원)"""

    utterances_to_summarize = self._get_unsummarized_utterances()
    if not utterances_to_summarize:
        return

    # 현재 토픽의 기존 세그먼트 찾기
    existing_segment = self._find_current_topic_segment()

    if reason == "topic_change":
        # 토픽 전환: 새 세그먼트 생성
        segment = self._create_new_segment(utterances_to_summarize)
        self.l1_segments.append(segment)
        self.l0_topic_buffer.clear()

    elif reason in ("turn_limit", "time_limit"):
        if existing_segment:
            # 재귀적 요약: 기존 요약 + 새 발화 -> 통합 요약
            new_summary = await self._recursive_summarize(
                previous_summary=existing_segment.summary,
                new_utterances=utterances_to_summarize,
            )
            existing_segment.summary = new_summary
            existing_segment.end_utterance_id = utterances_to_summarize[-1].id
        else:
            # 첫 요약: 새 세그먼트 생성
            segment = self._create_new_segment(utterances_to_summarize)
            self.l1_segments.append(segment)

    self._last_summarized_utterance_id = utterances_to_summarize[-1].id
```

**재귀적 요약 프롬프트:**

```python
RECURSIVE_SUMMARY_PROMPT = """
기존 요약과 새로운 발화를 통합하여 하나의 요약을 생성하세요.

## 기존 요약
{previous_summary}

## 새로운 발화 (Turn {start}~{end})
{new_utterances}

## 지침
1. 기존 요약의 핵심 내용을 유지하면서 새 정보를 통합
2. 중복 제거 및 정보 압축
3. 시간 순서대로 주요 논의 흐름 유지
4. 토큰 예산: 최대 500 토큰

## 출력 형식 (JSON)
{
    "summary": "통합된 3-5문장 요약",
    "key_points": ["핵심 포인트 (최대 5개)"],
    "keywords": ["키워드 (최대 10개)"]
}
"""
```

### 3.4 토픽 감지 전략

**LLM 기반 토픽 분류:**

```python
TOPIC_DETECTION_PROMPT = """
현재 회의의 최근 발화를 분석하여 토픽 변화를 감지하세요.

## 이전 토픽 요약
{previous_topic_summary}

## 최근 발화 (최근 5턴)
{recent_utterances}

## 분석 기준
1. 주제가 명확히 변경되었는가? (예: "다음 안건으로 넘어가죠")
2. 논의 대상이 바뀌었는가? (예: 프로젝트A → 프로젝트B)
3. 질문/답변이 끝나고 새 질문이 시작되었는가?

## 출력 형식 (JSON)
{
    "topic_changed": true/false,
    "previous_topic": "이전 토픽 이름",
    "current_topic": "현재 토픽 이름",
    "confidence": 0.0~1.0,
    "reason": "판단 근거"
}
"""
```

**키워드 기반 빠른 감지 (LLM 호출 최소화):**

```python
TOPIC_CHANGE_KEYWORDS = [
    "다음 안건", "넘어가", "다른 주제", "그건 그렇고",
    "이제", "다음으로", "마무리하고", "정리하면",
]

async def _quick_topic_change_check(self, utterance: str) -> bool:
    """LLM 호출 없이 빠른 토픽 전환 감지"""
    return any(kw in utterance for kw in TOPIC_CHANGE_KEYWORDS)
```

### 3.5 L1 요약 생성 전략

```python
L1_SUMMARY_PROMPT = """
회의 토픽을 요약하세요.

## 토픽 제목
{topic_name}

## 해당 토픽의 발화 내용
{topic_utterances}

## 요약 형식 (JSON)
{
    "summary": "3-5문장 요약",
    "key_points": ["핵심 포인트 1", "핵심 포인트 2", ...],
    "decisions": ["결정된 사항 (있다면)"],
    "pending": ["보류/미해결 사항 (있다면)"],
    "participants": ["발언한 참여자 목록"],
    "keywords": ["핵심 키워드"]
}
"""
```

---

## 4. 에이전트 호출 시 컨텍스트 주입

### 4.1 호출 유형별 컨텍스트 조합

에이전트가 호출되는 상황에 따라 필요한 컨텍스트가 다르다:

| 호출 유형 | L0 | L1 | 외부 검색 | 설명 |
|-----------|:--:|:--:|:---------:|------|
| **즉시 응답** (팩트체크) | O | △ | O | 최근 발화 + 필요시 검색 |
| **요약 요청** | △ | O | X | L1 기반 + 최근 발화 보완 |
| **액션아이템 추출** | O | O | X | 현재 토픽 전체 필요 |
| **문서 검색** (mit_search) | △ | O | O | 맥락 파악 후 검색 |

### 4.2 Context Builder 설계

```python
class ContextBuilder:
    """에이전트 호출 시 컨텍스트 조합 담당

    호출 유형에 따라 L0/L1을 적절히 조합하여
    OrchestrationState에 주입할 컨텍스트를 생성
    """

    def build_context(
        self,
        call_type: AgentCallType,
        context_manager: ContextManager,
        user_query: str | None = None,
    ) -> AgentContext:
        """호출 유형에 맞는 컨텍스트 조합"""

        match call_type:
            case "IMMEDIATE_RESPONSE":
                return self._build_immediate_context(
                    context_manager, user_query
                )
            case "SUMMARY":
                return self._build_summary_context(context_manager)
            case "ACTION_EXTRACTION":
                return self._build_action_context(context_manager)
            case "SEARCH":
                return self._build_search_context(
                    context_manager, user_query
                )
```

### 4.3 컨텍스트 주입 형식

OrchestrationState에 주입되는 컨텍스트 구조:

```python
class AgentContext(BaseModel):
    """에이전트에 주입되는 컨텍스트 (Topic-Segmented)

    OrchestrationState.messages에 system message로 주입
    """

    # 메타 정보
    meeting_id: str
    current_time: datetime
    call_type: str

    # L0 컨텍스트 (선택적)
    recent_utterances: list[Utterance] | None
    current_topic: str | None

    # L1 컨텍스트 (Topic-Segmented)
    topic_segments: list[TopicSegment] | None  # 완료된 토픽 세그먼트 리스트
    pending_items: list[str] | None

    # 참여자 정보
    participants: list[Participant]
    speaker_roles: dict[str, str]  # user_id -> role
```

### 4.4 System Prompt 주입

```python
def format_context_as_system_prompt(ctx: AgentContext) -> str:
    """AgentContext를 시스템 프롬프트로 변환"""

    parts = [
        "## 현재 회의 정보",
        f"- 회의 ID: {ctx.meeting_id}",
        f"- 현재 시각: {ctx.current_time.isoformat()}",
        f"- 호출 유형: {ctx.call_type}",
        f"- 현재 토픽: {ctx.current_topic or '미정'}",
        "",
    ]

    # 참여자 정보
    if ctx.participants:
        parts.append("## 참여자")
        for p in ctx.participants:
            role = ctx.speaker_roles.get(p.user_id, "")
            role_str = f" ({role})" if role else ""
            parts.append(f"- {p.name}{role_str}")
        parts.append("")

    # L0: 최근 발화
    if ctx.recent_utterances:
        parts.append("## 최근 발화 (L0)")
        for u in ctx.recent_utterances:
            ts = u.absolute_timestamp.strftime("%H:%M:%S")
            parts.append(f"[{ts}] {u.speaker_name}: {u.text}")
        parts.append("")

    # L1: 토픽 세그먼트
    if ctx.topic_segments:
        parts.append("## 토픽별 요약 (L1)")
        for segment in ctx.topic_segments:
            parts.append(f"### {segment.name}")
            parts.append(segment.summary)
            if segment.key_points:
                parts.append(f"- Key Points: {', '.join(segment.key_points)}")
            if segment.key_decisions:
                parts.append(f"- Decisions: {', '.join(segment.key_decisions)}")
            if segment.pending_items:
                parts.append(f"- Pending: {', '.join(segment.pending_items)}")
            if segment.participants:
                parts.append(f"- Participants: {', '.join(segment.participants)}")
            if segment.keywords:
                parts.append(f"- Keywords: {', '.join(segment.keywords)}")
            parts.append("")

    # L1: 미해결 사항
    if ctx.pending_items:
        parts.append("## 미해결 사항")
        for item in ctx.pending_items:
            parts.append(f"- {item}")
        parts.append("")

    return "
".join(parts)
```

---

## 5. 다자간 회의 특수 고려사항

### 5.1 화자 구분 및 역할 추적

다자간 회의에서는 "누가 말했는가"가 중요한 컨텍스트다:

```python
class SpeakerContext:
    """화자별 컨텍스트 관리"""

    def __init__(self):
        # 화자별 발화 버퍼
        self.speaker_buffers: dict[str, deque[Utterance]] = {}

        # 화자 역할 추론
        self.speaker_roles: dict[str, str] = {}

        # 화자간 상호작용 패턴
        self.interaction_matrix: dict[tuple[str, str], int] = {}

    def infer_roles(self) -> dict[str, str]:
        """발화 패턴에서 역할 추론

        - 질문을 많이 하는 사람 → 의사결정자/리더
        - 설명을 많이 하는 사람 → 담당자/전문가
        - 합의를 유도하는 사람 → 퍼실리테이터
        """
        pass
```

### 5.2 발화 어트리뷰션

에이전트 응답 시 발화자를 명확히 구분:

```python
RESPONSE_TEMPLATE = """
## 요청에 대한 분석

{analysis}

## 관련 발화 (출처)
{attributed_quotes}

## 제안
{suggestion}
"""

# 예시 출력:
# ## 관련 발화 (출처)
# - **김철수** (14:32): "예산은 2억으로 확정했습니다"
# - **박영희** (14:35): "그럼 인력은 5명으로 조정해야겠네요"
```

### 5.3 동시 발화 처리

현재 구현에서는 동시 발화를 별도로 그룹화하지 않습니다.  
필요 시 동일 시간대(예: 2초) 발화를 묶는 전처리 레이어를 추가하는 방식으로 확장 가능합니다.

---

## 6. 구현 우선순위 및 로드맵

### Phase 1: 기본 L0/L1 구현 (MVP) - 완료

| 항목 | 설명 | 난이도 | 상태 |
|------|------|--------|------|
| L0 버퍼 구현 | 최근 N턴 발화 유지 | 낮음 | 완료 |
| 턴 기반 L1 트리거 | 25턴마다 요약 생성 | 낮음 | 완료 |
| 기본 요약 프롬프트 | 단순 텍스트 요약 | 중간 | Stub |
| Context Builder MVP | 즉시응답/요약 지원 | 중간 | 완료 |
| Worker 통합 | RealtimeWorker에 ContextManager 연동 | 중간 | 완료 |
| 테스트 스크립트 | 대화형/배치/검증 테스트 | 낮음 | 완료 |

### Phase 2: 토픽 기반 고도화 - 진행중

| 항목 | 설명 | 난이도 | 상태 |
|------|------|--------|------|
| 토픽 감지 (키워드) | 빠른 휴리스틱 감지 | 낮음 | 완료 |
| 토픽 감지 (LLM) | 정확한 토픽 분류 | 중간 | Stub |
| 토픽별 요약 저장 | L1 topic_segments | 중간 | 완료 |
| 재귀적 요약 | 토픽 내 25턴 초과 시 누적 요약 | 중간 | 설계됨 |
| 가변 L0 윈도우 | 토픽 내 전체 발화 유지 | 높음 | 완료 |

### Phase 3: 다자간 최적화 - 부분 완료

| 항목 | 설명 | 난이도 | 상태 |
|------|------|--------|------|
| 화자별 버퍼 | speaker_buffers | 중간 | 완료 |
| 역할 추론 | 발화 패턴 분석 | 높음 | 완료 |
| 어트리뷰션 포맷팅 | 출처 명시 응답 | 낮음 | 미착수 |

---

## 7. 설정 및 튜닝 파라미터

```python
class ContextConfig(BaseSettings):
    """컨텍스트 엔지니어링 설정 (Topic-Segmented)

    주의:
    - 토큰 예산은 HCX-003 (8K) 기준으로 산정
    - 시간 기반 트리거 제거됨, 순수 턴/토픽 기반
    """

    # L0 설정
    l0_max_turns: int = 25              # 최대 턴 수 (HCX-003 8K 기준)
    l0_max_tokens: int = 3000           # 최대 토큰 수 (초과 시 오래된 것부터 제거)
    l0_include_timestamps: bool = True  # 타임스탬프 포함 여부

    # L0 토픽 버퍼 설정 (무한 증식 방지)
    l0_topic_buffer_max_turns: int = 100  # 토픽 내 최대 발화 수
    l0_topic_buffer_max_tokens: int = 10000  # 토픽 내 최대 토큰

    # L1 설정 (Topic-Segmented)
    l1_topic_check_interval_turns: int = 5  # 토픽 전환 체크 주기 (턴 단위)
    l1_summary_max_tokens: int = 500        # 요약 최대 토큰 (HCX-003 기준)

    # LLM 설정 (HCX-003 기준)
    summary_model_name: str = "HCX-007"          # 요약용
    topic_detection_model_name: str = "HCX-003"  # 토픽 감지용

    class Config:
        env_prefix = "CONTEXT_"
```

---

## 8. 모니터링 및 디버깅

### 8.1 메트릭

```python
CONTEXT_METRICS = {
    # L0 메트릭
    "l0_buffer_size": Gauge,           # 현재 버퍼 크기
    "l0_avg_utterance_length": Gauge,  # 평균 발화 길이

    # L1 메트릭
    "l1_update_count": Counter,        # L1 업데이트 횟수
    "l1_topic_count": Gauge,           # 감지된 토픽 수
    "l1_summary_latency": Histogram,   # 요약 생성 지연

    # 에이전트 호출 메트릭
    "agent_call_context_tokens": Histogram,  # 주입된 컨텍스트 토큰 수
    "agent_call_type_count": Counter,        # 호출 유형별 카운트
}
```

### 8.2 디버그 로깅

```python
import structlog

logger = structlog.get_logger(__name__)

async def _segment_and_summarize(self, next_topic_name: str):
    logger.info(
        "l1_segment_created",
        meeting_id=self.meeting_id,
        topic_name=self.current_topic,
        l0_buffer_size=len(self.l0_buffer),
        l1_segments_count=len(self.l1_segments),
        next_topic=next_topic_name,
    )
```

---

## 9. 결론

### 9.1 핵심 설계 원칙

1. **정보 수명에 따른 계층화**: L0(즉시)/L1(세션)
2. **선별적 압축**: 토큰 효율과 정확도의 균형
3. **호출 유형별 최적화**: 필요한 컨텍스트만 주입
4. **토픽 기반 관리**: 고정 윈도우 → 의미 단위 윈도우
5. **화자 어트리뷰션**: 다자간 회의의 본질적 요구

### 9.2 기대 효과

| 지표 | Before | After | 개선 |
|------|--------|-------|------|
| 컨텍스트 토큰 | ~50K | ~5K | 90% 감소 |
| 응답 지연 | 5-10s | 1-3s | 50-70% 감소 |
| API 비용 | 기준 | -80% | 토큰 감소 효과 |
| 맥락 정확도 | 낮음 | 높음 | 토픽 기반 관리 |

### 9.3 관련 문서

- [MitHub Agent Overview](./mithub-agent-overview.md) - 에이전트 전체 비전
- [MitHub LangGraph Architecture](./mithub-langgraph-architecture.md) - 그래프 구조
- [MitHub LangGraph Development Guideline](./mithub-langgraph-development-guideline.md) - 개발 절차

### 9.4 알려진 이슈 및 해결 방안

| 이슈 | 원인 | 해결 방안 | 상태 |
|------|------|-----------|------|
| **SSOT vs 인메모리** | ContextManager가 인메모리로 상태 관리 시 워커 재시작/스케일아웃에서 유실 | DB(PostgreSQL)를 SSOT로, 인메모리는 캐시로만 사용. `restore_from_db()`, `_sync_to_db()` 메서드 추가 | Stub 구현 |
| **컨텍스트 윈도우 불일치** | 문서 내 128K/200K vs HCX-003 8K 혼용 | HCX-003 8K 기준으로 통일, 토큰 예산표 추가 | 해결됨 |
| **L0 토픽 버퍼 무한증식** | `l0_topic_buffer`가 제한 없는 list | `deque(maxlen=100)` 으로 변경 | 구현 완료 |
| **L1 반복 요약** | turn/time 트리거 시 동일 구간 재요약 | `_last_summarized_utterance_id` 추적 필드 추가, `_get_unsummarized_utterances()` 메서드 | 구현 완료 |
| **timezone-naive datetime** | `datetime.now()`와 `datetime.now(timezone.utc)` 혼용 | 모든 datetime을 `datetime.now(timezone.utc)` (UTC aware)로 통일 | 해결됨 |
| **토픽 내 25턴 초과 시 세그먼트 중복** | 토픽 전환 없이 25턴 초과 시 같은 토픽명으로 여러 세그먼트 생성 | 재귀적 요약(Recursive Summarization) 적용: 기존 요약 + 새 발화 -> 통합 요약 (섹션 3.3.1 참조) | 설계됨 |

---

## 10. Implementation Scaffolding

### 10.1 디렉토리 구조

```
backend/app/infrastructure/context/
├── __init__.py              # 모듈 진입점 (public exports)
├── config.py                # ContextConfig 설정
├── models.py                # 데이터 모델 (Utterance, AgentContext 등)
├── manager.py               # ContextManager (L0/L1 관리)
├── builder.py               # ContextBuilder (컨텍스트 조합)
├── topic_detector.py        # TopicDetector (토픽 감지)
├── speaker_context.py       # SpeakerContext (화자별 관리)
└── prompts/
    ├── __init__.py
    ├── topic_detection.py   # 토픽 감지 프롬프트
    └── summarization.py     # L1 요약 프롬프트
```

### 10.2 신규 생성 파일

> [!NOTE]
> 아래 예시는 **핵심 필드만 발췌한 최신 구현 요약**입니다.
> 전체 구현은 `backend/app/infrastructure/context/` 디렉토리의 실제 파일을 참고하세요.

#### 10.2.1 `config.py` - 설정

> **참조:** 현재 구현체: [`backend/app/infrastructure/context/config.py`](../../backend/app/infrastructure/context/config.py)

핵심 설정:
- `l0_max_turns: int = 25` - L0 최대 턴
- `l1_topic_check_interval_turns: int = 5` - 토픽 전환 체크 주기 (턴 단위)
- `l1_summary_max_tokens: int = 500` - 요약 최대 토큰

#### 10.2.2 `models.py` - 데이터 모델

```python
"""Context Engineering Data Models"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Utterance(BaseModel):
    """표준화된 발화 모델 (L0)"""

    id: int
    speaker_id: str
    speaker_name: str
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    absolute_timestamp: datetime
    topic: str | None = None
    topic_id: str | None = None

    model_config = ConfigDict(frozen=True)


class TopicSegment(BaseModel):
    """토픽 세그먼트 (L1)"""

    id: str
    name: str
    summary: str
    start_utterance_id: int
    end_utterance_id: int
    key_points: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    key_decisions: list[str] = Field(default_factory=list)
    pending_items: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)


class Participant(BaseModel):
    """참여자 정보"""

    user_id: str
    name: str
    role: str | None = None


AgentCallType = Literal[
    "IMMEDIATE_RESPONSE",
    "SUMMARY",
    "ACTION_EXTRACTION",
    "SEARCH",
]


class AgentContext(BaseModel):
    """에이전트에 주입되는 통합 컨텍스트"""

    meeting_id: str
    current_time: datetime
    call_type: str

    # L0 컨텍스트
    recent_utterances: list[Utterance] | None = None
    current_topic: str | None = None

    # L1 컨텍스트
    topic_segments: list[TopicSegment] | None = None
    pending_items: list[str] | None = None

    # 참여자 정보
    participants: list[Participant] = Field(default_factory=list)
    speaker_roles: dict[str, str] = Field(default_factory=dict)
```

#### 10.2.3 `manager.py` - ContextManager

```python
"""ContextManager - 실시간 회의 컨텍스트 관리자 (Topic-Segmented)"""

import logging
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone

from app.infrastructure.context.config import ContextConfig
from app.infrastructure.context.models import TopicSegment, Utterance
from app.infrastructure.context.prompts.summarization import (
    L1_SUMMARY_PROMPT,
    RECURSIVE_SUMMARY_PROMPT,
)
from app.infrastructure.context.speaker_context import SpeakerContext, SpeakerStats
from app.infrastructure.context.topic_detector import TopicDetector

logger = logging.getLogger(__name__)

TOPIC_CHANGE_KEYWORDS = ["다음", "안건", "주제 전환", "넘어가죠"]
TOPIC_DETECTION_PROMPT = """토픽 변화를 JSON으로 판단하세요.

## 이전 토픽 요약
{previous_topic_summary}

## 최근 발화
{recent_utterances}
"""


class ContextManager:
    def __init__(self, meeting_id: str, config: ContextConfig | None = None):
        self.meeting_id = meeting_id
        self.config = config or ContextConfig()

        # L0: Raw Window (고정 크기)
        self.l0_buffer: deque[Utterance] = deque(maxlen=self.config.l0_max_turns)
        self.current_topic: str = "Intro"

        # L0: Topic Buffer (현재 토픽 발화, 제한 있음)
        self.l0_topic_buffer: deque[Utterance] = deque(
            maxlen=self.config.l0_topic_buffer_max_turns
        )

        # L1: Topic Segments
        self.l1_segments: list[TopicSegment] = []

        # 업데이트 추적 (UTC 사용)
        self._last_l1_update: datetime = datetime.now(timezone.utc)
        self._turn_count_since_l1: int = 0
        self._last_summarized_utterance_id: int | None = None

        # 토픽 감지/화자 컨텍스트
        self._topic_detector = TopicDetector(config=self.config)
        self._speaker_context = SpeakerContext(
            max_buffer_per_speaker=self.config.speaker_buffer_max_per_speaker
        )

    async def add_utterance(self, utterance: Utterance) -> None:
        """새 발화 추가"""
        utterance_with_topic = utterance.model_copy(update={"topic": self.current_topic})
        self.l0_buffer.append(utterance_with_topic)
        self.l0_topic_buffer.append(utterance_with_topic)
        self._turn_count_since_l1 += 1
        self._speaker_context.add_utterance(utterance_with_topic)

        should_update, reason, next_topic = await self._should_update_l1(
            utterance_with_topic
        )
        if should_update:
            await self._update_l1(reason, next_topic)

    async def _should_update_l1(
        self,
        latest_utterance: Utterance,
    ) -> tuple[bool, str, str | None]:
        """L1 업데이트 필요 여부 판단"""
        new_utterances = self._get_unsummarized_utterances()
        if not new_utterances:
            return False, "", None

        if (
            self._turn_count_since_l1 % self.config.l1_topic_check_interval_turns == 0
            and self._topic_detector.quick_check(latest_utterance.text)
        ):
            result = await self._topic_detector.detect(
                recent_utterances=list(self.l0_buffer)[-5:],
                previous_topic_summary=self._get_current_topic_summary(),
            )
            if result.topic_changed:
                next_topic = result.current_topic or self._generate_next_topic_name()
                return True, "topic_change", next_topic

        if len(new_utterances) >= self.config.l1_update_turn_threshold:
            return True, "turn_limit", None

        elapsed = datetime.now(timezone.utc) - self._last_l1_update
        if elapsed > timedelta(minutes=self.config.l1_update_interval_minutes):
            min_utterances = self.config.l1_min_new_utterances_for_time_trigger
            if len(new_utterances) >= min_utterances:
                return True, "time_limit", None

        return False, "", None

    async def _update_l1(self, reason: str, next_topic: str | None) -> None:
        """L1 업데이트 수행 (재귀적 요약 지원)"""
        utterances_to_summarize = self._get_unsummarized_utterances()
        if not utterances_to_summarize:
            return

        summary = await self._summarize_utterances(
            utterances_to_summarize, L1_SUMMARY_PROMPT
        )
        existing_segment = self._find_current_topic_segment()
        if existing_segment:
            existing_segment.summary = await self._summarize_utterances(
                [existing_segment.summary, summary], RECURSIVE_SUMMARY_PROMPT
            )
            existing_segment.end_utterance_id = utterances_to_summarize[-1].id
        else:
            self.l1_segments.append(
                TopicSegment(
                    id=str(uuid.uuid4()),
                    name=self.current_topic,
                    summary=summary,
                    start_utterance_id=utterances_to_summarize[0].id,
                    end_utterance_id=utterances_to_summarize[-1].id,
                )
            )

        self._last_summarized_utterance_id = utterances_to_summarize[-1].id
        self._last_l1_update = datetime.now(timezone.utc)
        self._turn_count_since_l1 = 0

        if reason == "topic_change":
            self.current_topic = next_topic or self._generate_next_topic_name()
            self.l0_topic_buffer.clear()
            self._last_summarized_utterance_id = None

    def get_l0_utterances(self, limit: int | None = None) -> list[Utterance]:
        utterances = list(self.l0_buffer)
        return utterances[-limit:] if limit else utterances

    def get_topic_utterances(self) -> list[Utterance]:
        return list(self.l0_topic_buffer)

    def get_l1_segments(self) -> list[TopicSegment]:
        return self.l1_segments.copy()
```

#### 10.2.4 `builder.py` - ContextBuilder

```python
"""ContextBuilder - 에이전트 호출 시 컨텍스트 조합"""

from datetime import datetime, timezone

from app.infrastructure.context.manager import ContextManager
from app.infrastructure.context.models import AgentCallType, AgentContext, Participant


class ContextBuilder:
    def build_context(
        self,
        call_type: AgentCallType,
        context_manager: ContextManager,
        user_query: str | None = None,
        participants: list[Participant] | None = None,
    ) -> AgentContext:
        match call_type:
            case "IMMEDIATE_RESPONSE":
                return self._build_immediate_context(
                    context_manager, user_query, participants
                )
            case "SUMMARY":
                return self._build_summary_context(context_manager, participants)
            case "ACTION_EXTRACTION":
                return self._build_action_context(context_manager, participants)
            case "SEARCH":
                return self._build_search_context(
                    context_manager, user_query, participants
                )
            case _:
                return self._build_default_context(context_manager, participants)

    def build_planning_input_context(
        self,
        ctx: ContextManager,
        l0_limit: int = 10,
    ) -> str:
        """Planning 입력용 요약 컨텍스트 (L0 + L1 토픽 목록만)"""
        lines: list[str] = []
        lines.append(f"## 현재 토픽: {ctx.current_topic}")
        lines.append("")

        lines.append("## L0 최근 발화")
        recent = ctx.get_l0_utterances(limit=l0_limit)
        if recent:
            for u in recent:
                ts = u.absolute_timestamp.strftime("%H:%M:%S")
                topic_label = u.topic or ctx.current_topic
                lines.append(f"[{ts}] {u.speaker_name} (topic: {topic_label}): {u.text}")
        else:
            lines.append("- 없음")

        lines.append("")
        lines.append("## L1 토픽 목록")
        segments = ctx.get_l1_segments()
        if segments:
            for seg in segments:
                lines.append(
                    f"- {seg.name} (utterances {seg.start_utterance_id}~{seg.end_utterance_id})"
                )
        else:
            lines.append("- 없음")

        return "\n".join(lines)

    def build_required_topic_context(
        self,
        ctx: ContextManager,
        topic_names: list[str],
    ) -> tuple[str, list[str]]:
        """선택된 토픽의 상세 컨텍스트 (L1 내용)"""
        if not topic_names:
            return "", []

        segment_map = {seg.name: seg for seg in ctx.get_l1_segments()}
        missing = [name for name in topic_names if name not in segment_map]

        lines: list[str] = ["## L1 토픽 상세"]
        added = False
        for name in topic_names:
            segment = segment_map.get(name)
            if not segment:
                continue
            added = True
            lines.append(f"### {segment.name}")
            lines.append(segment.summary)
            if segment.key_points:
                lines.append(f"Key Points: {', '.join(segment.key_points)}")
            if segment.key_decisions:
                lines.append(f"Decisions: {', '.join(segment.key_decisions)}")
            if segment.pending_items:
                lines.append(f"Pending: {', '.join(segment.pending_items)}")
            if segment.participants:
                lines.append(f"Participants: {', '.join(segment.participants)}")
            if segment.keywords:
                lines.append(f"Keywords: {', '.join(segment.keywords)}")
            lines.append("")

        if not added:
            return "", missing

        return "\n".join(lines).strip(), missing

    def _build_immediate_context(
        self,
        ctx: ContextManager,
        user_query: str | None,
        participants: list[Participant] | None,
    ) -> AgentContext:
        return AgentContext(
            meeting_id=ctx.meeting_id,
            current_time=datetime.now(timezone.utc),
            call_type="IMMEDIATE_RESPONSE",
            recent_utterances=ctx.get_l0_utterances(limit=10),
            current_topic=ctx.current_topic,
            topic_segments=None,
            participants=participants or [],
            speaker_roles=ctx.speaker_context.infer_roles(),
        )

    # _build_summary_context / _build_action_context / _build_search_context 생략
```

#### 10.2.5 `topic_detector.py` - TopicDetector

```python
"""TopicDetector - 토픽 변경 감지"""

import json
import logging

from pydantic import BaseModel

from app.core.config import get_settings
from app.infrastructure.context.config import ContextConfig
from app.infrastructure.context.models import Utterance

logger = logging.getLogger(__name__)

TOPIC_CHANGE_KEYWORDS = ["다음", "안건", "주제 전환", "넘어가죠"]
TOPIC_DETECTION_PROMPT = """토픽 변화를 JSON으로 판단하세요."""


class TopicChangeResult(BaseModel):
    topic_changed: bool
    previous_topic: str | None = None
    current_topic: str | None = None
    confidence: float = 0.0
    reason: str = ""


class TopicDetector:
    def __init__(self, config: ContextConfig | None = None):
        self.config = config or ContextConfig()
        self._llm_enabled = bool(get_settings().ncp_clovastudio_api_key)

    def quick_check(self, utterance: str) -> bool:
        return any(kw in utterance for kw in TOPIC_CHANGE_KEYWORDS)

    async def detect(
        self,
        recent_utterances: list[Utterance],
        previous_topic_summary: str = "",
    ) -> TopicChangeResult:
        utterances_text = "\n".join(
            f"[{u.speaker_name}] {u.text}" for u in recent_utterances
        )
        prompt = TOPIC_DETECTION_PROMPT.format(
            previous_topic_summary=previous_topic_summary or "(첫 토픽)",
            recent_utterances=utterances_text,
        )

        if not self._llm_enabled:
            return TopicChangeResult(
                topic_changed=False,
                previous_topic=None,
                current_topic=None,
                confidence=0.0,
                reason="no_change_detected",
            )

        response = await self._call_llm(prompt)
        parsed = self._parse_llm_response(response)
        return parsed or TopicChangeResult(
            topic_changed=False,
            previous_topic=None,
            current_topic=None,
            confidence=0.0,
            reason="parse_error",
        )

    def _parse_llm_response(self, response: str) -> TopicChangeResult | None:
        try:
            data = json.loads(response)
            return TopicChangeResult(
                topic_changed=data.get("topic_changed", False),
                previous_topic=data.get("previous_topic"),
                current_topic=data.get("current_topic"),
                confidence=data.get("confidence", 0.0),
                reason=data.get("reason", ""),
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return None
```

#### 10.2.6 `speaker_context.py` - SpeakerContext

```python
"""SpeakerContext - 화자별 컨텍스트 관리"""

from collections import deque
from typing import Literal

from pydantic import BaseModel

from app.infrastructure.context.models import Utterance


class SpeakerStats(BaseModel):
    user_id: str
    name: str
    utterance_count: int = 0
    question_count: int = 0
    statement_count: int = 0
    total_words: int = 0
    avg_utterance_length: float = 0.0


SpeakerRole = Literal["facilitator", "presenter", "participant", "observer"]


class SpeakerContext:
    def __init__(self, max_buffer_per_speaker: int = 25):
        self.max_buffer = max_buffer_per_speaker
        self.speaker_buffers: dict[str, deque[Utterance]] = {}
        self.speaker_roles: dict[str, SpeakerRole] = {}
        self.interaction_matrix: dict[tuple[str, str], int] = {}
        self.speaker_stats: dict[str, SpeakerStats] = {}
        self._last_speaker_id: str | None = None

    def add_utterance(self, utterance: Utterance) -> None:
        speaker_id = utterance.speaker_id
        if speaker_id not in self.speaker_buffers:
            self.speaker_buffers[speaker_id] = deque(maxlen=self.max_buffer)
            self.speaker_stats[speaker_id] = SpeakerStats(
                user_id=speaker_id,
                name=utterance.speaker_name,
            )

        self.speaker_buffers[speaker_id].append(utterance)
        stats = self.speaker_stats[speaker_id]
        stats.utterance_count += 1
        words = len(utterance.text.split())
        stats.total_words += words
        stats.avg_utterance_length = stats.total_words / stats.utterance_count

        if self._is_question(utterance.text):
            stats.question_count += 1
        else:
            stats.statement_count += 1

        if self._last_speaker_id and self._last_speaker_id != speaker_id:
            key = (self._last_speaker_id, speaker_id)
            self.interaction_matrix[key] = self.interaction_matrix.get(key, 0) + 1

        self._last_speaker_id = speaker_id

    def _is_question(self, text: str) -> bool:
        question_endings = ["?", "까요", "나요", "습니까", "ㅂ니까", "을까", "ㄹ까", "지요", "죠"]
        question_starters = ["어떻게", "왜", "누가", "언제", "어디", "무엇", "뭐", "어느"]

        if "?" in text:
            return True

        for ending in question_endings:
            if text.endswith(ending):
                return True

        for starter in question_starters:
            if text.startswith(starter):
                return True

        return False

    def infer_roles(self) -> dict[str, SpeakerRole]:
        roles: dict[str, SpeakerRole] = {}
        for user_id, stats in self.speaker_stats.items():
            if stats.utterance_count == 0:
                continue

            question_ratio = stats.question_count / stats.utterance_count
            if question_ratio > 0.5:
                roles[user_id] = "facilitator"
            elif stats.avg_utterance_length > 20:
                roles[user_id] = "presenter"
            elif stats.utterance_count < 3:
                roles[user_id] = "observer"
            else:
                roles[user_id] = "participant"

        self.speaker_roles = roles
        return roles
```

#### 10.2.7 `__init__.py` - 모듈 진입점

```python
"""Context Engineering Module

실시간 회의 컨텍스트 관리를 위한 모듈.

계층적 메모리 시스템:
- L0 (Raw Window): 최근 N턴 발화 원본
- L1 (Running Summary): 토픽별 요약 (Topic-Segmented)

사용 예시:
    from app.infrastructure.context import ContextManager, ContextBuilder

    # 회의 시작 시 ContextManager 생성
    ctx_manager = ContextManager(meeting_id="meeting-xxx")

        # 기존 상태 복원 (워커 재시작 대응)
        await ctx_manager.restore_from_db()

        # STT 세그먼트 수신 시
        await ctx_manager.add_utterance(utterance)

        # 에이전트 호출 시
        builder = ContextBuilder()
        context = builder.build_context(
            call_type="IMMEDIATE_RESPONSE",
            context_manager=ctx_manager,
        )
"""

from app.infrastructure.context.config import ContextConfig
from app.infrastructure.context.manager import ContextManager
from app.infrastructure.context.builder import ContextBuilder, format_context_as_system_prompt
from app.infrastructure.context.topic_detector import TopicDetector
from app.infrastructure.context.speaker_context import SpeakerContext
from app.infrastructure.context.models import (
    AgentCallType,
    AgentContext,
    Participant,
    TopicSegment,
    Utterance,
)
from app.infrastructure.context.topic_detector import TopicChangeResult

__all__ = [
    # Config
    "ContextConfig",
    # Core
    "ContextManager",
    "ContextBuilder",
    "format_context_as_system_prompt",
    # Detectors
    "TopicDetector",
    "TopicChangeResult",
    "SpeakerContext",
    "SpeakerStats",
    # Models
    "AgentCallType",
    "AgentContext",
    "Utterance",
    "Participant",
    "TopicSegment",
]
```

### 10.3 실시간 회의 워크플로우

#### 10.3.1 전체 워크플로우 다이어그램

```
                              실시간 회의 워크플로우
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│   [LiveKit Audio]                                                               │
│        │                                                                        │
│        ▼                                                                        │
│   [STT (Clova)]                                                                 │
│        │                                                                        │
│        ▼                                                                        │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │                        RealtimeWorker                                    │  │
│   │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│   │  │  _on_stt_result()                                                 │   │  │
│   │  │     │                                                             │   │  │
│   │  │     ├─▶ Utterance 객체 생성                                       │   │  │
│   │  │     │                                                             │   │  │
│   │  │     ├─▶ ContextManager.add_utterance()  ────────────────────┐    │   │  │
│   │  │     │      │                                                 │    │   │  │
│   │  │     │      ├─▶ L0 Buffer 업데이트                            │    │   │  │
│   │  │     │      ├─▶ SpeakerContext 업데이트                       │    │   │  │
│   │  │     │      ├─▶ 토픽 전환 감지 (_should_update_l1)            │    │   │  │
│   │  │     │      │      │                                          │    │   │  │
│   │  │     │      │      ├─ 키워드 빠른 체크                        │    │   │  │
│   │  │     │      │      ├─ N턴 주기 LLM 감지                       │    │   │  │
│   │  │     │      │      └─ 턴/시간 기반 트리거                     │    │   │  │
│   │  │     │      │                                                 │    │   │  │
│   │  │     │      └─▶ L1 업데이트 (_update_l1)                      │    │   │  │
│   │  │     │             │                                          │    │   │  │
│   │  │     │             ├─ 기존 세그먼트 → 재귀적 요약              │    │   │  │
│   │  │     │             └─ 새 세그먼트 → 토픽 요약 생성             │    │   │  │
│   │  │     │                                                        │    │   │  │
│   │  │     └─▶ Backend API 전송 (TranscriptSegmentRequest)          │    │   │  │
│   │  └──────────────────────────────────────────────────────────────────┘   │  │
│   │                                                                          │  │
│   │  [에이전트 호출 시]                                                      │  │
│   │  일반 호출: ContextBuilder.build_context()                              │  │
│   │     ├─ IMMEDIATE_RESPONSE: L0 (10턴) + SpeakerRoles                     │  │
│   │     ├─ SUMMARY: L1 세그먼트 + L0 (5턴)                                  │  │
│   │     ├─ ACTION_EXTRACTION: 토픽 전체 발화 + L1                           │  │
│   │     └─ SEARCH: L1 + L0 (5턴)                                            │  │
│   │     └─▶ format_context_as_system_prompt()                               │  │
│   │                                                                          │  │
│   │  Orchestration: build_planning_input_context()                           │  │
│   │     └─▶ planning_context → required_topics                               │  │
│   │         build_required_topic_context() → additional_context              │  │
│   └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│                                    │                                            │
│                                    ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │                        Orchestration Graph                               │  │
│   │                                                                          │  │
│   │  [1단계: Planning]                                                       │  │
│   │     planning_context (L0 + L1 토픽 목록) 주입                            │  │
│   │     → required_topics 반환 (추가 컨텍스트 필요 토픽)                     │  │
│   │                                                                          │  │
│   │  [2단계: Answering]                                                      │  │
│   │     additional_context (선택된 토픽 상세) 주입                           │  │
│   │     → 최종 응답 생성                                                     │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 10.3.2 L0/L1 업데이트 시퀀스

```
시퀀스 다이어그램: 발화 추가 시 L0/L1 업데이트 흐름

RealtimeWorker          ContextManager           TopicDetector           SpeakerContext
     │                        │                        │                        │
     │  add_utterance(u)      │                        │                        │
     │───────────────────────▶│                        │                        │
     │                        │                        │                        │
     │                        │  l0_buffer.append(u)   │                        │
     │                        │────────────┐           │                        │
     │                        │            │           │                        │
     │                        │◀───────────┘           │                        │
     │                        │                        │                        │
     │                        │  l0_topic_buffer.append(u)                      │
     │                        │────────────┐           │                        │
     │                        │            │           │                        │
     │                        │◀───────────┘           │                        │
     │                        │                        │                        │
     │                        │  add_utterance(u)      │                        │
     │                        │────────────────────────────────────────────────▶│
     │                        │                        │                        │
     │                        │  _should_update_l1()   │                        │
     │                        │────────────┐           │                        │
     │                        │            │           │                        │
     │                        │            │ quick_check(text)?                 │
     │                        │            │──────────▶│                        │
     │                        │            │           │                        │
     │                        │            │◀──────────│ True/False             │
     │                        │            │           │                        │
     │                        │            │ [if quick_check or N턴 주기]       │
     │                        │            │ detect(utterances)                 │
     │                        │            │──────────▶│                        │
     │                        │            │           │                        │
     │                        │            │◀──────────│ TopicChangeResult      │
     │                        │            │           │                        │
     │                        │◀───────────┘           │                        │
     │                        │                        │                        │
     │                        │  [if should_update]    │                        │
     │                        │  _update_l1(reason)    │                        │
     │                        │────────────┐           │                        │
     │                        │            │           │                        │
     │                        │            │ [topic_change]                     │
     │                        │            │   → 새 TopicSegment 생성           │
     │                        │            │   → l0_topic_buffer.clear()        │
     │                        │            │                                    │
     │                        │            │ [turn_limit]                       │
     │                        │            │   → 기존 세그먼트에 재귀적 요약    │
     │                        │            │                                    │
     │                        │◀───────────┘           │                        │
     │                        │                        │                        │
     │◀───────────────────────│                        │                        │
     │                        │                        │                        │
```

#### 10.3.3 Orchestration Graph 연동 흐름

```python
# 실제 사용 예시: 에이전트 호출 시 2단계 컨텍스트 주입

from app.infrastructure.context import ContextBuilder, ContextManager
from app.infrastructure.graph.orchestration import app
from app.infrastructure.graph.orchestration.nodes.planning import create_plan

builder = ContextBuilder()

async def invoke_agent_with_context(
    manager: ContextManager,
    user_query: str,
) -> str:
    # 1단계: Planning (가벼운 컨텍스트)
    planning_context = builder.build_planning_input_context(manager)
    state = {
        "messages": [HumanMessage(content=user_query)],
        "planning_context": planning_context,
        "retry_count": 0,
    }

    planning_result = create_plan(state)
    required_topics = planning_result.get("required_topics", [])

    # 2단계: Answering (필요한 토픽만 상세)
    additional_context, missing = builder.build_required_topic_context(
        manager,
        required_topics,
    )
    if missing:
        logger.warning(f"Missing required topics: {missing}")

    full_state = {
        **state,
        **planning_result,
        "additional_context": additional_context,
        "skip_planning": True,  # Planning 결과 재사용
    }

    final_state = app.invoke(full_state)
    return final_state.get("response", "")
```

#### 10.3.4 에이전트 호출 유형별 컨텍스트 조합 상세

| 호출 유형 | L0 포함량 | L1 포함량 | 예상 토큰 | 사용 시나리오 |
|-----------|-----------|-----------|-----------|---------------|
| IMMEDIATE_RESPONSE | 10턴 (~1,500) | 없음 | ~1,500 | 팩트체크, 즉시 질문 |
| SUMMARY | 5턴 (~750) | 전체 세그먼트 (~1,000) | ~1,750 | 회의 요약 요청 |
| ACTION_EXTRACTION | 토픽 전체 (~3,000) | 전체 세그먼트 (~1,000) | ~4,000 | 액션아이템 추출 |
| SEARCH | 5턴 (~750) | 전체 세그먼트 (~1,000) | ~1,750 | 문서/과거 회의 검색 |

### 10.4 수정 대상 파일

#### 10.3.1 `backend/worker/src/main.py`

RealtimeWorker에 ContextManager 통합:

```python
# 추가할 import
from app.infrastructure.context import ContextManager, Utterance

class RealtimeWorker:
    def __init__(self, meeting_id: str):
        # ... 기존 코드 ...

        # Context Manager 추가
        self.context_manager = ContextManager(meeting_id=meeting_id)

    async def _on_stt_result(
        self,
        user_id: str,
        participant_name: str,
        segment: STTSegment,
    ) -> None:
        # ... 기존 코드 ...

        # ContextManager에 발화 추가
        utterance = Utterance(
            id=0,  # 자동 할당
            speaker_id=user_id,
            speaker_name=participant_name,
            text=segment.text,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            absolute_timestamp=datetime.now(timezone.utc),
            confidence=segment.confidence,
        )
        await self.context_manager.add_utterance(utterance)
```

#### 10.3.2 `backend/app/infrastructure/graph/orchestration/state.py`

OrchestrationState에 컨텍스트 필드 추가:

```python
# 추가할 필드
class OrchestrationState(TypedDict):
    # ... 기존 필드 ...

    # Context Engineering 필드
    meeting_context: Annotated[str | None, "injected meeting context"]
    call_type: Annotated[str | None, "agent call type"]
```

### 10.4 의존성 추가

`backend/pyproject.toml`에 추가:

```toml
[project]
dependencies = [
    # ... 기존 의존성 ...
    "pydantic-settings>=2.0.0",  # ContextConfig용
]
```

### 10.5 환경변수

`.env.example`에 추가:

```bash
# Context Engineering (HCX-003 8K 기준)
CONTEXT_L0_MAX_TURNS=25
CONTEXT_L0_MAX_TOKENS=3000
CONTEXT_L0_TOPIC_BUFFER_MAX_TURNS=100
CONTEXT_L1_UPDATE_INTERVAL_MINUTES=15
CONTEXT_L1_UPDATE_TURN_THRESHOLD=25
CONTEXT_L1_SUMMARY_MAX_TOKENS=500
CONTEXT_L1_MIN_NEW_UTTERANCES_FOR_TIME_TRIGGER=5
CONTEXT_TOPIC_QUICK_CHECK_ENABLED=true
CONTEXT_SUMMARY_MODEL=HCX-003
CONTEXT_TOPIC_DETECTION_MODEL=HCX-003

# DB 동기화 설정
CONTEXT_DB_SYNC_INTERVAL_SECONDS=5
CONTEXT_DB_SYNC_UTTERANCE_THRESHOLD=10
```
