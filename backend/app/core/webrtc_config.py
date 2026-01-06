"""WebRTC 관련 설정"""

# ICE 서버 설정 (STUN만 사용)
# 같은 네트워크 또는 NAT 타입이 호환되는 환경에서 P2P 연결 가능
# TURN 서버 없이 동작하므로 제한적인 NAT(Symmetric NAT) 환경에서는 연결 실패 가능
ICE_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
]

# 최대 참여자 수
MAX_PARTICIPANTS = 10

# 미디어 제약 조건 (오디오만)
MEDIA_CONSTRAINTS = {
    "audio": True,
    "video": False,  # 추후 확장 시 True로 변경
}

# WebSocket 에러 코드
class WSErrorCode:
    """WebSocket 에러 코드"""
    INVALID_TOKEN = 4001
    MEETING_NOT_FOUND = 4002
    NOT_PARTICIPANT = 4003
    MEETING_NOT_STARTED = 4004
    MEETING_ALREADY_ENDED = 4005
    ROOM_FULL = 4006
    INTERNAL_ERROR = 4500
