"""ICECandidateParser 단위 테스트"""

import pytest
from unittest.mock import patch, MagicMock

from app.utils.ice_parser import ICECandidateParser


class TestICECandidateParser:
    """ICECandidateParser.parse() 메서드 테스트"""

    def test_parse_host_candidate_success(self):
        """host 타입 ICE candidate 파싱 성공"""
        # Given: 유효한 host candidate
        candidate_str = "842163049 1 udp 2122260223 192.168.1.100 54321 typ host generation 0"
        candidate_dict = {"sdpMid": "0", "sdpMLineIndex": 0}

        # When
        result = ICECandidateParser.parse(candidate_str, candidate_dict)

        # Then
        assert result is not None
        assert result.foundation == "842163049"
        assert result.component == 1
        assert result.protocol == "udp"
        assert result.priority == 2122260223
        assert result.ip == "192.168.1.100"
        assert result.port == 54321
        assert result.type == "host"
        assert result.sdpMid == "0"
        assert result.sdpMLineIndex == 0
        assert result.relatedAddress is None
        assert result.relatedPort is None

    def test_parse_srflx_candidate_with_raddr_rport(self):
        """srflx 타입 ICE candidate (raddr/rport 포함) 파싱 성공"""
        # Given: srflx candidate with related address/port
        candidate_str = "1234567890 1 udp 1685987071 203.0.113.50 12345 typ srflx raddr 192.168.1.100 rport 54321"
        candidate_dict = {"sdpMid": "audio", "sdpMLineIndex": 0}

        # When
        result = ICECandidateParser.parse(candidate_str, candidate_dict)

        # Then
        assert result is not None
        assert result.type == "srflx"
        assert result.ip == "203.0.113.50"
        assert result.port == 12345
        assert result.relatedAddress == "192.168.1.100"
        assert result.relatedPort == 54321

    def test_parse_relay_candidate(self):
        """relay 타입 ICE candidate 파싱 성공"""
        # Given: relay candidate
        candidate_str = "9876543210 1 udp 41885439 198.51.100.10 60000 typ relay raddr 203.0.113.50 rport 12345"
        candidate_dict = {"sdpMid": "0", "sdpMLineIndex": 0}

        # When
        result = ICECandidateParser.parse(candidate_str, candidate_dict)

        # Then
        assert result is not None
        assert result.type == "relay"
        assert result.relatedAddress == "203.0.113.50"
        assert result.relatedPort == 12345

    def test_parse_candidate_with_prefix(self):
        """'candidate:' 접두사가 있는 경우 정상 파싱"""
        # Given: candidate: prefix 포함
        candidate_str = "candidate:842163049 1 udp 2122260223 192.168.1.100 54321 typ host"
        candidate_dict = {"sdpMid": "0", "sdpMLineIndex": 0}

        # When
        result = ICECandidateParser.parse(candidate_str, candidate_dict)

        # Then
        assert result is not None
        assert result.foundation == "842163049"
        assert result.type == "host"

    def test_parse_candidate_without_prefix(self):
        """'candidate:' 접두사가 없는 경우 정상 파싱"""
        # Given: prefix 없음
        candidate_str = "842163049 1 udp 2122260223 192.168.1.100 54321 typ host"
        candidate_dict = {"sdpMid": "0", "sdpMLineIndex": 0}

        # When
        result = ICECandidateParser.parse(candidate_str, candidate_dict)

        # Then
        assert result is not None
        assert result.foundation == "842163049"

    def test_parse_tcp_candidate(self):
        """TCP 프로토콜 candidate 파싱"""
        # Given: TCP candidate
        candidate_str = "842163049 1 tcp 2122260223 192.168.1.100 9999 typ host tcptype passive"
        candidate_dict = {"sdpMid": "0", "sdpMLineIndex": 0}

        # When
        result = ICECandidateParser.parse(candidate_str, candidate_dict)

        # Then
        assert result is not None
        assert result.protocol == "tcp"

    def test_parse_invalid_candidate_too_few_fields(self):
        """필드가 부족한 잘못된 candidate는 None 반환"""
        # Given: 8개 미만 필드
        candidate_str = "842163049 1 udp 2122260223"
        candidate_dict = {"sdpMid": "0", "sdpMLineIndex": 0}

        # When
        result = ICECandidateParser.parse(candidate_str, candidate_dict)

        # Then
        assert result is None

    def test_parse_invalid_component_value(self):
        """component가 정수가 아닌 경우 None 반환"""
        # Given: component가 문자열
        candidate_str = "842163049 invalid udp 2122260223 192.168.1.100 54321 typ host"
        candidate_dict = {"sdpMid": "0", "sdpMLineIndex": 0}

        # When
        result = ICECandidateParser.parse(candidate_str, candidate_dict)

        # Then
        assert result is None

    def test_parse_invalid_port_value(self):
        """port가 정수가 아닌 경우 None 반환"""
        # Given: port가 문자열
        candidate_str = "842163049 1 udp 2122260223 192.168.1.100 invalid typ host"
        candidate_dict = {"sdpMid": "0", "sdpMLineIndex": 0}

        # When
        result = ICECandidateParser.parse(candidate_str, candidate_dict)

        # Then
        assert result is None

    def test_parse_empty_sdp_mid(self):
        """sdpMid가 없는 경우에도 파싱 성공"""
        # Given: sdpMid 없음
        candidate_str = "842163049 1 udp 2122260223 192.168.1.100 54321 typ host"
        candidate_dict = {}

        # When
        result = ICECandidateParser.parse(candidate_str, candidate_dict)

        # Then
        assert result is not None
        assert result.sdpMid is None
        assert result.sdpMLineIndex is None

    def test_parse_uppercase_protocol_converted_to_lowercase(self):
        """프로토콜이 대문자인 경우 소문자로 변환"""
        # Given: UDP 대문자
        candidate_str = "842163049 1 UDP 2122260223 192.168.1.100 54321 typ host"
        candidate_dict = {"sdpMid": "0", "sdpMLineIndex": 0}

        # When
        result = ICECandidateParser.parse(candidate_str, candidate_dict)

        # Then
        assert result is not None
        assert result.protocol == "udp"

    def test_parse_candidate_with_extra_fields(self):
        """추가 필드가 있는 candidate도 정상 파싱"""
        # Given: generation, ufrag 등 추가 필드
        candidate_str = "842163049 1 udp 2122260223 192.168.1.100 54321 typ host generation 0 ufrag abc network-id 1"
        candidate_dict = {"sdpMid": "0", "sdpMLineIndex": 0}

        # When
        result = ICECandidateParser.parse(candidate_str, candidate_dict)

        # Then
        assert result is not None
        assert result.type == "host"
