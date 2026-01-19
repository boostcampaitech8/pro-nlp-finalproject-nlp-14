import logging

from orchestrator.state import GraphState

logger = logging.getLogger("AgentLogger")
logger.setLevel(logging.INFO)

# mit_tool node
def mit_tools_response(state: GraphState):
    '''
    Mit Tool 사용 결과 반환하는 노드 (그냥 일단 대충...했다 쳐)
    '''
    logger.info("mit-tool 단계 진입")

    tool_result = '검색 내용 ~~~~~'

    print(f"검색 내용: {tool_result}")

    return {"toolcalls": tool_result}
