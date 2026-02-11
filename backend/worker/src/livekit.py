"""LiveKit Bot - 회의 참여, 오디오 구독 및 AI 에이전트 기능"""

import asyncio
import logging
from array import array
from dataclasses import dataclass, field
from typing import Callable

from livekit import api, rtc
from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class ParticipantAudio:
    """참여자 오디오 정보"""

    participant_id: str
    participant_name: str
    user_id: str  # 실제 사용자 ID (메타데이터에서 추출)
    track: rtc.RemoteAudioTrack | None = None
    audio_stream: rtc.AudioStream | None = None


@dataclass
class LiveKitBotContext:
    """LiveKit Bot 컨텍스트"""

    room: rtc.Room | None = None
    meeting_id: str = ""
    participants: dict[str, ParticipantAudio] = field(default_factory=dict)
    is_connected: bool = False


class LiveKitBot:
    """LiveKit 회의 참여 Bot

    회의에 Bot으로 참여하여:
    1. 모든 참여자의 오디오를 구독하고 PCM 데이터를 STT로 전달
    2. (향후) RAG 기반 응답을 TTS로 변환하여 회의실에 발화
    """

    def __init__(
        self,
        meeting_id: str,
        on_audio_frame: Callable[[str, str, bytes], None] | None = None,
        on_participant_joined: Callable[[str, str], None] | None = None,
        on_participant_left: Callable[[str], None] | None = None,
        on_vad_event: Callable[[str, str, dict], None] | None = None,
        enable_tts_publish: bool = False,
    ):
        """
        Args:
            meeting_id: 회의 ID (LiveKit room name)
            on_audio_frame: 오디오 프레임 수신 콜백 (user_id, participant_name, pcm_data)
            on_participant_joined: 참여자 입장 콜백 (user_id, participant_name)
            on_participant_left: 참여자 퇴장 콜백 (user_id)
            on_vad_event: VAD 이벤트 수신 콜백 (user_id, event_type, payload)
        """
        self.config = get_config()
        self.meeting_id = meeting_id
        self.on_audio_frame = on_audio_frame
        self.on_participant_joined = on_participant_joined
        self.on_participant_left = on_participant_left
        self.on_vad_event = on_vad_event
        self._enable_tts_publish = enable_tts_publish

        self._ctx = LiveKitBotContext(meeting_id=meeting_id)
        self._audio_tasks: dict[str, asyncio.Task] = {}
        self._tts_source: rtc.AudioSource | None = None
        self._tts_track: rtc.LocalAudioTrack | None = None
        self._tts_publish_lock = asyncio.Lock()
        self._tts_volume_scale = self.config.tts_volume_scale

        if self._tts_volume_scale != 1.0:
            logger.info("TTS 볼륨 스케일 적용: %.2f", self._tts_volume_scale)

    async def _create_token(self) -> str:
        """LiveKit 접근 토큰 생성"""
        token = api.AccessToken(
            self.config.livekit_api_key,
            self.config.livekit_api_secret,
        )
        token.with_identity(f"mit-agent-{self.meeting_id}")
        token.with_name("부덕이")
        token.with_grants(
            api.VideoGrants(
                room_join=True,
                room=self.meeting_id,
                can_subscribe=True,
                can_publish=self._enable_tts_publish,
                can_publish_data=True,
            )
        )
        return token.to_jwt()

    async def connect(self) -> None:
        """회의 참여"""
        if self._ctx.is_connected:
            logger.warning("이미 회의에 연결됨")
            return

        # Room 생성 및 이벤트 핸들러 등록
        self._ctx.room = rtc.Room()
        self._ctx.room.on("participant_connected", self._on_participant_connected)
        self._ctx.room.on("participant_disconnected", self._on_participant_disconnected)
        self._ctx.room.on("track_subscribed", self._on_track_subscribed)
        self._ctx.room.on("track_unsubscribed", self._on_track_unsubscribed)
        self._ctx.room.on("disconnected", self._on_disconnected)
        self._ctx.room.on("data_received", self._on_data_received)

        # (추가) auto_subscribe=False 환경에서, 필요한 트랙(마이크 오디오)만 수동 구독
        self._ctx.room.on("track_published", self._on_track_published)

        # 토큰 생성 및 연결
        token = await self._create_token()
        await self._ctx.room.connect(
            self.config.livekit_ws_url,
            token,
            rtc.RoomOptions(auto_subscribe=False),
        )

        self._ctx.is_connected = True
        logger.info(f"LiveKit 회의 참여: {self.meeting_id}")

        # (추가) 이미 참여 중인 참여자의 기존 트랙도 마이크 오디오만 구독
        for participant in self._ctx.room.remote_participants.values():
            for publication in participant.track_publications.values():
                self._subscribe_publication_if_needed(publication)

        # 이미 참여 중인 참여자 처리
        for participant in self._ctx.room.remote_participants.values():
            await self._handle_participant_joined(participant)

    async def disconnect(self) -> None:
        """회의 퇴장"""
        if not self._ctx.is_connected:
            return

        # 오디오 스트림 태스크 취소
        for task in self._audio_tasks.values():
            task.cancel()
        self._audio_tasks.clear()

        # Room 연결 해제
        if self._ctx.room:
            await self._ctx.room.disconnect()
            self._ctx.room = None

        self._ctx.is_connected = False
        self._ctx.participants.clear()
        logger.info(f"LiveKit 회의 퇴장: {self.meeting_id}")

    async def ensure_tts_track(self, sample_rate: int, num_channels: int = 1) -> None:
        """TTS 오디오 트랙 생성 및 publish"""
        if not self._ctx.room or not self._ctx.is_connected:
            raise RuntimeError("LiveKit 연결이 필요합니다.")

        async with self._tts_publish_lock:
            if self._tts_source and self._tts_track:
                return

            self._tts_source = rtc.AudioSource(sample_rate, num_channels, queue_size_ms=1000)
            self._tts_track = rtc.LocalAudioTrack.create_audio_track(
                "mit-agent-tts", self._tts_source
            )
            options = rtc.TrackPublishOptions()
            options.source = rtc.TrackSource.SOURCE_MICROPHONE
            await self._ctx.room.local_participant.publish_track(self._tts_track, options)
            logger.info("TTS 오디오 트랙 publish 완료 (sr=%s, ch=%s)", sample_rate, num_channels)

    async def play_pcm_bytes(
        self,
        pcm_bytes: bytes,
        sample_rate: int,
        num_channels: int = 1,
        *,
        target_sample_rate: int | None = None,
        frame_duration_ms: int = 20,
        interrupt_event: asyncio.Event | None = None,
    ) -> bool:
        """PCM16LE 바이트를 LiveKit 오디오로 재생

        Args:
            pcm_bytes: raw PCM16LE 오디오 데이터
            sample_rate: PCM 데이터의 sample rate (Hz)
            num_channels: 채널 수 (기본 1=mono)
            target_sample_rate: 출력 sample rate (None이면 입력과 동일)
            frame_duration_ms: 프레임 길이 (ms)
            interrupt_event: 설정 시 이 이벤트가 set되면 재생 중단

        Returns:
            True if playback completed, False if interrupted
        """
        if not pcm_bytes:
            return True

        pcm = pcm_bytes

        if num_channels == 2:
            pcm = self._stereo_to_mono_int16(pcm)
            num_channels = 1

        pcm = self._apply_gain_int16(pcm, self._tts_volume_scale)

        output_rate = target_sample_rate or sample_rate
        await self.ensure_tts_track(output_rate, num_channels)

        if output_rate != sample_rate:
            resampler = rtc.AudioResampler(
                sample_rate,
                output_rate,
                num_channels=num_channels,
                quality=rtc.AudioResamplerQuality.MEDIUM,
            )
            async for frame in self._resample_and_chunk(
                resampler, pcm, sample_rate, num_channels, frame_duration_ms
            ):
                if interrupt_event and interrupt_event.is_set():
                    logger.info("TTS 재생 인터럽트 감지됨 (resample)")
                    return False
                await self._tts_source.capture_frame(frame)
        else:
            async for frame in self._chunk_pcm_frames(
                pcm, sample_rate, num_channels, frame_duration_ms
            ):
                if interrupt_event and interrupt_event.is_set():
                    logger.info("TTS 재생 인터럽트 감지됨")
                    return False
                await self._tts_source.capture_frame(frame)

        return True

    @staticmethod
    def _stereo_to_mono_int16(pcm_data: bytes) -> bytes:
        """16-bit stereo PCM을 mono로 변환"""
        samples = array("h")
        samples.frombytes(pcm_data)
        if len(samples) % 2 != 0:
            samples = samples[:-1]

        mono = array("h")
        for i in range(0, len(samples), 2):
            mono.append((samples[i] + samples[i + 1]) // 2)

        return mono.tobytes()

    @staticmethod
    def _apply_gain_int16(pcm_data: bytes, gain: float) -> bytes:
        """16-bit PCM 데이터에 gain을 적용한다."""
        if not pcm_data or gain == 1.0:
            return pcm_data

        if len(pcm_data) % 2 != 0:
            logger.warning(
                "PCM 데이터 길이가 홀수(%d bytes)여서 마지막 1바이트를 버립니다.",
                len(pcm_data),
            )
            pcm_data = pcm_data[:-1]

        if not pcm_data:
            return b""

        samples = array("h")
        samples.frombytes(pcm_data)

        scaled_samples = array("h")
        for sample in samples:
            scaled = int(sample * gain)
            if scaled > 32767:
                scaled = 32767
            elif scaled < -32768:
                scaled = -32768
            scaled_samples.append(scaled)

        return scaled_samples.tobytes()

    @staticmethod
    async def _chunk_pcm_frames(
        pcm_data: bytes,
        sample_rate: int,
        num_channels: int,
        frame_duration_ms: int,
    ):
        """PCM 바이트를 AudioFrame 단위로 분할"""
        bytes_per_sample = 2
        samples_per_frame = max(1, int(sample_rate * frame_duration_ms / 1000))
        frame_size = samples_per_frame * num_channels * bytes_per_sample

        for offset in range(0, len(pcm_data), frame_size):
            chunk = pcm_data[offset : offset + frame_size]
            samples = len(chunk) // (num_channels * bytes_per_sample)
            if samples <= 0:
                continue
            yield rtc.AudioFrame(chunk, sample_rate, num_channels, samples)

    @staticmethod
    async def _resample_and_chunk(
        resampler: rtc.AudioResampler,
        pcm_data: bytes,
        sample_rate: int,
        num_channels: int,
        frame_duration_ms: int,
    ):
        """리샘플링 후 AudioFrame 단위로 분할"""
        bytes_per_sample = 2
        samples_per_frame = max(1, int(sample_rate * frame_duration_ms / 1000))
        frame_size = samples_per_frame * num_channels * bytes_per_sample

        for offset in range(0, len(pcm_data), frame_size):
            chunk = pcm_data[offset : offset + frame_size]
            if not chunk:
                continue
            for frame in resampler.push(bytearray(chunk)):
                yield frame

        for frame in resampler.flush():
            yield frame

    async def send_chat_message(self, content: str, user_name: str = "부덕이") -> None:
        """DataPacket으로 채팅 메시지 전송"""
        if not self._ctx.room or not self._ctx.is_connected:
            return

        try:
            import json
            import uuid
            from datetime import datetime, timezone

            payload = {
                "type": "chat_message",
                "payload": {
                    "id": str(uuid.uuid4()),
                    "content": content,
                    "userName": user_name,
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                },
            }

            await self._ctx.room.local_participant.publish_data(
                json.dumps(payload),
                reliable=True,
            )
        except Exception as e:
            logger.warning(f"채팅 메시지 전송 실패: {e}")

    async def send_agent_state(self, state: str) -> None:
        """DataPacket으로 에이전트 상태 전송"""
        if not self._ctx.room or not self._ctx.is_connected:
            return

        try:
            import json

            payload = {
                "type": "agent_state",
                "payload": {
                    "state": state,
                },
            }

            await self._ctx.room.local_participant.publish_data(
                json.dumps(payload),
                reliable=True,
            )
            logger.debug(f"Agent 상태 전송: {state}")
        except Exception as e:
            logger.warning(f"Agent 상태 전송 실패: {e}")

    async def send_agent_status(self, text: str) -> None:
        """DataPacket으로 에이전트 상태 텍스트 전송 (프로필 위 표시용)"""
        if not self._ctx.room or not self._ctx.is_connected:
            return

        try:
            import json

            payload = {
                "type": "agent_status",
                "payload": {
                    "text": text,
                },
            }

            await self._ctx.room.local_participant.publish_data(
                json.dumps(payload),
                reliable=True,
            )
            logger.debug(f"Agent 상태 텍스트 전송: {text[:30]}")
        except Exception as e:
            logger.warning(f"Agent 상태 텍스트 전송 실패: {e}")

    def _on_participant_connected(self, participant: rtc.RemoteParticipant) -> None:
        """참여자 입장 이벤트"""
        asyncio.create_task(self._handle_participant_joined(participant))

        # (추가) 참가자 입장 시 이미 publish된 트랙이 있으면 마이크 오디오만 구독
        for publication in participant.track_publications.values():
            self._subscribe_publication_if_needed(publication)

    def _on_participant_disconnected(self, participant: rtc.RemoteParticipant) -> None:
        """참여자 퇴장 이벤트"""
        asyncio.create_task(self._handle_participant_left(participant))

    def _on_track_subscribed(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        """트랙 구독 이벤트"""
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            asyncio.create_task(self._handle_audio_track_subscribed(track, participant))

    def _on_track_unsubscribed(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        """트랙 구독 해제 이벤트"""
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            self._handle_audio_track_unsubscribed(participant)

    def _on_disconnected(self) -> None:
        """연결 해제 이벤트"""
        logger.warning(f"LiveKit 연결 해제: {self.meeting_id}")
        self._ctx.is_connected = False

    def _on_data_received(self, data: rtc.DataPacket) -> None:
        """DataPacket 수신 이벤트 (VAD 이벤트 등)"""
        try:
            import json

            message = json.loads(data.data.decode("utf-8"))

            if message.get("type") == "vad_event":
                payload = message.get("payload", {})
                event_type = payload.get("eventType", "")

                # 발신자 정보 추출
                participant = data.participant
                user_id = participant.identity if participant else "unknown"

                # 메타데이터에서 실제 user_id 추출
                if participant and participant.metadata:
                    try:
                        meta = json.loads(participant.metadata)
                        user_id = meta.get("userId", user_id)
                    except Exception:
                        pass

                logger.info(
                    f"VAD 이벤트 수신: user={user_id}, type={event_type}, "
                    f"start={payload.get('segmentStartMs')}, end={payload.get('segmentEndMs')}"
                )

                if self.on_vad_event:
                    self.on_vad_event(user_id, event_type, payload)

        except Exception as e:
            logger.warning(f"DataPacket 파싱 오류: {e}")

    # (추가) 트랙 publish 이벤트에서 마이크 오디오만 구독
    def _on_track_published(
        self,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        self._subscribe_publication_if_needed(publication)

    # (추가) publication을 보고 구독 여부를 결정 (마이크 오디오만)
    def _subscribe_publication_if_needed(self, publication) -> None:
        try:
            kind = getattr(publication, "kind", None)
            if kind != rtc.TrackKind.KIND_AUDIO:
                return

            # source가 노출되는 SDK 버전이라면 "마이크"만 허용
            source = getattr(publication, "source", None)
            if source is not None:
                # SDK 버전에 따라 TrackSource 상수명이 다를 수 있어 안전하게 비교
                mic_source = getattr(rtc.TrackSource, "MICROPHONE", None)
                if mic_source is not None and source != mic_source:
                    return

            # 이미 구독 중이면 스킵
            is_subscribed = getattr(publication, "subscribed", None)
            if is_subscribed is True:
                return

            publication.set_subscribed(True)

        except Exception as e:
            logger.debug(f"publication 구독 처리 실패: {e}")

    async def _handle_participant_joined(
        self,
        participant: rtc.RemoteParticipant,
    ) -> None:
        """참여자 입장 처리"""
        # 메타데이터에서 user_id 추출 (없으면 identity 사용)
        user_id = participant.identity
        if participant.metadata:
            try:
                import json

                meta = json.loads(participant.metadata)
                user_id = meta.get("userId", participant.identity)
            except Exception:
                pass

        self._ctx.participants[participant.sid] = ParticipantAudio(
            participant_id=participant.sid,
            participant_name=participant.name or participant.identity,
            user_id=user_id,
        )

        logger.info(f"참여자 입장: {participant.name} (user_id={user_id})")

        if self.on_participant_joined:
            self.on_participant_joined(user_id, participant.name or participant.identity)

    async def _handle_participant_left(
        self,
        participant: rtc.RemoteParticipant,
    ) -> None:
        """참여자 퇴장 처리"""
        if participant.sid in self._ctx.participants:
            p_audio = self._ctx.participants.pop(participant.sid)
            logger.info(f"참여자 퇴장: {p_audio.participant_name} (user_id={p_audio.user_id})")

            # 오디오 스트림 태스크 취소
            if participant.sid in self._audio_tasks:
                self._audio_tasks[participant.sid].cancel()
                del self._audio_tasks[participant.sid]

            if self.on_participant_left:
                self.on_participant_left(p_audio.user_id)

    async def _handle_audio_track_subscribed(
        self,
        track: rtc.Track,
        participant: rtc.RemoteParticipant,
    ) -> None:
        """오디오 트랙 구독 처리"""
        if participant.sid not in self._ctx.participants:
            return

        p_audio = self._ctx.participants[participant.sid]
        p_audio.track = track

        # 오디오 스트림 생성 및 처리 태스크 시작
        audio_stream = rtc.AudioStream(
            track,
            sample_rate=16000,
            num_channels=1,
            frame_size_ms=100,  # STT 버퍼(100ms)와 맞추기
            capacity=10,  # 무한 큐 방지
        )
        p_audio.audio_stream = audio_stream

        task = asyncio.create_task(self._process_audio_stream(participant.sid, audio_stream))
        self._audio_tasks[participant.sid] = task

        logger.debug(f"오디오 트랙 구독: {p_audio.participant_name}")

    def _handle_audio_track_unsubscribed(
        self,
        participant: rtc.RemoteParticipant,
    ) -> None:
        """오디오 트랙 구독 해제 처리"""
        if participant.sid in self._audio_tasks:
            self._audio_tasks[participant.sid].cancel()
            del self._audio_tasks[participant.sid]

        if participant.sid in self._ctx.participants:
            p_audio = self._ctx.participants[participant.sid]
            p_audio.track = None
            p_audio.audio_stream = None
            logger.debug(f"오디오 트랙 구독 해제: {p_audio.participant_name}")

    async def _process_audio_stream(
        self,
        participant_sid: str,
        audio_stream: rtc.AudioStream,
    ) -> None:
        """오디오 스트림 처리

        LiveKit AudioStream에서 프레임을 받아 PCM으로 변환하여 콜백 호출
        """
        try:
            async for frame_event in audio_stream:
                frame = frame_event.frame

                if participant_sid not in self._ctx.participants:
                    break

                p_audio = self._ctx.participants[participant_sid]

                # PCM 16-bit로 변환 (AudioStream에서 이미 16kHz, mono로 리샘플링됨)
                pcm_data = frame.data.tobytes()

                if self.on_audio_frame and pcm_data:
                    self.on_audio_frame(
                        p_audio.user_id,
                        p_audio.participant_name,
                        pcm_data,
                    )

        except asyncio.CancelledError:
            logger.debug(f"오디오 스트림 태스크 취소: {participant_sid}")
        except Exception as e:
            logger.exception(f"오디오 스트림 처리 오류: {e}")
        finally:
            # 중요: 네이티브 핸들 정리
            await audio_stream.aclose()
