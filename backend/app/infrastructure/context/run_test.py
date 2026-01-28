#!/usr/bin/env python3
"""Context Engineering 테스트 스크립트

이 스크립트로 컨텍스트 엔지니어링을 로컬에서 테스트할 수 있습니다.
Worker나 LiveKit 없이 수동으로 발화를 입력하고 L0/L1 상태를 확인합니다.

사용법:
    cd backend
    uv run python -m app.infrastructure.context.run_test

또는:
    cd backend
    python -m app.infrastructure.context.run_test
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, ".")

from langchain_core.messages import HumanMessage

from app.infrastructure.context import (
    ContextBuilder,
    ContextConfig,
    ContextManager,
    Utterance,
    format_context_as_system_prompt,
)
from app.infrastructure.graph.orchestration import app
from app.infrastructure.graph.orchestration.nodes.planning import create_plan


def print_header(title: str) -> None:
    """섹션 헤더 출력"""
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_context_status(manager: ContextManager) -> None:
    """컨텍스트 상태 출력"""
    snapshot = manager.get_context_snapshot()

    print_header("CONTEXT ENGINEERING STATUS")

    # L0 상태
    print()
    print("[L0 - Active Context] (Raw Window)")
    print(f"  Current Topic: {snapshot['current_topic']}")
    print(f"  Buffer Size: {snapshot['l0_buffer_size']} utterances")
    print(f"  Topic Buffer Size: {snapshot['l0_topic_buffer_size']} utterances")

    # L0 최근 발화 표시
    recent = manager.get_l0_utterances(limit=5)
    if recent:
        print("  Recent Utterances:")
        for u in recent:
            ts = u.absolute_timestamp.strftime("%H:%M:%S")
            text_preview = u.text[:50] + "..." if len(u.text) > 50 else u.text
            print(f"    [{ts}] {u.speaker_name}: {text_preview}")

    # L1 상태
    print()
    print("[L1 - Topic History] (Segmented Summaries)")
    print(f"  Segments Count: {snapshot['l1_segments_count']}")

    segments = manager.get_l1_segments()
    if segments:
        print("  Topic Segments:")
        for seg in segments:
            print(f"    - {seg.name}: {seg.summary}")
            if seg.key_points:
                print(f"      Key Points: {', '.join(seg.key_points)}")
            if seg.key_decisions:
                print(f"      Decisions: {', '.join(seg.key_decisions)}")
            if seg.pending_items:
                print(f"      Pending: {', '.join(seg.pending_items)}")
            if seg.participants:
                print(f"      Participants: {', '.join(seg.participants)}")
            if seg.keywords:
                print(f"      Keywords: {', '.join(seg.keywords)}")

    # 화자 정보
    print()
    print("[Speaker Context]")
    speakers = snapshot.get('speakers', [])
    if speakers:
        speaker_ctx = manager.speaker_context
        roles = speaker_ctx.infer_roles()
        for speaker_id in speakers:
            stats = speaker_ctx.get_speaker_stats(speaker_id)
            if stats:
                role = roles.get(speaker_id, "participant")
                print(
                    f"  - {stats.name}: {stats.utterance_count} utterances, "
                    f"role={role}, questions={stats.question_count}"
                )
    else:
        print("  No speakers yet")

    print("=" * 60)


async def invoke_orchestration(
    manager: ContextManager,
    user_query: str,
    label: str = "Orchestration Graph Test",
    debug_context: bool = True,
) -> None:
    """오케스트레이션 그래프 호출 (2단계 컨텍스트 주입)"""
    print_header(label)

    builder = ContextBuilder()
    planning_context = builder.build_planning_input_context(manager)
    messages = [HumanMessage(content=user_query)]

    state = {
        "messages": messages,
        "run_id": str(uuid.uuid4()),
        "user_id": "test_user",
        "executed_at": datetime.now(timezone.utc),
        "retry_count": 0,
        "planning_context": planning_context,
    }

    try:
        planning_result = await create_plan(state)
    except Exception as e:
        print(f"[오류] Planning 실행 실패: {e}")
        return

    required_topics = planning_result.get("required_topics", [])
    if required_topics:
        print(f"추가 컨텍스트 요청 토픽: {', '.join(required_topics)}")
    else:
        print("추가 컨텍스트 요청 토픽: 없음")

    additional_context, missing_topics = builder.build_required_topic_context(
        manager, required_topics
    )
    if missing_topics:
        print(
            "[경고] required_topics 매칭 실패: "
            f"{', '.join(missing_topics)}"
        )

    if debug_context:
        print("\n" + "=" * 50)
        print("[Planning 입력 컨텍스트]")
        print("=" * 50)
        print(planning_context)
        print("=" * 50)
        if additional_context:
            print("\n" + "=" * 50)
            print("[추가 토픽 컨텍스트]")
            print("=" * 50)
            print(additional_context)
            print("=" * 50)
        elif required_topics:
            print("\n" + "=" * 50)
            print("[추가 토픽 컨텍스트]")
            print("=" * 50)
            print("매칭되는 토픽이 없어 추가 컨텍스트를 생성하지 못했습니다.")
            print("=" * 50)

    full_state = {
        **state,
        **planning_result,
        "additional_context": additional_context,
        "skip_planning": True,
    }

    try:
        final_state = await app.ainvoke(full_state)
    except Exception as e:
        print(f"[오류] Orchestration 실행 실패: {e}")
        return

    print("\n" + "=" * 50)
    print("[Planning 결과]")
    print("=" * 50)
    print(f"계획: {final_state.get('plan', '')}")
    print(f"도구 필요 여부: {'예' if final_state.get('need_tools') else '아니오'}")
    print(f"추가 토픽 요청: {final_state.get('required_topics', [])}")

    print("\n" + "=" * 50)
    print("답변:")
    print("=" * 50)
    print(final_state.get("response", "응답 없음"))
    print("=" * 50)


async def run_orchestration_test(manager: ContextManager) -> None:
    """오케스트레이션 그래프 연동 테스트 (2단계 컨텍스트 주입)"""
    user_query = (await asyncio.to_thread(
        input, "에이전트 질문을 입력하세요: "
    )).strip()
    if not user_query:
        print("빈 입력입니다. 기본 질문으로 진행합니다.")
        user_query = "이번 회의에서 결정된 액션 아이템과 담당자를 요약해줘."

    await invoke_orchestration(
        manager,
        user_query,
        label="Orchestration Graph Test",
    )


async def run_interactive_test():
    """대화형 테스트 실행"""
    print_header("Context Engineering Interactive Test")
    print()
    print("컨텍스트 엔지니어링을 대화형으로 테스트합니다.")
    print("발화를 입력하면 L0/L1 상태가 업데이트됩니다.")
    print()
    print("명령어:")
    print("  /status - 현재 컨텍스트 상태 출력")
    print("  /topic <name> - 수동 토픽 전환")
    print("  /speaker <name> - 화자 변경")
    print("  /prompt <type> - 에이전트 프롬프트 출력 (IMMEDIATE_RESPONSE, SUMMARY 등)")
    print("  /quit - 종료")
    print()

    config = ContextConfig(
        l0_max_turns=25,
        l1_topic_check_interval_turns=5,
        l1_update_turn_threshold=10,  # 테스트를 위해 낮게 설정
        topic_quick_check_enabled=True,
    )
    manager = ContextManager(meeting_id="test-meeting", config=config)
    builder = ContextBuilder()

    current_speaker = "User1"
    utterance_id = 0

    print(f"현재 화자: {current_speaker}")
    print()

    while True:
        try:
            user_input = input(f"[{current_speaker}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if not user_input:
            continue

        # 명령어 처리
        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "/quit":
                print("종료합니다.")
                break

            elif cmd == "/status":
                print_context_status(manager)

            elif cmd == "/topic":
                if arg:
                    await manager.force_topic_change(arg)
                    print(f"토픽 변경: {arg}")
                else:
                    print("사용법: /topic <토픽이름>")

            elif cmd == "/speaker":
                if arg:
                    current_speaker = arg
                    print(f"화자 변경: {current_speaker}")
                else:
                    print("사용법: /speaker <화자이름>")

            elif cmd == "/prompt":
                call_type = arg.upper() if arg else "IMMEDIATE_RESPONSE"
                valid_types = ["IMMEDIATE_RESPONSE", "SUMMARY",
                              "ACTION_EXTRACTION", "SEARCH"]
                if call_type not in valid_types:
                    print(f"유효한 타입: {', '.join(valid_types)}")
                else:
                    context = builder.build_context(
                        call_type=call_type,
                        context_manager=manager,
                    )
                    prompt = format_context_as_system_prompt(context)
                    print()
                    print(f"=== Agent Prompt ({call_type}) ===")
                    print(prompt)
                    print("=" * 40)

            else:
                print(f"알 수 없는 명령어: {cmd}")

            continue

        # 발화 추가
        utterance_id += 1
        prev_topic = manager.current_topic
        utterance = Utterance(
            id=utterance_id,
            speaker_id=f"user_{current_speaker.lower()}",
            speaker_name=current_speaker,
            text=user_input,
            start_ms=utterance_id * 1000,
            end_ms=(utterance_id + 1) * 1000,
            confidence=0.95,
            absolute_timestamp=datetime.now(timezone.utc),
        )

        await manager.add_utterance(utterance)
        print(f"  [발화 #{utterance_id} 추가됨]")

        # 토픽 전환 키워드 감지 알림
        # if manager.topic_detector.quick_check(user_input):
        #     print("  [토픽 전환 키워드 감지!]")

        # 토픽 전환 발생 시 알림
        if manager.current_topic != prev_topic:
            print(f"  [토픽 전환] {prev_topic} -> {manager.current_topic}")

        # 5개마다 자동 상태 출력
        if utterance_id % 5 == 0:
            print_context_status(manager)


async def run_batch_test() -> ContextManager:
    """배치 테스트 실행 (미리 정의된 시나리오)"""
    print_header("Context Engineering Batch Test")

    config = ContextConfig(
        l0_max_turns=25,
        l1_update_turn_threshold=25,
        topic_quick_check_enabled=True,
    )
    manager = ContextManager(meeting_id="batch-test", config=config)

    # 테스트 시나리오 (중간중간 에이전트 호출 포함)
    scenario = [
        # [Topic 1: 베타 런칭 피드백]
        {"type": "utterance", "speaker": "민준", "text": "자, 다들 오셨나요? 시간 됐으니 이번 주 위클리 시작할게요."},
        {"type": "utterance", "speaker": "소연", "text": "네, 안녕하세요."},
        {"type": "utterance", "speaker": "지훈", "text": "네, 접속했습니다."},
        {"type": "utterance", "speaker": "혜린", "text": "안녕하세요!"},
        {"type": "utterance", "speaker": "민준", "text": "지난주 월요일에 드디어 사내 베타 오픈했잖아요. 일주일 동안 수집된 피드백 먼저 공유하고 넘어갈게요. 제가 공유해 드린 노션 페이지 보시죠."},
        {"type": "utterance", "speaker": "혜린", "text": "일단 디자인 쪽 피드백 먼저 말씀드려도 될까요?"},
        {"type": "utterance", "speaker": "민준", "text": "네, 혜린 님 먼저 말씀해 주세요."},
        {"type": "utterance", "speaker": "혜린", "text": "전반적으로 UI가 깔끔하다는 평은 많은데, '검색' 버튼이랑 'AI 요약' 버튼 위치가 헷갈린다는 의견이 15건 정도 들어왔어요."},
        {"type": "utterance", "speaker": "지훈", "text": "아, 저도 그거 헷갈리더라고요. 엔터 치면 검색이 되는지 요약이 되는지 모르겠어요."},
        {"type": "utterance", "speaker": "혜린", "text": "맞아요. 지금 검색창 바로 옆에 두 버튼이 나란히 있어서 오클릭이 잦은 것 같아요. 요약 버튼을 아예 결과 창으로 내리는 게 어떨까 싶어요."},
        {"type": "utterance", "speaker": "소연", "text": "결과 창으로 내리면, 검색 결과가 나오기 전에는 요약을 못 하는 건가요?"},
        {"type": "utterance", "speaker": "혜린", "text": "네, 현재 UX 흐름상 검색 결과를 먼저 보고, 그중에서 요약할 문서를 선택하는 게 더 자연스럽다는 피드백이 있었거든요."},
        {"type": "utterance", "speaker": "민준", "text": "일리 있네요. 지금은 전체 DB를 요약하려고 시도하는 유저들이 있어서 토큰 소모도 크잖아요."},
        {"type": "utterance", "speaker": "지훈", "text": "맞습니다. 저번 주에 어떤 분이 '전체 문서 요약해줘'라고 입력해서 서버 타임아웃 났었어요."},
        {"type": "utterance", "speaker": "소연", "text": "아, 그 로그 봤어요. 컨텍스트 윈도우 초과 에러였죠?"},
        {"type": "utterance", "speaker": "지훈", "text": "네, 맞아요. 버튼 분리하는 건 저도 찬성입니다. 백엔드 쪽 수정은 크지 않을 것 같아요."},
        {"type": "utterance", "speaker": "민준", "text": "좋습니다. 그럼 혜린 님이 버튼 위치 수정안 내일 오전까지 공유해 주시면, 이번 스프린트에 반영하시죠."},
        {"type": "utterance", "speaker": "혜린", "text": "네, 알겠습니다. 그리고 '답변 복사' 기능 넣어달라는 요청도 꽤 많았어요."},
        {"type": "utterance", "speaker": "민준", "text": "클립보드 복사 말씀하시는 거죠?"},
        {"type": "utterance", "speaker": "혜린", "text": "네, 생성된 답변을 바로 이메일이나 슬랙에 붙여넣고 싶어 하더라고요."},
        {"type": "utterance", "speaker": "지훈", "text": "그건 프론트엔드 작업만 하면 되니까 금방 할 수 있겠네요."},
        {"type": "utterance", "speaker": "민준", "text": "오케이, 그것도 반영하죠. 기능적인 피드백은 어땠나요?"},
        {"type": "utterance", "speaker": "소연", "text": "제가 로그 분석 좀 해봤는데요, 검색 정확도에 대한 불만은 크게 없는데 '최신 문서' 반영이 느리다는 의견이 있었어요."},
        {"type": "utterance", "speaker": "지훈", "text": "아, 그건 지금 임베딩 파이프라인이 하루에 한 번만 돌아서 그래요. 배치 작업이라서."},
        {"type": "utterance", "speaker": "민준", "text": "실시간성을 요구하는 문서들이 있나 보네요?"},
        {"type": "utterance", "speaker": "소연", "text": "네, 사내 공지사항이나 식단표 같은 건 당일 업데이트가 중요한데, 어제 올라온 글이 검색 안 된다고 리포트가 왔습니다."},
        {"type": "utterance", "speaker": "지훈", "text": "실시간 임베딩으로 바꾸려면 지금 구조를 좀 뜯어고쳐야 하는데... 카프카(Kafka) 도입을 고려해야 할 수도 있어요."},
        {"type": "utterance", "speaker": "민준", "text": "일이 커지겠네요. 일단 지금 당장은 배치 주기를 하루 2회로 늘리는 걸로 임시 대응 가능할까요? 점심시간 즈음에 한 번 더 돌리는 걸로요."},
        {"type": "utterance", "speaker": "지훈", "text": "그 정도는 가능합니다. 오늘 바로 스케줄러 수정해 놓을게요."},
        {"type": "utterance", "speaker": "민준", "text": "네, 감사합니다. 피드백은 이 정도로 정리하고, 다음 안건인 제일 심각한 이슈로 넘어가죠."},
        {"type": "agent_call", "speaker": "민준", "question": "지금까지 UI/피드백 관련 결정사항과 액션 아이템을 요약해줘."},

        # [Topic 2: RAG 검색 속도 이슈]
        {"type": "utterance", "speaker": "민준", "text": "두 번째 안건입니다. 지금 '답변 생성까지 너무 오래 걸린다'는 VOC가 전체의 40%입니다."},
        {"type": "utterance", "speaker": "소연", "text": "네, 저도 써보니까 체감상 5초에서 길면 10초까지 걸리더라고요."},
        {"type": "utterance", "speaker": "혜린", "text": "사용자들은 3초만 넘어가도 멈춘 줄 알고 새로고침을 누르더라고요. 그래서 중복 요청이 들어오는 경우도 봤어요."},
        {"type": "utterance", "speaker": "지훈", "text": "제가 트레이싱(Tracing) 툴로 구간별 속도를 좀 찍어봤거든요? 공유해 드릴게요. 잠시만요."},
        {"type": "utterance", "speaker": "민준", "text": "네, 화면 공유 부탁드려요."},
        {"type": "utterance", "speaker": "지훈", "text": "(화면 공유 중) 여기 보시면, 검색(Retrieval) 자체는 0.5초 내외로 빠른 편이에요. 벡터 DB에서 가져오는 건 문제가 아닙니다."},
        {"type": "utterance", "speaker": "소연", "text": "그럼 생성(Generation) 쪽 병목인가요?"},
        {"type": "utterance", "speaker": "지훈", "text": "네, 맞습니다. 프롬프트 구성하고 LLM API 호출해서 첫 토큰 떨어지기까지(TTFT)가 평균 3초, 완료까지 7초 정도 걸려요."},
        {"type": "utterance", "speaker": "민준", "text": "우리가 지금 모델을 GPT-4o 쓰고 있죠?"},
        {"type": "utterance", "speaker": "소연", "text": "네, 정확도를 최우선으로 하느라 가장 무거운 모델을 쓰고 있어요."},
        {"type": "utterance", "speaker": "민준", "text": "사내 문서 검색용으로 쓰기엔 좀 과한가 싶기도 하고요. 비용 문제도 있고."},
        {"type": "utterance", "speaker": "소연", "text": "사실 단순 요약이나 팩트 체크 정도면 4o-mini나 3.5급으로 낮춰도 충분하긴 해요."},
        {"type": "utterance", "speaker": "지훈", "text": "모델을 바꾸면 속도는 확실히 빨라지나요?"},
        {"type": "utterance", "speaker": "소연", "text": "네, mini 모델 쓰면 속도는 2~3배 빨라질 거고 비용도 1/10 수준으로 줄어들 거예요. 다만 복잡한 추론이 필요한 질문엔 답변 퀄리티가 좀 떨어질 수 있어요."},
        {"type": "utterance", "speaker": "혜린", "text": "사용자 입장에서는 답변이 조금 덜 똑똑해도, 빨리 나오는 게 더 중요할 때가 많아요. 기다리다 지치는 것보단요."},
        {"type": "utterance", "speaker": "민준", "text": "그럼 이렇게 하죠. '하이브리드'로 갈 수 있을까요? 질문 난이도에 라우팅을 한다거나."},
        {"type": "utterance", "speaker": "소연", "text": "라우팅 모델을 하나 더 붙이면 그게 또 레이턴시(지연 시간)가 되어서... 차라리 사용자가 선택하게 하는 건 어때요? '빠른 답변' vs '정밀 답변' 처럼요."},
        {"type": "utterance", "speaker": "혜린", "text": "UI 적으로는 옵션을 줄 수 있긴 한데, 사용자가 그걸 매번 선택하는 게 번거롭지 않을까요?"},
        {"type": "utterance", "speaker": "지훈", "text": "일단 기본값을 가벼운 모델로 바꾸고, 결과가 마음에 안 들면 '재생성(고급 모드)' 버튼을 누르게 하는 건 어때요?"},
        {"type": "utterance", "speaker": "민준", "text": "오, 그거 괜찮네요. 기본 경험은 빠르게 제공하고, 딥한 니즈가 있는 사람만 무거운 모델을 쓰게 하는 거네요."},
        {"type": "utterance", "speaker": "소연", "text": "기술적으로도 그게 깔끔하겠네요. 그럼 제가 이번 주 내로 프롬프트 최적화해서 mini 모델 테스트해 볼게요."},
        {"type": "utterance", "speaker": "지훈", "text": "그리고 또 하나, 검색된 문서(Context)가 너무 많이 들어가는 것도 원인인 것 같아요. 지금 Top-k가 몇 개죠?"},
        {"type": "utterance", "speaker": "소연", "text": "지금 상위 10개 문서(Chunk)를 다 넣고 있어요."},
        {"type": "utterance", "speaker": "지훈", "text": "10개는 좀 많은 것 같은데... 5개로 줄이면 프롬프트 길이가 절반으로 줄잖아요."},
        {"type": "utterance", "speaker": "소연", "text": "5개로 줄이면 정보 누락 가능성이 있어서... 리랭킹(Re-ranking) 과정을 넣으면 어떨까요? 20개 가져와서 리랭커로 5개만 추리는 거죠."},
        {"type": "utterance", "speaker": "민준", "text": "리랭커 돌리면 또 시간 걸리지 않나요?"},
        {"type": "utterance", "speaker": "소연", "text": "리랭커는 가벼운 모델이라 0.1~0.2초면 돼요. 대신 정확도는 훨씬 올라가니까, Top-k를 5개로 줄여도 안심할 수 있죠."},
        {"type": "utterance", "speaker": "지훈", "text": "합리적이네요. 리랭킹 도입해서 인풋 토큰 줄이고, 모델 경량화하고. 이 두 가지면 3초 이내 끊을 수 있을 것 같습니다."},
        {"type": "utterance", "speaker": "혜린", "text": "아, 그리고 로딩 중에 '문서를 분석 중입니다...' 같은 멘트가 롤링되면 체감 대기시간이 줄어들 것 같아요. 지금은 그냥 스피너만 돌잖아요."},
        {"type": "utterance", "speaker": "민준", "text": "좋은 디테일이네요. 스트리밍(Streaming) 처리는 이미 되어 있죠?"},
        {"type": "utterance", "speaker": "지훈", "text": "네, 글자가 타닥타닥 찍히는 건 되어 있는데, 첫 글자 나오기 전까지 흰 화면인 게 문제라서요."},
        {"type": "utterance", "speaker": "혜린", "text": "네, 그 빈 시간(Blank time)을 UI로 채워보겠습니다."},
        {"type": "utterance", "speaker": "민준", "text": "정리할게요. 모델 경량화, 리랭킹 도입, UI 개선. 이거 이번 주에 다 가능할까요?"},
        {"type": "utterance", "speaker": "소연", "text": "모델 테스트랑 리랭킹 구현은 3일 정도면 될 것 같아요."},
        {"type": "utterance", "speaker": "지훈", "text": "백엔드 변경 사항은 크지 않아서 소연 님 작업 끝나면 바로 붙일 수 있습니다."},
        {"type": "utterance", "speaker": "혜린", "text": "UI 문구 추가는 오늘 바로 할게요."},
        {"type": "utterance", "speaker": "민준", "text": "좋습니다. 속도 개선이 이번 주 최우선 과제입니다. 다들 신경 써 주세요. 이제 다음 스프린트 안건으로 넘어가겠습니다."},
        {"type": "agent_call", "speaker": "민준", "question": "속도 이슈에 대한 합의된 해결책과 담당자를 정리해줘."},

        # [Topic 3: 다음 스프린트 우선순위]
        {"type": "utterance", "speaker": "민준", "text": "마지막 안건입니다. 다음 주 스프린트 백로그를 정해야 하는데, 경영지원팀에서 강력하게 요청한 기능이 있어요. 'PDF 파일 업로드 후 채팅' 기능입니다."},
        {"type": "utterance", "speaker": "지훈", "text": "아... 그거 꽤 큰 작업인데요."},
        {"type": "utterance", "speaker": "소연", "text": "지금은 사내 DB에 있는 것만 검색하는데, 사용자가 가진 로컬 파일을 올리게 해달라는 거죠?"},
        {"type": "utterance", "speaker": "민준", "text": "맞아요. 규정집 개정안 같은 거 아직 DB에 안 올라간 파일을 챗봇한테 먹여서 비교하고 싶나 봐요."},
        {"type": "utterance", "speaker": "혜린", "text": "사용자 입장에서는 진짜 필요한 기능이긴 해요. 저한테도 따로 문의하신 분 있었어요."},
        {"type": "utterance", "speaker": "지훈", "text": "기능이 필요한 건 알겠는데, 지금 아키텍처가 DB 검색 중심이라... 파일 업로드하면 그걸 실시간으로 파싱하고 임시 벡터 스토어에 저장하고, 세션 끝나면 날리고... 관리할 게 많아요."},
        {"type": "utterance", "speaker": "민준", "text": "일정상 얼마나 걸릴까요?"},
        {"type": "utterance", "speaker": "지훈", "text": "파일 파싱부터 파이프라인 새로 짜려면 백엔드만 꼬박 1주일 넘게 걸릴 것 같은데요. 프론트도 파일 업로더 만들어야 하고."},
        {"type": "utterance", "speaker": "소연", "text": "PDF 파싱이 은근히 까다로워요. 표나 이미지가 섞여 있으면 텍스트가 다 깨지거든요. OCR(광학 문자 인식) 기술도 좀 필요할 수 있고요."},
        {"type": "utterance", "speaker": "민준", "text": "그럼 이번 스프린트에 바로 넣는 건 무리겠네요?"},
        {"type": "utterance", "speaker": "소연", "text": "네, 지금 속도 이슈 잡는 것도 빠듯해서요. 이거까지 얹으면 이도 저도 안 될 것 같아요."},
        {"type": "utterance", "speaker": "지훈", "text": "저도 반대입니다. 지금 서버 500 에러 간헐적으로 뜨는 것도 잡아야 해요. 이번 주는 '안정화' 주간으로 가야 합니다."},
        {"type": "utterance", "speaker": "민준", "text": "하지만 경영지원팀에서는 다음 주 월요일 임원 회의 때 쓰고 싶다고 하셔서..."},
        {"type": "utterance", "speaker": "혜린", "text": "혹시 '텍스트 붙여넣기'로 타협 보면 안 될까요? PDF 통째로 업로드 말고, 그냥 텍스트 긁어서 입력창에 넣으면 그걸 컨텍스트로 인식하게요."},
        {"type": "utterance", "speaker": "지훈", "text": "오, 프롬프트에 그냥 문맥으로 쑤셔 넣는 방식이요?"},
        {"type": "utterance", "speaker": "혜린", "text": "네, 긴 텍스트 입력받을 수 있게 입력창 글자 수 제한만 좀 풀고요."},
        {"type": "utterance", "speaker": "소연", "text": "그거라면 RAG 파이프라인 안 건드리고, 그냥 프롬프트 엔지니어링으로 처리 가능하니까 훨씬 쉽죠."},
        {"type": "utterance", "speaker": "지훈", "text": "토큰 제한만 안 넘기면 되니까... 입력창에 '이 내용을 바탕으로 대답해'라고 넣는 거랑 똑같잖아요. 구현 난이도 '하'입니다."},
        {"type": "utterance", "speaker": "민준", "text": "그거 좋은 대안이네요. PDF 업로드 기능은 '준비 중'이라고 하고, 일단 텍스트 붙여넣기로 가이드하죠. 긴 텍스트 입력 UI만 좀 다듬어 주시면 될까요?"},
        {"type": "utterance", "speaker": "혜린", "text": "네, 입력창 확장되는 UI로 잡으면 될 것 같아요."},
        {"type": "utterance", "speaker": "소연", "text": "대신 사용자가 너무 긴 글을 넣으면 '너무 깁니다'라고 잘라주는 로직은 필요해요. 모델 컨텍스트 리밋이 있으니까요."},
        {"type": "utterance", "speaker": "지훈", "text": "그건 제가 API 단에서 예외 처리해 놓겠습니다."},
        {"type": "utterance", "speaker": "민준", "text": "그럼 정리가 된 것 같네요. 이번 스프린트 목표는 속도 개선, 배치 주기 변경, 텍스트 대량 입력 지원입니다."},
        {"type": "utterance", "speaker": "지훈", "text": "깔끔하네요."},
        {"type": "utterance", "speaker": "소연", "text": "네, 알겠습니다. 리랭킹 모델은 제가 오늘 오후에 선정해서 슬랙으로 공유드릴게요."},
        {"type": "utterance", "speaker": "민준", "text": "혜린 님은 버튼 위치 변경이랑 로딩 멘트, 입력창 UI 시안 오늘 중으로 가능할까요?"},
        {"type": "utterance", "speaker": "혜린", "text": "네, 버튼 위치는 바로 수정해서 제플린에 올릴게요."},
        {"type": "utterance", "speaker": "민준", "text": "지훈 님은 서버 로그 계속 모니터링 부탁드리고요. 아까 500 에러 원인 파악되면 공유 부탁드립니다."},
        {"type": "utterance", "speaker": "지훈", "text": "네, 알겠습니다. 아마 DB 커넥션 풀 문제 같은데 확인해 볼게요."},
        {"type": "utterance", "speaker": "민준", "text": "추가로 논의할 거 있나요?"},
        {"type": "utterance", "speaker": "소연", "text": "아, 저 휴가 일정 공유드려도 될까요? 다음 주 금요일 연차입니다."},
        {"type": "utterance", "speaker": "민준", "text": "아, 네. 캘린더에 등록해 주세요. 일정 짤 때 참고할게요."},
        {"type": "utterance", "speaker": "지훈", "text": "저도 다다음 주 예비군이라 미리 말씀드립니다."},
        {"type": "utterance", "speaker": "민준", "text": "네, 다들 고생 많으셨습니다. 이번 주도 파이팅하시죠!"},
        {"type": "utterance", "speaker": "모두", "text": "수고하셨습니다!"},
        {"type": "agent_call", "speaker": "민준", "question": "PDF 업로드 대체안과 다음 스프린트 우선순위를 요약해줘."},
        {"type": "agent_call", "speaker": "민준", "question": "전체 회의의 핵심 결정사항과 액션 아이템을 정리해줘."},
    ]

    print("테스트 발화 입력 시작...")
    print()

    utterance_id = 0
    agent_call_id = 0

    for item in scenario:
        if item["type"] == "utterance":
            utterance_id += 1
            speaker = item["speaker"]
            text = item["text"]
            utterance = Utterance(
                id=utterance_id,
                speaker_id=f"user_{speaker}",
                speaker_name=speaker,
                text=text,
                start_ms=utterance_id * 3000,
                end_ms=(utterance_id + 1) * 3000 - 500,
                confidence=0.95,
                absolute_timestamp=datetime.now(timezone.utc),
            )

            print(f"[{utterance_id:2d}] {speaker}: {text}")
            await manager.add_utterance(utterance)

            # 토픽 전환 키워드 감지 알림
            if manager.topic_detector.quick_check(text):
                print("      ^ 토픽 전환 키워드 감지!")

            await asyncio.sleep(0.1)  # 약간의 딜레이
            continue

        if item["type"] == "agent_call":
            agent_call_id += 1
            speaker = item.get("speaker", "Unknown")
            question = item["question"]

            # 참가자의 질문을 발화로 추가
            utterance_id += 1
            utterance = Utterance(
                id=utterance_id,
                speaker_id=f"user_{speaker}",
                speaker_name=speaker,
                text=question,
                start_ms=utterance_id * 3000,
                end_ms=(utterance_id + 1) * 3000 - 500,
                confidence=0.95,
                absolute_timestamp=datetime.now(timezone.utc),
            )

            print(f"[{utterance_id:2d}] {speaker} (질문): {question}")
            await manager.add_utterance(utterance)

            await invoke_orchestration(
                manager,
                question,
                label=f"Agent Call #{agent_call_id} ({speaker})",
            )
            continue

    print()
    print_context_status(manager)

    # 에이전트 프롬프트 출력
    builder = ContextBuilder()
    print()
    print_header("Generated Agent Prompt (SUMMARY)")
    context = builder.build_context(
        call_type="SUMMARY",
        context_manager=manager,
    )
    prompt = format_context_as_system_prompt(context)
    print(prompt)

    return manager


async def run_verification():
    """검증 테스트 (기본 기능 확인)"""
    print_header("Context Engineering Verification Test")

    # 1. Initialize Manager
    manager = ContextManager(meeting_id="test-meeting-verification")
    print(f"L0 Max Turns: {manager.config.l0_max_turns}")
    assert manager.config.l0_max_turns == 25, "L0 max turns should be 25"

    # 2. Test L0 Buffer & Segmentation Logic
    print("Testing L0 buffer & Segmentation...")

    # Add 25 utterances
    for i in range(25):
        u = Utterance(
            id=i,
            speaker_id="user1",
            speaker_name="Tester",
            text=f"Test message {i}",
            start_ms=i * 1000,
            end_ms=(i + 1) * 1000,
            confidence=0.9,
            absolute_timestamp=datetime.now(timezone.utc),
        )
        await manager.add_utterance(u)

    # Check if segmentation happened
    print(f"L0 Buffer Size: {len(manager.l0_buffer)}")
    print(f"L0 Topic Buffer Size: {len(manager.l0_topic_buffer)}")
    print(f"L1 Segments: {len(manager.l1_segments)}")

    # L0 buffer는 sliding window (deque maxlen=25)이므로 비워지지 않음
    # L1 업데이트는 turn_limit(25턴) 도달 시 발생
    assert len(manager.l1_segments) >= 1, "Should have created at least 1 segment"
    assert len(manager.l0_buffer) == 25, "L0 buffer is a sliding window, keeps last 25"
    assert manager.l1_segments[0].name == "Intro", "First segment should be Intro"

    # 3. Test Context Builder
    print("Testing Context Builder with Segments...")
    builder = ContextBuilder()

    ctx = builder.build_context("IMMEDIATE_RESPONSE", manager)
    print(f"Context Segments: {len(ctx.topic_segments) if ctx.topic_segments else 0}")

    print()
    print("Verification passed!")


async def run_batch_with_orchestration():
    """배치 테스트 후 오케스트레이션 연동 테스트 실행"""
    manager = await run_batch_test()
    await run_orchestration_test(manager)


def main():
    """메인 함수"""
    print()
    print("Context Engineering Test")
    print("========================")
    print()
    print("테스트 모드를 선택하세요:")
    print("  1. 대화형 테스트 (직접 발화 입력)")
    print("  2. 배치 테스트 (미리 정의된 시나리오)")
    print("  3. 검증 테스트 (기본 기능 확인)")
    print("  4. 오케스트레이션 연동 테스트 (배치 시나리오 + 그래프)")
    print()

    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        try:
            choice = input("선택 (1/2/3/4): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            return

    if choice == "1":
        asyncio.run(run_interactive_test())
    elif choice == "2":
        asyncio.run(run_batch_test())
    elif choice == "3":
        asyncio.run(run_verification())
    elif choice == "4":
        asyncio.run(run_batch_with_orchestration())
    else:
        print("1, 2, 3 또는 4를 선택해주세요.")


if __name__ == "__main__":
    main()
