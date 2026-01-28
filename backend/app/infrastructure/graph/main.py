from datetime import datetime

from langchain_core.messages import HumanMessage

from app.infrastructure.graph.orchestration import app

# # 그래프를 PNG 이미지 데이터로 변환
# try:
#     graph_image = app.get_graph().draw_mermaid_png()

#     # 파일로 저장
#     with open("graph.png", "wb") as f:
#         f.write(graph_image)
#     print("성공: 'graph.png' 파일로 저장되었습니다.")

# except Exception as e:
#     print(f"오류 발생: {e}")
#     print("Graphviz 등 시각화 의존성이 설치되어 있는지 확인해주세요.")

async def main():
    import uuid

    print("=" * 50)
    print("종료하려면 'quit', 'exit', 'q' 를 입력하세요")
    print("=" * 50 + "\n")

    # 대화 히스토리를 유지할 메시지 리스트
    messages = []
    run_id = str(uuid.uuid4())
    user_id = "chat_user"

    while True:
        user_input = input("\n질문: ").strip()

        # 종료 명령어 체크
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n프로그램을 종료합니다.")
            break

        if not user_input:
            print("입력이 비어있습니다. 다시 입력해주세요.")
            continue

        try:
            # 사용자 메시지 추가
            messages.append(HumanMessage(content=user_input))

            # 초기 상태 설정
            initial_state = {
                "messages": messages,
                "run_id": run_id,
                "user_id": user_id,
                "executed_at": datetime.now(),
                "retry_count": 0,  # 재시도 카운트 초기화
            }

            # 그래프 실행 (스트리밍)
            print("\n처리 중...")

            final_state = None
            current_response = ""
            in_generator = False

            # astream_events를 사용하여 LLM 토큰 스트리밍
            async for event in app.astream_events(initial_state, version="v2"):
                kind = event["event"]
                name = event.get("name", "")
                tags = event.get("tags", [])

                # 노드 시작 감지 (필요한 이벤트만 처리)
                if kind == "on_chain_start":
                    # Generator 노드만 명시적으로 표시
                    if name == "generator" or "seq:step:4" in tags:
                        in_generator = True
                        print("\n" + "=" * 50)
                        print("답변:")
                        print("=" * 50)

                # LLM 스트리밍 토큰 (응답 출력)
                elif kind == "on_chat_model_stream":
                    # generator 노드에서만 출력
                    if in_generator:
                        chunk = event.get("data", {}).get("chunk", {})
                        if hasattr(chunk, "content"):
                            content = chunk.content
                        else:
                            content = chunk.get("content", "")
                        
                        if content:
                            print(content, end="", flush=True)
                            current_response += content

                # 노드 종료
                elif kind == "on_chain_end":
                    if in_generator and (name == "generator" or "seq:step:4" in tags):
                        print("\n" + "=" * 50)
                        in_generator = False

                    # 최종 그래프 종료 감지
                    if name == "LangGraph":
                        final_state = event.get("data", {}).get("output", {})

            # 최종 상태가 없으면 초기 상태 사용
            if final_state is None:
                final_state = initial_state

            # 메시지 히스토리 업데이트 (응답을 포함하여)
            messages = final_state.get('messages', messages)

        except Exception as e:
            print(f"\n실행 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            print("\n다시 시도해주세요.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
