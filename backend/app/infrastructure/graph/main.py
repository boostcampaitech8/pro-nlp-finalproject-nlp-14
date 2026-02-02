from datetime import datetime

from langchain_core.messages import HumanMessage

from app.infrastructure.graph.orchestration import get_compiled_app


async def main():
    import argparse
    import uuid

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--query", type=str, default=None)
    parser.add_argument("--no-checkpointer", action="store_true", help="Disable checkpointer")
    args, _ = parser.parse_known_args()

    # 컴파일된 앱 로드 (checkpointer 선택적 적용)
    use_checkpointer = not args.no_checkpointer
    app = await get_compiled_app(with_checkpointer=use_checkpointer)

    print("=" * 50)
    if use_checkpointer:
        print("Checkpointer: 활성화 (멀티턴 지원)")
    else:
        print("Checkpointer: 비활성화 (단일 턴)")
    print("종료하려면 'quit', 'exit', 'q' 를 입력하세요")
    print("=" * 50 + "\n")

    run_id = str(uuid.uuid4())
    user_id = "user-1e6382d1"  # 신수효 (샘플 데이터의 실제 사용자)
    thread_id = f"cli-session-{run_id[:8]}"  # CLI 세션용 thread_id
    config = {"configurable": {"thread_id": thread_id}}

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
            print("\n처리 중...\n")

            # ainvoke로 그래프 실행 (checkpointer 사용 시 멀티턴 지원)
            if use_checkpointer:
                await app.ainvoke(initial_state, config)
            else:
                await app.ainvoke(initial_state)

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
