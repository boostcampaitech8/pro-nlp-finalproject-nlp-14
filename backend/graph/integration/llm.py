import os

from langchain_community.chat_models import ChatClovaX

os.environ["NCP_CLOVASTUDIO_API_KEY"]
os.environ["NCP_APIGW_API_KEY"]
os.environ["NCP_CLOVASTUDIO_APP_ID"]

# LLM 객체 생성
llm = ChatClovaX(
    temperature=0.5,
    max_tokens=256,
    model="HCX-003"
)
