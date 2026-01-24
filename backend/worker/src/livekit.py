"""LiveKit Bot - 회의 참여, 오디오 구독 및 AI 에이전트 기능"""

import asyncio
import logging
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

        self._ctx = LiveKitBotContext(meeting_id=meeting_id)
        self._audio_tasks: dict[str, asyncio.Task] = {}

    async def _create_token(self) -> str:
        """LiveKit 접근 토큰 생성"""
        token = api.AccessToken(
            self.config.livekit_api_key,
            self.config.livekit_api_secret,
        )
        token.with_identity(f"mit-agent-{self.meeting_id}")
        token.with_name("Mit Agent")
        token.with_grants(
            api.VideoGrants(
                room_join=True,
                room=self.meeting_id,
                can_subscribe=True,
                can_publish=False,  # 현재는 오디오 발행 안함 (향후 TTS/RAG 응답 시 True)
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

        # 토큰 생성 및 연결
        token = await self._create_token()
        await self._ctx.room.connect(self.config.livekit_ws_url, token)

        self._ctx.is_connected = True
        logger.info(f"LiveKit 회의 참여: {self.meeting_id}")

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

    def _on_participant_connected(self, participant: rtc.RemoteParticipant) -> None:
        """참여자 입장 이벤트"""
        asyncio.create_task(self._handle_participant_joined(participant))

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
            asyncio.create_task(
                self._handle_audio_track_subscribed(track, participant)
            )

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

            # 마지막 실제 참여자가 나가면 worker도 퇴장
            if not self._ctx.participants:
                logger.info("마지막 참여자 퇴장, Worker 종료")
                await self.disconnect()

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
