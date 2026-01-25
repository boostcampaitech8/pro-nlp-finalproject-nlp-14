from langchain_community.chat_models import ChatClovaX

from app.infrastructure.graph.config import NCP_CLOVASTUDIO_API_KEY

# LLM 객체 생성
llm = ChatClovaX(
    temperature=0.5,
    max_tokens=256,
    model="HCX-003",
    api_key=NCP_CLOVASTUDIO_API_KEY
)
