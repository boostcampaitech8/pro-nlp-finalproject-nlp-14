from datetime import datetime

from app.infrastructure.graph.orchestrator import app

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

    user_input = input("질문을 입력하세요.")

    if user_input.strip():
        try:
            # 2. 초기 상태 설정
            initial_state = {
                "query": user_input,
                "run_id": str(uuid.uuid4()),
                "user_id": "single_run_user",
                "executed_at": datetime.now(),
            }

            # 3. 그래프 실행 (로그가 출력됨)
            # invoke가 끝나면 final_state에 결과가 담기고, 바로 다음 줄로 넘어갑니다.
            final_state = app.invoke(initial_state)

            # 4. 최종 응답 출력
            print("\n" + "-"*30)
            print(f"{final_state['response']}")
            print("-"*30 + "\n")
        except Exception as e:
            print(f"실행 중 오류 발생: {e}")
    else:
        print("입력된 내용이 없어 프로그램을 종료합니다.")

    print("프로그램이 종료되었습니다.")
