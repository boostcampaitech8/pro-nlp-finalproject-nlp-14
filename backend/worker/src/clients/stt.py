"""Clova Speech gRPC STT 클라이언트"""

import array
import asyncio
import json
import logging
import math
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import grpc
import nest_pb2
import nest_pb2_grpc

from src.config import get_config

logger = logging.getLogger(__name__)


def is_silence(pcm_data: bytes, threshold: float) -> bool:
    """PCM 데이터의 에너지 계산하여 무음 판별

    Args:
        pcm_data: 16-bit PCM 데이터
        threshold: 무음 임계값 (RMS, 0~32768)

    Returns:
        True if silence (RMS < threshold)
    """
    if not pcm_data:
        return True

    # bytes -> int16 배열로 변환
    try:
        samples = array.array("h", pcm_data)  # 'h' = signed short (16-bit)
    except ValueError:
        # 데이터 크기가 홀수인 경우 (비정상)
        return True

    if not samples:
        return True

    # RMS (Root Mean Square) 계산
    sum_squares = sum(s * s for s in samples)
    rms = math.sqrt(sum_squares / len(samples))

    return rms < threshold


@dataclass
class STTSegment:
    """STT 결과 세그먼트"""

    text: str
    start_ms: int
    end_ms: int
    confidence: float
    is_final: bool
    timestamp: datetime


class ClovaSpeechSTTClient:
    """Clova Speech gRPC STT 클라이언트

    실시간 오디오 스트리밍을 gRPC로 Clova Speech에 전송하고
    텍스트 결과를 비동기로 수신
    """

    def __init__(
        self,
        language: str = "ko",
        on_result: Callable[[STTSegment], None] | None = None,
    ):
        """
        Args:
            language: STT 언어 코드 (ko, en, ja, zh)
            on_result: STT 결과 수신 시 호출되는 콜백
        """
        self.config = get_config()
        self.language = language
        self.on_result = on_result

        self._channel: grpc.aio.Channel | None = None
        self._stub: nest_pb2_grpc.NestServiceStub | None = None
        self._audio_queue: asyncio.Queue[tuple[bytes, bool] | None] = asyncio.Queue()
        self._is_running = False
        self._seq_id = 0

        # 전체 텍스트 누적 버퍼 (Clova는 증분 방식으로 결과 반환)
        self._full_text = ""
        self._start_timestamp: int | None = None
        self._end_timestamp: int = 0
        self._confidence_sum = 0.0
        self._confidence_count = 0

    async def connect(self) -> None:
        """gRPC 채널 연결"""
        if self._channel is not None:
            return

        # TLS 보안 채널 생성
        self._channel = grpc.aio.secure_channel(
            self.config.clova_stt_endpoint,
            grpc.ssl_channel_credentials(),
        )
        self._stub = nest_pb2_grpc.NestServiceStub(self._channel)
        logger.info(f"Clova Speech gRPC 연결: {self.config.clova_stt_endpoint}")

    async def disconnect(self) -> None:
        """gRPC 채널 종료"""
        self._is_running = False
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._stub = None
            logger.info("Clova Speech gRPC 연결 종료")

    async def _generate_requests(self) -> AsyncGenerator[nest_pb2.NestRequest, None]:
        """gRPC 요청 생성기

        1. CONFIG 요청 전송 (언어, 키워드 부스팅 설정)
        2. DATA 요청 반복 전송 (오디오 청크)
        """
        # 1. 초기 설정 요청 (키워드 부스팅 포함)
        config_dict: dict = {"transcription": {"language": self.language}}

        # 키워드 부스팅 설정 추가
        if self.config.stt_boost_keywords:
            config_dict["keywordBoosting"] = {
                "boostings": [
                    {
                        "words": self.config.stt_boost_keywords,
                        "weight": self.config.stt_boost_weight,
                    }
                ]
            }

        config_json = json.dumps(config_dict)
        yield nest_pb2.NestRequest(
            type=nest_pb2.RequestType.CONFIG,
            config=nest_pb2.NestConfig(config=config_json),
        )
        logger.debug(f"STT CONFIG 전송: {config_json}")

        # 2. 오디오 데이터 요청 반복
        while self._is_running:
            try:
                # 큐에서 오디오 청크 대기 (타임아웃 100ms)
                item = await asyncio.wait_for(
                    self._audio_queue.get(),
                    timeout=0.1,
                )

                if item is None:
                    # 종료 신호
                    logger.debug("STT 스트림 종료 신호 수신")
                    break

                chunk, is_end_of_speech = item
                extra = json.dumps({"seqId": self._seq_id, "epFlag": is_end_of_speech})
                if is_end_of_speech:
                    logger.info(f"발화 종료 신호 전송: seqId={self._seq_id}")

                yield nest_pb2.NestRequest(
                    type=nest_pb2.RequestType.DATA,
                    data=nest_pb2.NestData(chunk=chunk, extra_contents=extra),
                )
                self._seq_id += 1

            except asyncio.TimeoutError:
                # 큐가 비어있으면 계속 대기
                continue

    def _reset_buffer(self) -> None:
        """텍스트 누적 버퍼 초기화"""
        self._full_text = ""
        self._start_timestamp = None
        self._end_timestamp = 0
        self._confidence_sum = 0.0
        self._confidence_count = 0

    async def _process_responses(self, responses) -> None:
        """gRPC 응답 처리

        Clova Speech는 증분 방식으로 결과 반환:
        - text: 새로 인식된 부분
        - position: 전체 텍스트에서의 위치
        - epFlag=True: 발화 종료, 누적된 전체 텍스트 전송
        """
        try:
            async for response in responses:
                timestamp = datetime.now(timezone.utc)

                try:
                    data = json.loads(response.contents)
                    logger.info(f"STT 응답: {data}")

                    # transcription 결과 파싱
                    if "transcription" in data:
                        trans = data["transcription"]
                        is_final = trans.get("epFlag", False)
                        text = trans.get("text", "")
                        position = trans.get("position", 0)
                        start_ts = trans.get("startTimestamp", 0)
                        end_ts = trans.get("endTimestamp", 0)
                        confidence = trans.get("confidence", 0.0)

                        # 전체 텍스트 구성 (position 기반)
                        if text:
                            # position 위치에 text 삽입/덮어쓰기
                            if position <= len(self._full_text):
                                self._full_text = self._full_text[:position] + text
                            else:
                                self._full_text += text

                            # 타임스탬프 업데이트
                            if self._start_timestamp is None:
                                self._start_timestamp = start_ts
                            self._end_timestamp = max(self._end_timestamp, end_ts)

                            # confidence 평균 계산용
                            if confidence > 0:
                                self._confidence_sum += confidence
                                self._confidence_count += 1

                        logger.debug(
                            f"Transcript: '{text}' pos={position} -> "
                            f"full='{self._full_text}' (epFlag={is_final})"
                        )

                        # 중간 결과도 콜백 전달 (wake word 조기 감지용)
                        if not is_final and text.strip() and self.on_result:
                            segment = STTSegment(
                                text=self._full_text.strip(),
                                start_ms=self._start_timestamp or 0,
                                end_ms=self._end_timestamp,
                                confidence=confidence,
                                is_final=False,
                                timestamp=timestamp,
                            )
                            self.on_result(segment)

                        # epFlag=True: 발화 종료, 누적된 전체 텍스트로 콜백
                        if is_final:
                            if self._full_text.strip() and self.on_result:
                                avg_confidence = (
                                    self._confidence_sum / self._confidence_count
                                    if self._confidence_count > 0
                                    else 0.0
                                )
                                segment = STTSegment(
                                    text=self._full_text.strip(),
                                    start_ms=self._start_timestamp or 0,
                                    end_ms=self._end_timestamp,
                                    confidence=avg_confidence,
                                    is_final=True,
                                    timestamp=timestamp,
                                )
                                self.on_result(segment)

                            # 버퍼 초기화 (다음 발화 준비)
                            self._reset_buffer()

                except json.JSONDecodeError as e:
                    logger.warning(f"STT 응답 JSON 파싱 실패: {e}")

        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC 오류: {e.code()} - {e.details()}")
        except Exception as e:
            logger.exception(f"STT 응답 처리 오류: {e}")

    async def start_streaming(self) -> None:
        """STT 스트리밍 시작"""
        if self._is_running:
            logger.warning("STT 스트리밍이 이미 실행 중")
            return

        await self.connect()

        if self._stub is None:
            raise RuntimeError("gRPC Stub이 초기화되지 않음")

        self._is_running = True
        self._seq_id = 0
        self._reset_buffer()

        # 인증 메타데이터
        metadata = (("authorization", f"Bearer {self.config.clova_stt_secret}"),)

        # 양방향 스트리밍 RPC 호출
        responses = self._stub.recognize(
            self._generate_requests(),
            metadata=metadata,
        )

        # 응답 처리 태스크 시작
        asyncio.create_task(self._process_responses(responses))
        logger.debug("STT 스트리밍 시작")

    async def stop_streaming(self) -> None:
        """STT 스트리밍 종료"""
        if not self._is_running:
            return

        # 종료 신호 전송
        await self._audio_queue.put(None)
        self._is_running = False
        logger.debug("STT 스트리밍 종료")

    async def send_audio(self, audio_data: bytes) -> None:
        """오디오 데이터 전송 (무음 필터링)

        Args:
            audio_data: PCM 오디오 데이터 (16kHz, mono, 16-bit, 100ms 프레임)
        """
        if not self._is_running:
            logger.warning("STT 스트리밍이 시작되지 않음")
            return

        # 무음 필터링
        if is_silence(audio_data, self.config.silence_threshold):
            logger.debug(f"무음 감지, STT 전송 스킵 (RMS < {self.config.silence_threshold})")
            return

        await self._audio_queue.put((audio_data, False))

    async def mark_end_of_speech(self) -> None:
        """발화 종료 표시 (VAD speech_end 시 호출)

        epFlag=true를 전송하여 Clova에 발화 종료를 알림
        """
        if not self._is_running:
            return

        # epFlag=true 전송
        await self._audio_queue.put((b"", True))
        logger.info("발화 종료 마커 큐 추가")
