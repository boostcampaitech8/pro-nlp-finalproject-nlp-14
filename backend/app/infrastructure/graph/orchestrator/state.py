import datetime
import operator
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

# State 정의
class GraphState(TypedDict):
    run_id : Annotated[str, 'run_id']
    executed_at : Annotated[datetime, 'current_time']
    query : Annotated[str, add_messages]
    user_id : Annotated[str, 'user_id']
    toolcalls : Annotated[bool, 'true or false']
    response : Annotated[str, operator.add]
    plan : Annotated[str, add_messages]
