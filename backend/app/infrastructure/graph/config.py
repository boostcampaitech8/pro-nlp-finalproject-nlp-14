import os

from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

NCP_CLOVASTUDIO_API_KEY = os.getenv("NCP_CLOVASTUDIO_API_KEY")
