"""TTS 클라이언트 (MIT-tts-server 연동)"""

import logging

import httpx

from src.config import get_config

logger = logging.getLogger(__name__)


class TTSClient:
    """TTS 서버 호출 클라이언트"""

    def __init__(self) -> None:
        self.config = get_config()
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        """HTTP 클라이언트 초기화 및 연결 확인"""
        if self._client is not None:
            return

        if not self.config.tts_server_url:
            logger.warning("TTS_SERVER_URL 미설정, TTS 비활성화")
            return

        self._client = httpx.AsyncClient(
            base_url=self.config.tts_server_url,
            timeout=httpx.Timeout(
                connect=5.0,
                read=self.config.tts_timeout,
                write=10.0,
                pool=5.0,
            ),
            headers={"Content-Type": "application/json"},
        )
        logger.info("TTS 클라이언트 초기화: %s", self.config.tts_server_url)

        # 시작 시 연결 확인
        is_healthy = await self.health_check()
        if not is_healthy:
            logger.warning(
                "TTS 서버(%s) 연결 실패. TTS 기능이 동작하지 않을 수 있습니다.",
                self.config.tts_server_url,
            )

    async def disconnect(self) -> None:
        """HTTP 클라이언트 종료"""
        if self._client is None:
            return

        await self._client.aclose()
        self._client = None
        logger.info("TTS 클라이언트 종료")

    async def health_check(self) -> bool:
        """TTS 서버 연결 상태 확인"""
        if self._client is None:
            return False

        try:
            response = await self._client.get("/health", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                logger.info("TTS 서버 health check 성공: %s", data)
                return True
            else:
                logger.warning(
                    "TTS 서버 health check 실패: status=%s",
                    response.status_code,
                )
                return False
        except Exception as exc:
            logger.error("TTS 서버 연결 불가: %s", exc)
            return False

    async def synthesize(self, text: str) -> bytes | None:
        """텍스트를 음성으로 변환"""
        if not text.strip():
            return None

        if not self.config.tts_server_url:
            return None

        if self._client is None:
            await self.connect()

        if self._client is None:
            return None

        payload: dict[str, object] = {
            "text": text,
            "voice": self.config.tts_voice,
            "lang": "ko",
            "speed": 1.05,
            "output_format": "pcm",
        }

        path = self.config.tts_synthesize_path

        try:
            logger.debug("TTS 요청: path=%s, payload=%s", path, payload)

            response = await self._client.post(path, json=payload)

            if response.status_code != 200:
                logger.warning(
                    "TTS 요청 실패: path=%s, status=%s, body=%s",
                    path,
                    response.status_code,
                    response.text[:200],
                )
                return None

            # 응답 데이터 검증
            audio_bytes = response.content

            if not audio_bytes:
                logger.warning("TTS 응답이 비어 있음")
                return None

            # 성공 로깅 (응답 헤더의 메타데이터 활용)
            inference_ms = response.headers.get("x-inference-time-ms", "?")
            audio_duration = response.headers.get("x-audio-duration-sec", "?")
            logger.info(
                "TTS 합성 완료: text='%s...', 크기=%d bytes, "
                "추론=%sms, 오디오=%ss",
                text[:30],
                len(audio_bytes),
                inference_ms,
                audio_duration,
            )
            return audio_bytes

        except httpx.ConnectError as exc:
            logger.error(
                "TTS 서버 연결 실패(%s): %s",
                self.config.tts_server_url,
                exc,
            )
            return None
        except httpx.TimeoutException as exc:
            logger.error("TTS 요청 타임아웃: text='%s...', %s", text[:30], exc)
            return None
        except Exception as exc:
            logger.error("TTS 요청 오류: %s", exc, exc_info=True)
            return None
