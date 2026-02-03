import os
from datetime import datetime

from langchain_core.messages import HumanMessage

from app.infrastructure.graph.integration.langfuse import get_runnable_config
from app.infrastructure.graph.orchestration import get_compiled_app
from app.core.config import get_settings
from app.infrastructure.streaming.event_stream_manager import stream_llm_tokens_only


async def main():
    import argparse
    import uuid
    settings = get_settings()

    os.environ['LANGFUSE_PUBLIC_KEY'] = settings.langfuse_public_key
    os.environ['LANGFUSE_SECRET_KEY'] = settings.langfuse_secret_key
    os.environ['LANGFUSE_HOST'] = settings.langfuse_host
    os.environ["LANGFUSE_ENABLED"] = "true" if settings.langfuse_enabled else "false"

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--query", type=str, default=None)
    parser.add_argument("--no-checkpointer", action="store_true", help="Disable checkpointer")
    parser.add_argument("--no-streaming", action="store_true", help="Disable streaming (use ainvoke)")
    args, _ = parser.parse_known_args()

    # 컴파일된 앱 로드 (checkpointer 선택적 적용)
    use_checkpointer = not args.no_checkpointer
    use_streaming = not args.no_streaming
    app = await get_compiled_app(with_checkpointer=use_checkpointer)

    print("\n" + "=" * 60)
    print("🚀 Orchestration Graph CLI")
    print("=" * 60)
    if use_checkpointer:
        print("✅ Checkpointer: 활성화 (멀티턴 지원)")
    else:
        print("⚠️  Checkpointer: 비활성화 (단일 턴)")

    if use_streaming:
        print("✅ Streaming: 활성화 (실시간 토큰 출력)")
    else:
        print("⚠️  Streaming: 비활성화 (완료 후 일괄 출력)")

    print("\n💡 종료하려면 'quit', 'exit', 'q' 를 입력하세요")
    print("=" * 60 + "\n")

    run_id = str(uuid.uuid4())
    user_id = "user-1e6382d1"  # 신수효 (샘플 데이터의 실제 사용자)
    thread_id = f"cli-session-{run_id[:8]}"  # CLI 세션용 thread_id

    single_query = args.query

    while True:
        if single_query:
            user_input = single_query.strip()
        else:
            user_input = input("\n질문: ").strip()

        # 종료 명령어 체크
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n프로그램을 종료합니다.")
            break

        if not user_input:
            print("입력이 비어있습니다. 다시 입력해주세요.")
            if single_query:
                break
            continue

        try:
            # 초기 상태 설정 (새 메시지만 전달, checkpointer가 이전 대화 복원)
            initial_state = {
                "messages": [HumanMessage(content=user_input)],
                "run_id": run_id,
                "user_id": user_id,
                "executed_at": datetime.now(),
                "retry_count": 0,
            }

            # 그래프 실행
            print("\n⚙️  처리 중...\n")

            # config 설정 (checkpointer 및 langfuse)
            config = get_runnable_config(
                trace_name="cli-mit-agent",
                user_id=user_id,
                session_id=run_id,
            )
            if use_checkpointer:
                config["configurable"] = {"thread_id": thread_id}

            if use_streaming:
                # 스트리밍 모드: 실시간 토큰 출력
                print("-" * 60)
                print("📡 응답:\n")

                # 노드 시작 메시지 매핑
                NODE_STATUS_MESSAGES = {
                    "planner": "🧠 계획 수립 중...",
                    "mit_tools": "🔍 데이터 검색 중...",
                    "evaluator": "✅ 결과 평가 중...",
                    "generator": "✍️ 답변 생성 중...",
                }

                token_count = 0
                stream_config = config if use_checkpointer else {}

                async for event in stream_llm_tokens_only(app, initial_state, stream_config):
                    event_type = event.get("type")

                    if event_type == "node_start":
                        node = event.get("node", "")
                        message = NODE_STATUS_MESSAGES.get(node, f"{node} 시작")
                        print(f"\n{message}")

                    elif event_type == "token":
                        token = event.get("content", "")
                        node = event.get("node", "")

                        # 실제 사용자 출력 (generator 노드만 빨간색으로 표시)
                        if node == "generator":
                            print(f"\033[91m{token}\033[0m", end="", flush=True)  # 빨간색
                            token_count += 1
                        else:
                            # 다른 노드들은 회색으로 표시 (디버그용)
                            print(f"\033[90m{token}\033[0m", end="", flush=True)  # 회색

                    elif event_type == "done":
                        print("\n")
                        print("-" * 60)
                        print(f"\n✅ 완료! (사용자 출력 토큰: {token_count}개)")

                    elif event_type == "error":
                        print("\n")
                        print(f"\n❌ 에러: {event.get('error')}")

            else:
                # 비스트리밍 모드: langfuse 설정 사용
                await app.ainvoke(initial_state, config=config)

        except Exception as e:
            print(f"\n실행 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            print("\n다시 시도해주세요.")

        if single_query:
            break


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
