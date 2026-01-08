"""ICE candidate 파싱 유틸리티"""

import logging

logger = logging.getLogger(__name__)


class ICECandidateParser:
    """브라우저 ICE candidate 문자열을 aiortc RTCIceCandidate로 파싱하는 유틸리티"""

    @staticmethod
    def parse(candidate_str: str, candidate_dict: dict):
        """브라우저 ICE candidate 문자열을 aiortc RTCIceCandidate로 파싱

        Args:
            candidate_str: "candidate:..." 형식의 문자열
            candidate_dict: sdpMid, sdpMLineIndex 포함 딕셔너리

        Returns:
            RTCIceCandidate 또는 None
        """
        from aiortc import RTCIceCandidate

        # "candidate:" 접두사 제거
        if candidate_str.startswith("candidate:"):
            candidate_str = candidate_str[10:]

        # 기본 필드 파싱: foundation component protocol priority ip port typ type
        parts = candidate_str.split()
        if len(parts) < 8:
            logger.warning(f"Invalid candidate format: {candidate_str[:50]}")
            return None

        try:
            foundation = parts[0]
            component = int(parts[1])
            protocol = parts[2].lower()
            priority = int(parts[3])
            ip = parts[4]
            port = int(parts[5])
            # parts[6]은 "typ"
            candidate_type = parts[7]

            # 선택적 필드 파싱 (raddr, rport 등)
            related_address = None
            related_port = None

            i = 8
            while i < len(parts) - 1:
                if parts[i] == "raddr":
                    related_address = parts[i + 1]
                    i += 2
                elif parts[i] == "rport":
                    related_port = int(parts[i + 1])
                    i += 2
                else:
                    i += 1

            return RTCIceCandidate(
                component=component,
                foundation=foundation,
                ip=ip,
                port=port,
                priority=priority,
                protocol=protocol,
                type=candidate_type,
                relatedAddress=related_address,
                relatedPort=related_port,
                sdpMid=candidate_dict.get("sdpMid"),
                sdpMLineIndex=candidate_dict.get("sdpMLineIndex"),
            )
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse candidate: {e}")
            return None
