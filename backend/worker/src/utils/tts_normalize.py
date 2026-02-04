"""TTS 입력 텍스트 정규화 모듈.

LLM 응답 및 status 메시지를 TTS 서버에 보내기 전에
음성 합성에 불필요한 요소를 제거합니다.
"""

from __future__ import annotations

import re

# ── 사전 컴파일 패턴 ────────────────────────────────────────

# 1. 마크다운 링크 → 텍스트만 보존 (URL 제거 전에 처리해야 함)
_RE_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")

# 1-1. URL
_RE_URL = re.compile(r"https?://\S+")

# 2. 마크다운
_RE_CODE_BLOCK = re.compile(r"```[\s\S]*?```")  # 코드블록 (내용 전체 제거)
_RE_INLINE_CODE = re.compile(r"`([^`]+)`")  # 인라인 코드 → 내용만 보존
_RE_HEADER = re.compile(r"^#{1,6}\s+", re.MULTILINE)  # 헤더 마커
_RE_BOLD_ITALIC = re.compile(r"\*{1,3}([^*]+)\*{1,3}")  # **bold**, *italic*
_RE_UNDERLINE_BOLD = re.compile(r"_{1,3}([^_]+)_{1,3}")  # __bold__, _italic_
_RE_STRIKETHROUGH = re.compile(r"~~([^~]+)~~")  # ~~취소선~~
_RE_BLOCKQUOTE = re.compile(r"^>\s?", re.MULTILINE)  # > 인용
_RE_UNORDERED_LIST = re.compile(r"^[\s]*[-*+]\s+", re.MULTILINE)  # - 항목, * 항목
_RE_ORDERED_LIST = re.compile(r"^[\s]*\d+\.\s+", re.MULTILINE)  # 1. 항목

# 3. 이모지 — SMP 이모지 블록 + BMP 에서 자주 쓰이는 이모지만 타겟팅
#    한글(U+AC00-U+D7AF), 일반 구두점, 라틴 문자와 겹치지 않도록 보수적 범위 사용
_RE_EMOJI = re.compile(
    "["
    "\U0001f600-\U0001f64f"  # Emoticons
    "\U0001f300-\U0001f5ff"  # Misc Symbols & Pictographs
    "\U0001f680-\U0001f6ff"  # Transport & Map
    "\U0001f1e0-\U0001f1ff"  # Flags (Regional Indicators)
    "\U0001f900-\U0001f9ff"  # Supplemental Symbols & Pictographs
    "\U0001fa00-\U0001fa6f"  # Chess Symbols
    "\U0001fa70-\U0001faff"  # Symbols & Pictographs Extended-A
    "\u2702-\u27b0"  # Dingbats
    "\u2600-\u26ff"  # Misc Symbols (☀☁☂ 등)
    "\ufe0f"  # Variation Selector-16
    "\u200d"  # Zero-Width Joiner
    "\u2b50"  # Star ⭐
    "\u2b55"  # Circle ⭕
    "\u2b05-\u2b07"  # Arrows ⬅⬆⬇
    "\u2b1b\u2b1c"  # Black/White squares ⬛⬜
    "\u23e9-\u23f3"  # Media controls ⏩-⏳
    "\u23f8-\u23fa"  # Media controls ⏸-⏺
    "\u231a\u231b"  # Watch/Hourglass ⌚⌛
    "\u25aa-\u25ab"  # Small squares ▪▫
    "\u25b6\u25c0"  # Play buttons ▶◀
    "\u25fb-\u25fe"  # Squares ◻-◾
    "\u3030"  # Wavy dash 〰
    "\u303d"  # Part alternation mark 〽
    "\u3297\u3299"  # Japanese symbols ㊗㊙
    "]+",
)

# 4. 인용/참조 마커
_RE_CITATION = re.compile(r"\[\d+\]")  # [1], [2] 등
_RE_REFERENCE = re.compile(r"\[[가-힣]{1,4}\]")  # [참고], [출처] 등

# 5. 괄호 기호 (내용 보존)
#    여는 괄호 → 공백 (앞 단어와 분리: 인증(OAuth) → 인증 OAuth)
#    닫는 괄호 → 제거 (뒤 조사와 연결 유지: 8기)의 → 8기의)
_RE_OPEN_BRACKETS = re.compile(r"[(\[{]")
_RE_CLOSE_BRACKETS = re.compile(r"[)\]}]")

# 6. 숫자 콤마 (숫자,숫자 패턴만)
_RE_NUM_COMMA = re.compile(r"(\d),(\d)")

# 7. 특수문자 (마크다운 제거 후 남은 것들)
#    ~: 범위 표현(10~20)에서 사용, ~~취소~~는 _RE_STRIKETHROUGH에서 처리됨
#    _: 기술 용어(action_item)에서 사용, __볼드__는 _RE_UNDERLINE_BOLD에서 처리됨
_RE_SPECIAL_CHARS = re.compile(r"[`*|]")

# 7-1. 마크다운 테이블 구분선 (--- 로만 구성된 행)
_RE_TABLE_SEPARATOR = re.compile(r"^[\s]*-{3,}[\s-]*$", re.MULTILINE)

# 8. 반복 구두점
_RE_REPEATED_PUNCT = re.compile(r"([.!?])\1+")

# 9. 다중 공백/개행
_RE_MULTI_NEWLINE = re.compile(r"\n{2,}")
_RE_MULTI_SPACE = re.compile(r" {2,}")


def normalize_tts_text(text: str) -> str:
    """TTS 전송용 텍스트 정규화.

    Parameters
    ----------
    text : str
        원본 텍스트 (LLM 응답 또는 status 메시지)

    Returns
    -------
    str
        정규화된 텍스트. 빈 문자열이면 TTS 큐에 추가하지 않아야 함.
    """
    if not text or not text.strip():
        return ""

    result = text

    # 1. 마크다운 링크 → 텍스트만 보존 (URL 제거 전에 처리)
    result = _RE_MD_LINK.sub(r"\1", result)

    # 1-1. URL 제거
    result = _RE_URL.sub("", result)

    # 2. 마크다운 구문 제거
    result = _RE_CODE_BLOCK.sub("", result)  # 코드블록 전체 제거
    result = _RE_INLINE_CODE.sub(r"\1", result)  # `코드` → 코드
    result = _RE_HEADER.sub("", result)  # ## 헤더 → 헤더
    result = _RE_BOLD_ITALIC.sub(r"\1", result)  # **볼드** → 볼드
    result = _RE_UNDERLINE_BOLD.sub(r"\1", result)  # __볼드__ → 볼드
    result = _RE_STRIKETHROUGH.sub(r"\1", result)  # ~~취소~~ → 취소
    result = _RE_BLOCKQUOTE.sub("", result)  # > 인용 → 인용
    result = _RE_UNORDERED_LIST.sub("", result)  # - 항목 → 항목
    result = _RE_ORDERED_LIST.sub("", result)  # 1. 항목 → 항목

    # 3. 이모지 제거
    result = _RE_EMOJI.sub("", result)

    # 4. 인용/참조 마커 제거
    result = _RE_CITATION.sub("", result)
    result = _RE_REFERENCE.sub("", result)

    # 5. 괄호 기호 제거 (내용 보존)
    result = _RE_OPEN_BRACKETS.sub(" ", result)
    result = _RE_CLOSE_BRACKETS.sub("", result)

    # 6. 숫자 콤마 제거 (반복 적용: 1,234,567 → 1234567)
    while _RE_NUM_COMMA.search(result):
        result = _RE_NUM_COMMA.sub(r"\1\2", result)

    # 7. 특수문자 정리
    result = _RE_SPECIAL_CHARS.sub("", result)

    # 7-1. 마크다운 테이블 구분선 제거
    result = _RE_TABLE_SEPARATOR.sub("", result)

    # 8. 반복 구두점 정규화
    result = _RE_REPEATED_PUNCT.sub(r"\1", result)

    # 9. 공백/개행 정규화
    result = _RE_MULTI_NEWLINE.sub("\n", result)
    result = _RE_MULTI_SPACE.sub(" ", result)
    result = result.strip()

    return result
