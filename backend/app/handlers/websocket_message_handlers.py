"""WebSocket 메시지 핸들러 - Strategy Pattern 구현"""

import logging
from typing import Protocol
from uuid import UUID

from app.schemas.webrtc import SignalingMessageType
from app.services.signaling_service import connection_manager

logger = logging.getLogger(__name__)


class MessageHandler(Protocol):
    """메시지 핸들러 프로토콜"""

    async def handle(self, meeting_id: UUID, user_id: UUID, data: dict) -> None:
        """메시지 처리

        Args:
            meeting_id: 회의 ID
            user_id: 사용자 ID
            data: 메시지 데이터
        """
        ...


class JoinHandler:
    """JOIN 메시지 핸들러"""

    async def handle(self, meeting_id: UUID, user_id: UUID, data: dict) -> None:
        # 현재 참여자 목록 전송
        participants = connection_manager.get_participants(meeting_id)
        participants_data = [
            {
                "userId": str(p.user_id),
                "userName": p.user_name,
                "role": p.role,
                "audioMuted": p.audio_muted,
            }
            for p in participants
        ]

        await connection_manager.send_to_user(
            meeting_id,
            user_id,
            {"type": SignalingMessageType.JOINED, "participants": participants_data},
        )

        # 다른 참여자들에게 새 참여자 알림
        current_participant = connection_manager.get_participant(meeting_id, user_id)
        if current_participant:
            await connection_manager.broadcast(
                meeting_id,
                {
                    "type": SignalingMessageType.PARTICIPANT_JOINED,
                    "participant": {
                        "userId": str(current_participant.user_id),
                        "userName": current_participant.user_name,
                        "role": current_participant.role,
                        "audioMuted": current_participant.audio_muted,
                    },
                },
                exclude_user_id=user_id,
            )


class OfferAnswerHandler:
    """OFFER/ANSWER 메시지 핸들러 (통합)"""

    def __init__(self, message_type: str):
        """
        Args:
            message_type: "offer" 또는 "answer"
        """
        self.message_type = message_type

    async def handle(self, meeting_id: UUID, user_id: UUID, data: dict) -> None:
        target_user_id = data.get("targetUserId")
        sdp = data.get("sdp")

        if not target_user_id or not sdp:
            return

        await connection_manager.send_to_user(
            meeting_id,
            UUID(target_user_id),
            {
                "type": self.message_type,
                "sdp": sdp,
                "fromUserId": str(user_id),
            },
        )


class ICECandidateHandler:
    """ICE_CANDIDATE 메시지 핸들러 (일반 + 화면공유)"""

    def __init__(self, message_type: str):
        """
        Args:
            message_type: "ice-candidate" 또는 "screen-ice-candidate"
        """
        self.message_type = message_type

    async def handle(self, meeting_id: UUID, user_id: UUID, data: dict) -> None:
        target_user_id = data.get("targetUserId")
        candidate = data.get("candidate")

        if not candidate:
            return

        if target_user_id:
            # 특정 사용자에게 전송
            await connection_manager.send_to_user(
                meeting_id,
                UUID(target_user_id),
                {
                    "type": self.message_type,
                    "candidate": candidate,
                    "fromUserId": str(user_id),
                },
            )
        else:
            # 모든 사용자에게 전송 (일반 ICE candidate만 해당)
            if self.message_type == SignalingMessageType.ICE_CANDIDATE:
                await connection_manager.broadcast(
                    meeting_id,
                    {
                        "type": self.message_type,
                        "candidate": candidate,
                        "fromUserId": str(user_id),
                    },
                    exclude_user_id=user_id,
                )
            else:
                logger.warning(f"Screen ICE candidate from {user_id} missing targetUserId")


class MuteHandler:
    """MUTE 메시지 핸들러"""

    async def handle(self, meeting_id: UUID, user_id: UUID, data: dict) -> None:
        muted = data.get("muted", False)

        # 상태 업데이트
        connection_manager.update_mute_status(meeting_id, user_id, muted)

        # 다른 참여자들에게 알림
        await connection_manager.broadcast(
            meeting_id,
            {
                "type": SignalingMessageType.PARTICIPANT_MUTED,
                "userId": str(user_id),
                "muted": muted,
            },
            exclude_user_id=user_id,
        )


class ScreenShareHandler:
    """SCREEN_SHARE_START/STOP 메시지 핸들러 (통합)"""

    def __init__(self, action: str):
        """
        Args:
            action: "start" 또는 "stop"
        """
        self.action = action
        self.response_type = (
            SignalingMessageType.SCREEN_SHARE_STARTED
            if action == "start"
            else SignalingMessageType.SCREEN_SHARE_STOPPED
        )

    async def handle(self, meeting_id: UUID, user_id: UUID, data: dict) -> None:
        logger.info(f"Screen share {self.action}ed by user {user_id} in meeting {meeting_id}")

        # 다른 참여자들에게 화면공유 상태 알림
        await connection_manager.broadcast(
            meeting_id,
            {
                "type": self.response_type,
                "userId": str(user_id),
            },
            exclude_user_id=user_id,
        )


class ScreenOfferAnswerHandler:
    """SCREEN_OFFER/ANSWER 메시지 핸들러 (통합)"""

    def __init__(self, message_type: str):
        """
        Args:
            message_type: "screen-offer" 또는 "screen-answer"
        """
        self.message_type = message_type

    async def handle(self, meeting_id: UUID, user_id: UUID, data: dict) -> None:
        target_user_id = data.get("targetUserId")
        sdp = data.get("sdp")

        if not target_user_id or not sdp:
            logger.warning(
                f"Invalid screen {self.message_type.split('-')[1]} from {user_id}: "
                f"missing targetUserId or sdp"
            )
            return

        logger.debug(f"Screen {self.message_type.split('-')[1]} from {user_id} to {target_user_id}")

        await connection_manager.send_to_user(
            meeting_id,
            UUID(target_user_id),
            {
                "type": self.message_type,
                "sdp": sdp,
                "fromUserId": str(user_id),
            },
        )


# 핸들러 레지스트리
HANDLERS: dict[str, MessageHandler] = {
    SignalingMessageType.JOIN: JoinHandler(),
    SignalingMessageType.OFFER: OfferAnswerHandler(SignalingMessageType.OFFER),
    SignalingMessageType.ANSWER: OfferAnswerHandler(SignalingMessageType.ANSWER),
    SignalingMessageType.ICE_CANDIDATE: ICECandidateHandler(SignalingMessageType.ICE_CANDIDATE),
    SignalingMessageType.MUTE: MuteHandler(),
    SignalingMessageType.SCREEN_SHARE_START: ScreenShareHandler("start"),
    SignalingMessageType.SCREEN_SHARE_STOP: ScreenShareHandler("stop"),
    SignalingMessageType.SCREEN_OFFER: ScreenOfferAnswerHandler(SignalingMessageType.SCREEN_OFFER),
    SignalingMessageType.SCREEN_ANSWER: ScreenOfferAnswerHandler(SignalingMessageType.SCREEN_ANSWER),
    SignalingMessageType.SCREEN_ICE_CANDIDATE: ICECandidateHandler(
        SignalingMessageType.SCREEN_ICE_CANDIDATE
    ),
}


async def dispatch_message(
    msg_type: str, meeting_id: UUID, user_id: UUID, data: dict
) -> bool:
    """메시지 타입에 따라 적절한 핸들러로 디스패치

    Args:
        msg_type: 메시지 타입
        meeting_id: 회의 ID
        user_id: 사용자 ID
        data: 메시지 데이터

    Returns:
        True if handler was found and executed, False if message type was LEAVE
    """
    # LEAVE는 특별 케이스 - 루프를 종료해야 함
    if msg_type == SignalingMessageType.LEAVE:
        return False

    handler = HANDLERS.get(msg_type)
    if handler:
        await handler.handle(meeting_id, user_id, data)
    else:
        logger.warning(f"Unknown message type: {msg_type}")

    return True
