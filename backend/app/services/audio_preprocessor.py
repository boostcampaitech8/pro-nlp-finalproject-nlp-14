"""오디오 전처리 모듈 (VAD 기반 발화 구간 추출)"""

import logging
import struct
from dataclasses import dataclass
from io import BytesIO
from typing import Iterator

import webrtcvad
from pydub import AudioSegment

logger = logging.getLogger(__name__)


@dataclass
class VoiceSegment:
    """발화 구간"""

    start_ms: int  # 시작 시간 (밀리초)
    end_ms: int    # 종료 시간 (밀리초)
    audio_data: bytes  # 해당 구간 오디오 데이터

    @property
    def duration_ms(self) -> int:
        """구간 길이 (밀리초)"""
        return self.end_ms - self.start_ms


class AudioPreprocessor:
    """오디오 전처리기

    VAD(Voice Activity Detection)를 사용하여 발화 구간을 추출하고
    무음 구간을 제거하여 STT 비용/시간을 절약
    """

    # VAD 프레임 크기 (10, 20, 30ms 중 선택)
    FRAME_DURATION_MS = 30

    # 발화 구간으로 인식하기 위한 최소 연속 프레임 수
    MIN_VOICE_FRAMES = 10  # 300ms

    # 발화 종료로 인식하기 위한 최소 무음 프레임 수
    MIN_SILENCE_FRAMES = 20  # 600ms

    # 발화 구간 병합을 위한 최소 간격 (밀리초)
    MERGE_GAP_MS = 500

    # VAD 민감도 (0-3, 높을수록 민감)
    VAD_MODE = 2

    def __init__(
        self,
        vad_mode: int = 2,
        min_voice_ms: int = 300,
        min_silence_ms: int = 600,
        merge_gap_ms: int = 500,
    ):
        """전처리기 초기화

        Args:
            vad_mode: VAD 민감도 (0-3)
            min_voice_ms: 발화로 인식할 최소 길이 (밀리초)
            min_silence_ms: 발화 종료로 인식할 무음 길이 (밀리초)
            merge_gap_ms: 구간 병합 최소 간격 (밀리초)
        """
        self.vad_mode = vad_mode
        self.min_voice_frames = min_voice_ms // self.FRAME_DURATION_MS
        self.min_silence_frames = min_silence_ms // self.FRAME_DURATION_MS
        self.merge_gap_ms = merge_gap_ms

    def extract_voice_segments(
        self,
        audio_data: bytes,
        output_format: str = "mp3",
    ) -> list[VoiceSegment]:
        """오디오에서 발화 구간만 추출

        Args:
            audio_data: 원본 오디오 바이트 데이터 (WebM, MP3 등)
            output_format: 출력 오디오 형식 (mp3, wav 등)

        Returns:
            list[VoiceSegment]: 발화 구간 목록
        """
        # 오디오 로드 및 변환
        audio = AudioSegment.from_file(BytesIO(audio_data))

        # VAD는 16kHz, mono, 16bit PCM 필요
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

        logger.info(
            f"Audio loaded: duration={len(audio)}ms, "
            f"sample_rate=16000, channels=1"
        )

        # VAD 초기화
        vad = webrtcvad.Vad(self.vad_mode)

        # 프레임 생성 및 VAD 분석
        frames = list(self._generate_frames(audio))
        speech_frames = self._detect_speech(vad, frames)

        # 연속된 발화 구간 찾기
        raw_segments = self._find_voice_segments(speech_frames)

        # 짧은 간격의 구간 병합
        merged_segments = self._merge_segments(raw_segments)

        # 오디오 데이터 추출
        result = []
        for start_ms, end_ms in merged_segments:
            segment_audio = audio[start_ms:end_ms]
            audio_bytes = BytesIO()
            segment_audio.export(audio_bytes, format=output_format)
            audio_bytes.seek(0)

            result.append(VoiceSegment(
                start_ms=start_ms,
                end_ms=end_ms,
                audio_data=audio_bytes.read(),
            ))

        logger.info(
            f"Voice segments extracted: "
            f"original={len(audio)}ms, "
            f"segments={len(result)}, "
            f"total_voice={sum(s.duration_ms for s in result)}ms"
        )

        return result

    def convert_to_mp3(self, audio_data: bytes, bitrate: str = "64k") -> bytes:
        """오디오를 MP3로 변환 (용량 감소)

        Args:
            audio_data: 원본 오디오 바이트 데이터
            bitrate: MP3 비트레이트 (기본: 64k)

        Returns:
            bytes: MP3 바이트 데이터
        """
        audio = AudioSegment.from_file(BytesIO(audio_data))
        output = BytesIO()
        audio.export(output, format="mp3", bitrate=bitrate)
        output.seek(0)

        original_size = len(audio_data)
        compressed_size = len(output.getvalue())
        logger.info(
            f"Audio converted to MP3: "
            f"{original_size} -> {compressed_size} bytes "
            f"({compressed_size / original_size * 100:.1f}%)"
        )

        return output.read()

    def get_audio_duration_ms(self, audio_data: bytes) -> int:
        """오디오 길이 조회 (밀리초)"""
        audio = AudioSegment.from_file(BytesIO(audio_data))
        return len(audio)

    def _generate_frames(
        self,
        audio: AudioSegment,
    ) -> Iterator[tuple[int, bytes]]:
        """오디오를 VAD 프레임으로 분할

        Yields:
            tuple[int, bytes]: (시작 시간 ms, 프레임 데이터)
        """
        frame_size = int(16000 * self.FRAME_DURATION_MS / 1000) * 2  # 16bit = 2bytes

        raw_data = audio.raw_data
        offset = 0
        timestamp = 0

        while offset + frame_size <= len(raw_data):
            yield timestamp, raw_data[offset:offset + frame_size]
            offset += frame_size
            timestamp += self.FRAME_DURATION_MS

    def _detect_speech(
        self,
        vad: webrtcvad.Vad,
        frames: list[tuple[int, bytes]],
    ) -> list[tuple[int, bool]]:
        """각 프레임의 발화 여부 감지

        Returns:
            list[tuple[int, bool]]: (시작 시간 ms, 발화 여부) 목록
        """
        results = []
        for timestamp, frame_data in frames:
            try:
                is_speech = vad.is_speech(frame_data, 16000)
            except Exception:
                # VAD 에러 시 무음으로 처리
                is_speech = False
            results.append((timestamp, is_speech))
        return results

    def _find_voice_segments(
        self,
        speech_frames: list[tuple[int, bool]],
    ) -> list[tuple[int, int]]:
        """연속된 발화 구간 찾기

        Returns:
            list[tuple[int, int]]: (시작 ms, 종료 ms) 목록
        """
        segments = []
        in_speech = False
        speech_start = 0
        voice_count = 0
        silence_count = 0

        for timestamp, is_speech in speech_frames:
            if not in_speech:
                if is_speech:
                    voice_count += 1
                    if voice_count >= self.min_voice_frames:
                        # 발화 시작
                        in_speech = True
                        speech_start = timestamp - (self.min_voice_frames - 1) * self.FRAME_DURATION_MS
                        silence_count = 0
                else:
                    voice_count = 0
            else:
                if is_speech:
                    silence_count = 0
                else:
                    silence_count += 1
                    if silence_count >= self.min_silence_frames:
                        # 발화 종료
                        speech_end = timestamp - (self.min_silence_frames - 1) * self.FRAME_DURATION_MS
                        segments.append((speech_start, speech_end))
                        in_speech = False
                        voice_count = 0
                        silence_count = 0

        # 마지막 구간 처리
        if in_speech and speech_frames:
            speech_end = speech_frames[-1][0] + self.FRAME_DURATION_MS
            segments.append((speech_start, speech_end))

        return segments

    def _merge_segments(
        self,
        segments: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """짧은 간격의 구간 병합

        Returns:
            list[tuple[int, int]]: 병합된 (시작 ms, 종료 ms) 목록
        """
        if not segments:
            return []

        merged = [segments[0]]

        for start, end in segments[1:]:
            prev_start, prev_end = merged[-1]

            # 이전 구간과의 간격이 짧으면 병합
            if start - prev_end <= self.merge_gap_ms:
                merged[-1] = (prev_start, end)
            else:
                merged.append((start, end))

        return merged
