"""LangGraph 오케스트레이션 설정"""

import os

from dotenv import load_dotenv

load_dotenv()

# LLM API 키
NCP_CLOVASTUDIO_API_KEY = os.getenv("NCP_CLOVASTUDIO_API_KEY")

# Orchestration 설정
MAX_RETRY = 3  # 최대 재시도 횟수
