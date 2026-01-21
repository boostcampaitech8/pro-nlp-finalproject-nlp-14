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

if __name__ == "__main__":
    import uuid
    from datetime import datetime

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

            # 그래프 실행
            final_state = app.invoke(initial_state)

            # Planning 결과 출력
            plan = final_state.get('plan', '')
            need_tools = final_state.get('need_tools', False)

            if plan:
                print("\n" + "=" * 50)
                print("[Planning 결과]")
                print("=" * 50)
                print(f"계획: {plan}")
                print(f"도구 필요 여부: {'예' if need_tools else '아니오'}")
                print("=" * 50)

            # 최종 응답 출력
            response = final_state.get('response', '응답 없음')
            print("\n" + "=" * 50)
            print("답변:")
            print("=" * 50)
            print(response)
            print("=" * 50)

            # 디버깅용: 평가 정보 출력
            evaluation = final_state.get('evaluation', '')
            evaluation_status = final_state.get('evaluation_status', '')
            evaluation_reason = final_state.get('evaluation_reason', '')

            if evaluation or evaluation_status:
                print("\n" + "=" * 50)
                print("[Evaluator 평가 결과]")
                print("=" * 50)
                if evaluation:
                    print(f"평가 내용: {evaluation}")
                if evaluation_status:
                    print(f"평가 상태: {evaluation_status}")
                if evaluation_reason:
                    print(f"평가 이유: {evaluation_reason}")
                retry_count = final_state.get('retry_count', 0)
                if retry_count > 0:
                    print(f"재시도 횟수: {retry_count}")
                print("=" * 50)

            # 메시지 히스토리 업데이트 (응답을 포함하여)
            messages = final_state.get('messages', messages)

        except Exception as e:
            print(f"\n실행 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            print("\n다시 시도해주세요.")

