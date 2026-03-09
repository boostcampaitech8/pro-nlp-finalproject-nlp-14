"""회의록 PDF를 generate_pr 입력 형태로 정규화하는 스크립트."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SPEAKER_UNKNOWN = "speaker_unknown"
MIN_TRANSCRIPT_LEN = 20
DEFAULT_MAX_WORKERS = max(1, (os.cpu_count() or 1) - 1)

BULLET_CHARS = "◯○◉●"
BULLET_CHAR_RE = re.compile(rf"[{re.escape(BULLET_CHARS)}]")

KNOWN_SURNAMES = {
    "가",
    "강",
    "고",
    "구",
    "권",
    "김",
    "나",
    "남",
    "노",
    "류",
    "문",
    "배",
    "백",
    "변",
    "보",
    "서",
    "성",
    "신",
    "안",
    "양",
    "어",
    "오",
    "우",
    "유",
    "윤",
    "이",
    "임",
    "장",
    "전",
    "조",
    "주",
    "진",
    "최",
    "채",
    "천",
    "한",
    "허",
    "홍",
    "황",
    "화",
    "백",
    "백",
    "오",
    "이",
    "임",
    "정",
}

ROLE_PREFIX_RE = re.compile(
    r"^("
    r"국회부의장대리|국회부의장|의사국장대리|의사국장|법제사법위원장대리|법제사법위원장|"
    r"재정경제위원장대리|재정경제위원장|과학기술정보방송통신위원장대리|과학기술정보방송통신위원장|"
    r"국방위위원장대리|국방위위원장|외교통일위원장대리|외교통일위원장|"
    r"위원장대리|의장대리|위원장|부의장|의장"
    r")\s+"
)

COMMITTEE_PREFIX_RE = re.compile(r"^[가-힣]{2,20}위원회\s+")

TIME_MARKER_RE = re.compile(r"^\(?\s*\d{1,2}\s*시\s*\d{1,2}\s*분[^)]*\)?$")
SESSION_OPEN_MARKER_RE = re.compile(r"개식|개회|개의|개\s*회")
SESSION_CLOSE_MARKER_RE = re.compile(r"폐식|산회|휴회|폐회|종료")
PAGE_HEADER_RE = re.compile(r"^\s*~{2,}\s*\d+\s*$")
PAGE_DATE_TOKEN_RE = r"\d{4}\s*(?:년|[./-])?\s*\d{1,2}\s*(?:월|[./-])?\s*\d{1,2}\s*(?:일|\.)?"
PAGE_MEETING_TOKEN_RE = r"제?\s*\d+\s*회.*(?:제?\s*\d+\s*차|개회식)"
PAGE_META_NOISE_RE = re.compile(
    rf"^\s*(?:\d+\s+)?{PAGE_MEETING_TOKEN_RE}\s*\(\s*{PAGE_DATE_TOKEN_RE}\s*\)\s*\d*\s*$",
    re.MULTILINE,
)
PAGE_META_NOISE_PREFIX_RE = re.compile(
    rf"(?m)^\s*(?:\d+\s+)?{PAGE_MEETING_TOKEN_RE}\s*\(\s*{PAGE_DATE_TOKEN_RE}\s*\)\s*\d*(?:\r?\n){{3}}",
)
PAGE_TRAILING_PNUM_RE = re.compile(r"(?m)^\s*\d+\s*(?:\r?\n){3}", re.MULTILINE)
PAGE_INLINE_NOISE_RE = re.compile(
    rf"^.*{PAGE_MEETING_TOKEN_RE}\s*\(\s*{PAGE_DATE_TOKEN_RE}\s*\)\s*\d*\s*",
    re.MULTILINE,
)
UNSPECIFIED_RESPONSE_RE = re.compile(
    r"^\(\s*(?:"
    r"(?:(?:◯|○|◉|●)\s*)?(?P<named_person>[가-힣]{2,4})\s*(?P<named_title>의원|위원|의장|위원장)\s*(?P<named_loc>의석|발언대 옆|단하|단상|의석\s*단말기)?\s*(?:에서|상)?\s*[―—\-]\s*(?:「(?P<named_quoted>[^」]+)」|(?P<named_plain>[^()]+?))"
    r"|"
    r"(?:[◯○◉●]\s*(?P<bullet_person>[가-힣]{2,4})(?=\s|$|[―—\-「]|(?:의원|위원|의장|위원장|의석|발언대|단하|단상))\s*(?P<bullet_title>의원|위원|의장|위원장)?\s*(?P<bullet_loc>의석|발언대 옆|단하|단상|의석\s*단말기)?\s*(?:에서|상)?\s*(?:[―—\-]{1,2}\s*)?(?:「(?P<bullet_quoted>[^」]+)」|(?P<bullet_plain>[^()]+?)))"
    r"|"
    r"(?:「(?P<quoted1>[^」]+)」|(?P<plain1>[^()]+?))\s*하는\s*(?P<role>(?:의원|위원|의원들|위원들))\s*있음"
    r")\s*\)\s*$"
)
UNSPECIFIED_INLINE_RESPONSE_RE = re.compile(
    r"\(\s*(?:"
    r"(?:(?:◯|○|◉|●)\s*)?(?P<named_person>[가-힣]{2,4})\s*(?P<named_title>의원|위원|의장|위원장)\s*(?P<named_loc>의석|발언대 옆|단하|단상|의석\s*단말기)?\s*(?:에서|상)?\s*[―—\-]\s*(?:「(?P<named_quoted>[^」]+)」|(?P<named_plain>[^()]+?))"
    r"|"
    r"(?:[◯○◉●]\s*(?P<bullet_person>[가-힣]{2,4})(?=\s|$|[―—\-「]|(?:의원|위원|의장|위원장|의석|발언대|단하|단상))\s*(?P<bullet_title>의원|위원|의장|위원장)?\s*(?P<bullet_loc>의석|발언대 옆|단하|단상|의석\s*단말기)?\s*(?:에서|상)?\s*(?:[―—\-]{1,2}\s*)?(?:「(?P<bullet_quoted>[^」]+)」|(?P<bullet_plain>[^()]+?)))"
    r"|"
    r"(?:「(?P<quoted1>[^」]+)」|(?P<plain1>[^()]+?))\s*하는\s*(?P<role>(?:의원|위원|의원들|위원들))\s*있음"
    r")\s*\)"
)
UNSPECIFIED_PREFIX_RESPONSE_RE = re.compile(r"^무기명 참석자 발언:\s*(?P<text>.+)$")
UNSPECIFIED_FOLLOWUP_RE = re.compile(
    r"^(?:(?:무기명\s*)?(?:가결|의결)했?습니다|가결되었음을\s*선포합니다|산회를\s*선포합니다|휴회를\s*선포합니다)\b.*$"
)
AGENDA_ITEM_RE = re.compile(r"^\d+\.\s*(?:국무위원후보자|의사일정|의안|안건|사안)")
AGENDA_LIST_ITEM_RE = re.compile(r"^\s*\d+\.\s+.+")
AGENDA_LIST_WRAP_RE = re.compile(r"^\s*번호\s*\d+\s*[\)\(]?$")
ANNEX_SECTION_RE = re.compile(r"^\s*.*실음\)?\s*$")
REPORT_END_FRAGMENT_RE = re.compile(r"^\s*\(보고사항은\s*끝에\s*$")
APPENDIX_FRAGMENT_RE = re.compile(r"^\s*\(심사보고서는\s*부록으로\s*보존함\s*$")
SPEAKER_LIST_META_RE = re.compile(
    r"^\s*-\s*(?:무제한토론|5분자유발언|반론발언)\s*의원\s*\([^)]+\)?\s*$"
)
AGENDA_META_INLINE_RE = re.compile(r"(?:^|\s)(?:번호|의안번호)\s+\d+.*$")
AGENDA_NUM_SERIES_RE = re.compile(r"\s+(?:\d{4,}\)\s*)+$")
AGENDA_ENDS_WITH_NUMBERISH_RE = re.compile(r"^\s*(?:\d+\)\s*)+$")
HEADER_MARKER_RE = re.compile(
    r"^\s*(?:"
    r"\[.*\]|"
    r"제?\s*\d+\s*회|"
    r"\d+\s*제\s*\d+\s*차|"
    r"◯?\s*회의록"
    r")\s*$"
)
SPEAKER_BLOCK_START_RE = re.compile(rf"(?m)^\s*[{re.escape(BULLET_CHARS)}]\s*")

PAREN_LEADING_RE = re.compile(r"^\((?:[^)]*)\)\s*")
SQUARE_LEADING_RE = re.compile(r"^\[(?:[^\]]*)\]\s*")
FULLWIDTH_BRACKET_LEADING_RE = re.compile(r"^（(?:[^）]*)）\s*")
CLOSED_BRACKET_PREFIX_RE = re.compile(r"^\s*[\)\]]+\s*")
QUOTE_MARK_PREFIX_RE = re.compile(r"^「(?:[^」]*)」\s*")
LOC_SPEECH_PREFIX_RE = re.compile(
    r"^(?:의석|발언대 옆|단하|단상|의석\s*단말기)\s*(?:에서|상)\s*[―—\-]\s*"
)

NAME_SUFFIXES = (
    "위원님",
    "위원입니다.",
    "위원입니다",
    "의원님",
    "의원입니다.",
    "의원입니다",
    "의장님",
    "의장입니다.",
    "의장입니다",
    "님",
    "입니다.",
    "입니다",
    "입니다만",
    "의원",
    "위원",
    "의장",
)

NAME_BLACKLIST_PREFIXES = (
    "조세",
    "조달",
    "보조",
    "성명",
    "가결",
    "성원",
    "안녕",
    "오늘",
    "주요",
    "한미",
    "문회",
    "신에",
    "남녀",
    "보고",
    "이에",
    "고는",
)

KNOWN_TITLES = {
    "국회부의장",
    "국회부의장대리",
    "의사국장",
    "의사국의사과",
    "의사국장대리",
    "법제사법위원장",
    "법제사법위원장대리",
    "재정경제위원장",
    "재정경제위원장대리",
    "과학기술정보방송통신위원장",
    "과학기술정보방송통신위원장대리",
    "국방위원장",
    "국방위원장대리",
    "외교통일위원장",
    "외교통일위원장대리",
    "위원장",
    "의장",
    "의장대리",
    "부의장",
    "의원",
    "위원",
    "전문위원",
    "위원장대리",
    "의장단",
    "청문회위원장",
    "교섭단체대표",
    "대통령",
}

NAME_SUFFIX_PATTERNS = (
    "의원님",
    "의원입니다.",
    "의원입니다",
    "위원님",
    "위원입니다.",
    "위원입니다",
    "의장님",
    "의장입니다.",
    "의장입니다",
    "님",
    "입니다.",
    "입니다",
    "입니다만",
)

_JOIN_PARTICLES = {
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "와",
    "과",
    "의",
    "에",
    "에서",
    "으로",
    "로",
    "께",
    "으로서",
    "으로는",
    "에서도",
    "에서도",
    "까지",
    "부터",
    "도",
    "만",
}

_JOIN_PREFIX_PAIRS = {
    "보": ("고드리",),
    "선": ("포",),
    "하": (
        "겠",
        "고",
        "구",
        "였",
        "도",
    ),
    "하도": ("록",),
    "하겠": (
        "습",
        "십시오",
        "시다",
    ),
    "가": ("결",),
    "법": ("률",),
    "일": ("부",),
    "수": ("정",),
    "직": ("장",),
    "조": ("정",),
    "관": ("련", "한"),
    "출": ("산", "석"),
    "제": ("출",),
    "동": ("료",),
    "이": ("용",),
}

_JOIN_ORPHAN_PREFIXES = (
    "결",
    "안",
    "포",
    "률",
    "정",
    "록",
    "습",
    "니",
    "용",
    "역",
    "산",
    "부",
    "조",
    "원",
    "료",
    "출",
    "한",
    "동",
    "일",
    "지",
)
_JOIN_ORPHAN_PREFIXES = (*_JOIN_ORPHAN_PREFIXES, "고", "서")
_JOIN_VERB_ENDING_TOKENS = (
    "다",
    "니다",
    "습니",
    "습니다",
    "시다",
    "십니다",
    "습니까",
    "시겠",
    "겠습니다",
)

_STANDALONE_SINGLE_CHARS = {
    "및",
    "등",
    "수",
    "것",
    "바",
    "데",
    "줄",
    "총",
    "각",
    "전",
    "현",
    "본",
    "타",
    "제",
    "그",
    "이",
    "저",
    "또",
    "왜",
    "참",
    "늘",
    "더",
    "덜",
    "곧",
    "잘",
    "못",
    "꼭",
    "꽤",
    "단",
    "즉",
    "약",
    "쯤",
    "겸",
    "만",
    "뿐",
    "내",
    "외",
    "앞",
    "뒤",
    "옆",
    "위",
    "아래",
    "때",
}

_AGENDA_STYLE_TOKEN_RE = re.compile(
    r"(의사일정|의안|안건|사안|법률안|개정법률안|국무위원후보자|국무위원|국정조사|결과보고서|의안번호|찬반의원성명|전자투표)"
)
_SENTENCE_VERB_HINT_RE = re.compile(
    r"(습니다|입니다|있습니다|했습니다|하였습니다|드립니다|말씀드리|제출|결정|상정|의결|선포|보고|설명|표결|투표|결과를|재석|의석|감사)"
)
_PAREN_STYLE_RE = re.compile(r"\([^)]+\)")
LEADING_ROLE_TOKEN_RE = re.compile(
    r"^(?P<title>의원|위원|의장|위원장)"
    r"(?:님|이|은|는|께서|께|도|으로서|으로는|으로|만|까지|부터)?\s*(?P<body>.+)$"
)
LEADING_ANNOTATED_ROLE_RE = re.compile(
    rf"^(?:[{re.escape(BULLET_CHARS)}]\s*)?[가-힣]{{2,40}}\s*\(\s*[가-힣]{{2,4}}\s*\)\s*(?P<tail>.+)$"
)


def _should_merge_wrapped_lines(prev_line: str, next_line: str) -> bool:
    prev = normalize_text(prev_line)
    nxt = normalize_text(next_line)
    if not prev or not nxt:
        return False

    # 괄호 블록이 닫히지 않은 상태면 다음 줄을 같은 발화로 이어 붙인다.
    prev_open = prev.count("(") + prev.count("[") + prev.count("（")
    prev_close = prev.count(")") + prev.count("]") + prev.count("）")
    if prev_open > prev_close:
        return True

    # 문장 경계가 확실한 경우는 나누지 않는다.
    if re.search(r"[\.!?]$", prev):
        return False
    if TIME_MARKER_RE.match(nxt):
        return False
    if _looks_like_agenda_item(nxt):
        return False
    if AGENDA_LIST_WRAP_RE.match(nxt):
        return False
    if _is_agenda_trailing_token_line(nxt):
        return False
    if re.fullmatch(r"\d+\)", nxt):
        return False
    if re.fullmatch(r"\d+", nxt):
        return False
    if re.fullmatch(r"[=․·\-]{2,}", nxt):
        return False

    if re.search(r"[\.!?]\)\s*$", prev):
        return False

    # 시작 괄호만 있는 독립 라인은 문장 경계로 본다.
    if nxt.startswith("(") and nxt.endswith(")") and not UNSPECIFIED_INLINE_RESPONSE_RE.search(nxt):
        return False

    return True


def _should_join_verbal_boundary(prev_token: str, next_token: str) -> bool:
    if next_token not in _JOIN_VERB_ENDING_TOKENS:
        return False
    if not re.fullmatch(r".*[가-힣]", prev_token):
        return False
    if prev_token.endswith(
        (
            "은",
            "는",
            "이",
            "가",
            "을",
            "를",
            "와",
            "과",
            "의",
            "에",
            "에서",
            "까지",
            "부터",
            "도",
            "라도",
            "만",
        )
    ):
        return False
    return True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha1_short(value: str, length: int = 16) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def normalize_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _strip_page_noise(text: str) -> str:
    # PDF 페이지 상단/중간에 반복되는 회차·일자·쪽수 노이즈 제거
    cleaned = PAGE_META_NOISE_RE.sub("", text, count=1)
    cleaned = PAGE_META_NOISE_PREFIX_RE.sub("", cleaned, count=1)
    cleaned = PAGE_INLINE_NOISE_RE.sub("", cleaned, count=1)
    cleaned = PAGE_TRAILING_PNUM_RE.sub("", cleaned, count=1)
    cleaned = re.sub(r"^\n{3,}", "", cleaned)
    return cleaned


def _strip_page_header(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text

    idx = 0
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx >= len(lines):
        return ""

    if PAGE_HEADER_RE.fullmatch(lines[idx].strip()):
        idx += 1
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
    # 회의명/회차/차(일자) 헤더가 첫 행에 끼어 있을 때도 제거
    while idx < len(lines):
        if PAGE_META_NOISE_RE.match(lines[idx]) or PAGE_INLINE_NOISE_RE.match(lines[idx]):
            idx += 1
            while idx < len(lines) and not lines[idx].strip():
                idx += 1
            continue
        break

    return "\n".join(lines[idx:]).strip()


def _normalize_space(text: str) -> str:
    text = re.sub(r"\)\s*(?=[가-힣A-Za-z0-9])", ") ", text)
    text = re.sub(r"\]\s*(?=[가-힣A-Za-z0-9])", "] ", text)
    text = re.sub(r"(?<=[가-힣0-9])(?=\()", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = _repair_korean_spacing(text)
    return text


def _span_end_token(text: str) -> str:
    matches = re.findall(r"[가-힣]+", text)
    return matches[-1] if matches else ""


def _span_start_token(text: str) -> str:
    matches = re.findall(r"[가-힣]+", text)
    return matches[0] if matches else ""


def _should_join_without_space(prev: str, next_text: str) -> bool:
    prev_token = _span_end_token(prev)
    next_token = _span_start_token(next_text)
    if not prev_token or not next_token:
        return False

    if prev_token in _STANDALONE_SINGLE_CHARS:
        return False

    if next_token in _JOIN_PARTICLES:
        return True

    if prev_token == "보" and next_token.startswith("고드리"):
        return True
    if prev_token.endswith("보") and next_token.startswith("고"):
        return True
    if prev_token.endswith("획") and next_token.startswith("서"):
        return True
    if prev_token.endswith("합니") and next_token.startswith("다"):
        return True
    if prev_token.endswith("습") and next_token.startswith("니다"):
        return True
    if prev_token in {"고", "서"} and next_token.startswith("드리"):
        return True
    if prev_token in _JOIN_PREFIX_PAIRS and next_token.startswith(_JOIN_PREFIX_PAIRS[prev_token]):
        return True
    if prev_token.endswith("하도") and next_token.startswith("록"):
        return True
    if _should_join_verbal_boundary(prev_token, next_token):
        return True
    if len(prev_token) == 1:
        return True
    return False


def _strip_trailing_agenda_garbage(text: str) -> str:
    if _is_meta_stage_line(text):
        return ""

    cleaned = re.sub(AGENDA_META_INLINE_RE, "", text)
    cleaned = re.sub(AGENDA_NUM_SERIES_RE, "", cleaned)
    cleaned = re.sub(r"\s*\(\s*\d{1,2}\s*시\s*\d{1,2}\s*분[^)]*\)\s*$", "", cleaned)
    cleaned = re.sub(r"\s*실음\)?\s*$", "", cleaned)

    if AGENDA_ENDS_WITH_NUMBERISH_RE.match(cleaned):
        cleaned = cleaned.strip()
        while AGENDA_ENDS_WITH_NUMBERISH_RE.match(cleaned):
            cleaned = re.sub(r"\s*\d+\)\s*$", "", cleaned)
        cleaned = cleaned.strip()

    return normalize_text(cleaned)


def _is_meta_stage_line(line: str) -> bool:
    text = normalize_text(line)
    if not text:
        return False
    if REPORT_END_FRAGMENT_RE.match(text):
        return True
    if APPENDIX_FRAGMENT_RE.match(text):
        return True
    if SPEAKER_LIST_META_RE.match(text):
        return True
    return False


def _split_by_sentence_endings(text: str) -> list[str]:
    text = _normalize_inline_parenthesis_boundary(normalize_text(text))
    if not text:
        return []

    # 1) 종결표점 기준 분할 (휴리스틱한 종결어미 목록 사용 X)
    sentence_chunks = [
        chunk.strip() for chunk in re.split(r"(?<=[\.!?])\s+", text) if chunk.strip()
    ]
    if not sentence_chunks:
        sentence_chunks = [text]

    return sentence_chunks


def _append_fragment(prev: str, next_text: str) -> str:
    prev = _normalize_space(prev)
    next_text = normalize_text(next_text)
    if not prev:
        return next_text
    if not next_text:
        return prev

    if _should_join_without_space(prev, next_text):
        return _normalize_space(f"{prev}{next_text}")

    return f"{prev} {next_text}"


def _repair_korean_spacing(text: str) -> str:
    cleaned = text
    # OCR 줄바꿈으로 잘못 분리된 조사/어미 조각을 붙임
    cleaned = re.sub(r"\b(보)\s+(고드리)", r"\1\2", cleaned)

    tokens = cleaned.split()
    if len(tokens) < 2:
        return cleaned

    def only_hangul(token: str) -> str:
        return re.sub(r"[^가-힣]", "", token)

    def should_merge(prev_token: str, next_token: str) -> bool:
        prev = only_hangul(prev_token)
        nxt = only_hangul(next_token)
        if not prev or not nxt:
            return False

        if prev in _STANDALONE_SINGLE_CHARS:
            return False

        if nxt in _JOIN_PARTICLES:
            return True
        if prev in _JOIN_PREFIX_PAIRS and nxt.startswith(_JOIN_PREFIX_PAIRS[prev]):
            return True
        if prev == "보" and nxt.startswith("고드리"):
            return True
        if prev.endswith("보") and nxt.startswith("고"):
            return True
        if prev.endswith("획") and nxt.startswith("서"):
            return True
        if _should_join_verbal_boundary(prev, nxt):
            return True
        if prev.endswith("합니") and nxt.startswith("다"):
            return True
        if prev.endswith("습") and nxt.startswith("니다"):
            return True
        if prev in {"고", "서"} and nxt.startswith("드리"):
            return True
        if prev.endswith("하도") and nxt.startswith("록"):
            return True
        if len(prev) == 1:
            return True
        return False

    merged: list[str] = []
    for token in tokens:
        if merged and should_merge(merged[-1], token):
            merged[-1] = f"{merged[-1]}{token}"
        else:
            merged.append(token)

    return " ".join(merged)


def _strip_parenthetical_prefix(line: str) -> str:
    changed = True
    while changed:
        before = line
        line = re.sub(rf"^[{re.escape(BULLET_CHARS)}]\s*", "", line)
        line = re.sub(CLOSED_BRACKET_PREFIX_RE, "", line)
        line = re.sub(PAREN_LEADING_RE, "", line)
        line = re.sub(SQUARE_LEADING_RE, "", line)
        line = re.sub(FULLWIDTH_BRACKET_LEADING_RE, "", line)
        line = re.sub(QUOTE_MARK_PREFIX_RE, "", line)
        changed = line != before
    return normalize_text(line)


def _strip_prefixes(text: str) -> str:
    body = normalize_text(text)
    if not body:
        return body

    body = _strip_parenthetical_prefix(body)
    # 위원회명만 제거하고 직함은 유지하여 name에 포함되게 한다.
    body = COMMITTEE_PREFIX_RE.sub("", body)
    return normalize_text(body)


def _looks_like_title(token: str) -> bool:
    if token in KNOWN_TITLES:
        return True
    if token.endswith(
        ("의원", "위원", "의장", "위원장", "대리", "총리", "전문위원", "장관", "차관", "원장")
    ):
        return True
    return False


def _split_compact_title_name_token(token: str) -> tuple[str, str] | None:
    compact = normalize_text(token)
    compact = re.sub(rf"^[{re.escape(BULLET_CHARS)}]\s*", "", compact)
    if not compact or len(compact) < 5:
        return None

    for name_len in (4, 3, 2):
        if len(compact) <= name_len:
            continue
        title = compact[:-name_len]
        name = compact[-name_len:]
        if _looks_like_title(title) and _looks_like_name(name):
            return title, name
    return None


def _looks_like_name(token: str) -> bool:
    if not token or len(token) < 2 or len(token) > 4:
        return False
    if not re.fullmatch(r"[가-힣]+", token):
        return False
    if token.endswith(("대리", "위원", "의원", "의장", "위원장", "장관", "총리", "원장")):
        return False
    if token in {"위원", "의원", "의장", "위원장"}:
        return False
    if token in NAME_BLACKLIST_PREFIXES:
        return False
    if any(token.startswith(prefix) for prefix in NAME_BLACKLIST_PREFIXES):
        return False
    return True


def _is_speaker_header_line(line: str) -> bool:
    target = normalize_text(line)
    if not target:
        return False
    if _is_noise_or_agenda(target):
        return False

    stripped = _strip_prefixes(target)
    if _extract_unspecified_response(stripped):
        return True
    return _extract_name_and_text(stripped)[0] is not None


def _strip_name_suffixes(text: str) -> str:
    rest = normalize_text(text)
    for suffix in NAME_SUFFIX_PATTERNS:
        if rest.startswith(suffix):
            return normalize_text(rest[len(suffix) :])
    return rest


def _strip_location_speech_prefix(text: str) -> str:
    return normalize_text(re.sub(LOC_SPEECH_PREFIX_RE, "", normalize_text(text)))


def _normalize_punctuation_noise(text: str) -> str:
    cleaned = normalize_text(text)
    cleaned = _normalize_inline_parenthesis_boundary(cleaned)
    cleaned = re.sub(r"(?:…|\.){2,}", ".", cleaned)
    cleaned = re.sub(r"[,.]{2,}", ".", cleaned)
    cleaned = re.sub(r"\s*[)\]]+\s*$", "", cleaned)
    cleaned = re.sub(r"\s*[(\[]+\s*$", "", cleaned)
    return normalize_text(cleaned)


def _normalize_inline_parenthesis_boundary(text: str) -> str:
    # `.) 한글`/`?) 한글`처럼 인터럽트 종료 뒤 본문이 붙는 패턴을 문장 경계로 복원.
    cleaned = re.sub(r"([\.!?])\s*[\)\]](?=\s*[가-힣A-Za-z0-9])", r"\1 ", text)
    cleaned = re.sub(r"([\.!?])\s*[\)\]]\s*$", r"\1", cleaned)
    return normalize_text(cleaned)


def _trim_orphan_brackets(text: str) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return cleaned

    def open_close_count(value: str) -> tuple[int, int]:
        opens = value.count("(") + value.count("[") + value.count("（")
        closes = value.count(")") + value.count("]") + value.count("）")
        return opens, closes

    # 여는 괄호 없이 남은 닫는 괄호만 제거한다.
    while cleaned and cleaned[0] in ")]":
        opens, closes = open_close_count(cleaned)
        if closes <= opens:
            break
        cleaned = normalize_text(cleaned[1:])

    while cleaned and cleaned[-1] in ")]":
        opens, closes = open_close_count(cleaned)
        if closes <= opens:
            break
        cleaned = normalize_text(cleaned[:-1])

    return normalize_text(cleaned)


def _split_leading_orphan_interjection(text: str) -> tuple[str, str] | None:
    """
    `... .) 본문` 형태에서 닫는 괄호 앞 문장을 인터럽트로 분리한다.
    """
    match = re.match(
        r"^\s*(?P<leading>[^()\[\]]{1,200}?[\.!?])\s*[\)\]]+\s*(?P<tail>[가-힣A-Za-z0-9].+)$",
        text,
    )
    if not match:
        return None

    leading = _normalize_punctuation_noise(match.group("leading"))
    tail = normalize_text(match.group("tail"))
    if not leading or not tail:
        return None
    return leading, tail


def _split_line_with_inline_unspecified(line: str) -> list[tuple[str, str, str | None]]:
    cleaned_line = normalize_text(line)
    if not cleaned_line:
        return []

    if "(" not in cleaned_line and "「" not in cleaned_line and "무기명" not in cleaned_line:
        return [("text", _normalize_inline_parenthesis_boundary(cleaned_line), None)]

    chunks: list[tuple[str, str, str | None]] = []
    pos = 0
    for match in UNSPECIFIED_INLINE_RESPONSE_RE.finditer(cleaned_line):
        before = _trim_orphan_brackets(
            _normalize_inline_parenthesis_boundary(cleaned_line[pos : match.start()])
        )
        if before:
            chunks.append(("text", before, None))

        named_person = match.group("named_person")
        named_title = match.group("named_title")
        named_quoted = match.group("named_quoted")
        named_plain = match.group("named_plain")
        bullet_person = match.group("bullet_person")
        bullet_title = match.group("bullet_title")
        bullet_quoted = match.group("bullet_quoted")
        bullet_plain = match.group("bullet_plain")
        saying1 = match.group("quoted1") or match.group("plain1")
        interjection = ""
        interjection_speaker: str | None = None
        if named_person and named_title and (named_quoted or named_plain):
            interjection_speaker = f"{normalize_text(named_person)} {named_title}"
            interjection = _normalize_punctuation_noise(named_quoted or named_plain or "")
        elif bullet_person and (bullet_quoted or bullet_plain):
            normalized_bullet_person = normalize_text(bullet_person)
            normalized_bullet_title = normalize_text(bullet_title or "")
            interjection_speaker = (
                f"{normalized_bullet_person} {normalized_bullet_title}".strip()
                if normalized_bullet_title
                else normalized_bullet_person
            )
            interjection = _normalize_punctuation_noise(bullet_quoted or bullet_plain or "")
        elif saying1:
            interjection = _normalize_punctuation_noise(saying1)

        if interjection:
            chunks.append(("unspecified", interjection, interjection_speaker))
        pos = match.end()

    tail = _trim_orphan_brackets(_normalize_inline_parenthesis_boundary(cleaned_line[pos:]))
    if tail:
        chunks.append(("text", tail, None))

    return chunks


def _extract_unspecified_response(line: str) -> tuple[str | None, str] | None:
    target = normalize_text(line)
    if not target:
        return None

    prefix_match = UNSPECIFIED_PREFIX_RESPONSE_RE.match(target)
    if prefix_match:
        text = normalize_text(prefix_match.group("text"))
        if not text:
            return None
        tokens = text.split(maxsplit=1)
        if tokens and tokens[0] in {"예", "아니요", "찬성", "반대", "기권"}:
            return None, tokens[0]
        return None, text

    if target.startswith("(") and target.endswith(")"):
        inner = normalize_text(target[1:-1])
        # Explicit speaker 복원은 구조 신호(◯ 시작)가 있는 괄호 발화에만 적용한다.
        # 인용형 무기명 인터럽트: (「...」 하는 의원 있음) 에는 적용하면 안 된다.
        if BULLET_CHAR_RE.match(inner):
            inner = re.sub(rf"^[{re.escape(BULLET_CHARS)}]\s*", "", inner)
            explicit_name, explicit_text = _extract_explicit_speaker_and_text(inner)
            if explicit_name and explicit_text:
                return explicit_name, explicit_text

    match = UNSPECIFIED_RESPONSE_RE.match(target)
    if not match:
        return None

    named_person = match.group("named_person")
    named_title = match.group("named_title")
    named_quoted = match.group("named_quoted")
    named_plain = match.group("named_plain")
    bullet_person = match.group("bullet_person")
    bullet_title = match.group("bullet_title")
    bullet_quoted = match.group("bullet_quoted")
    bullet_plain = match.group("bullet_plain")

    if named_person and named_title and (named_quoted or named_plain):
        return (
            f"{normalize_text(named_person)} {named_title}",
            normalize_text(named_quoted or named_plain or ""),
        )

    if bullet_person and (bullet_quoted or bullet_plain):
        normalized_bullet_person = normalize_text(bullet_person)
        normalized_bullet_title = normalize_text(bullet_title or "")
        speaker_name = (
            f"{normalized_bullet_person} {normalized_bullet_title}".strip()
            if normalized_bullet_title
            else normalized_bullet_person
        )
        return speaker_name, normalize_text(bullet_quoted or bullet_plain or "")

    saying1 = match.group("quoted1") or match.group("plain1")

    if saying1:
        return None, _normalize_punctuation_noise(saying1)

    return None


def _is_agenda_trailing_token_line(line: str) -> bool:
    normalized = normalize_text(line)
    if not normalized:
        return False

    compact = re.sub(r"\s+", "", normalized)
    if not compact:
        return False

    if compact.startswith("실음"):
        return True
    if "의안번호" in compact:
        return True
    if (
        "찬반의원성명" in compact
        or "찬반의원성명은끝에실음" in compact
        or "전자투표찬반의원성명" in compact
    ):
        return True
    if "번호" in compact and any(char.isdigit() for char in compact):
        return True
    if re.fullmatch(r"\d+\)\)?(?:\d+\)\)?)*", compact):
        return True
    return False


def _speaker_start_index(lines: list[str]) -> int:
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if TIME_MARKER_RE.match(line):
            idx += 1
            continue
        if _is_noise_or_agenda(line):
            stripped = _strip_prefixes(line)
            name, _ = _extract_name_and_text(stripped)
            if name or _extract_unspecified_response(line):
                break
            idx += 1
            continue
        break
    return idx


def _extract_explicit_speaker_and_text(text: str) -> tuple[str | None, str]:
    txt = normalize_text(text)
    if not txt:
        return None, ""

    annotated_role_match = LEADING_ANNOTATED_ROLE_RE.match(txt)
    if annotated_role_match:
        tail = normalize_text(annotated_role_match.group("tail"))
        tail_name, tail_text = _extract_explicit_speaker_and_text(tail)
        if tail_name and tail_text:
            return tail_name, tail_text
        bare_tail = re.match(r"^(?P<name>[가-힣]{2,4})\s+(?P<body>.+)$", tail)
        if bare_tail and _looks_like_name(bare_tail.group("name")):
            bare_body = normalize_text(bare_tail.group("body"))
            if bare_body:
                return bare_tail.group("name"), bare_body

    tokens = txt.split()
    if len(tokens) < 2:
        return None, ""

    # OCR 분절 복구:
    # - 외교통일위원 장대리 이용선 -> 외교통일위원장대리 이용선
    # - 교육위원 장 대리 백승아 -> 교육위원장대리 백승아
    if len(tokens) >= 3 and tokens[0].endswith("위원") and tokens[1] == "장대리":
        if _looks_like_name(tokens[2]):
            rest = _strip_location_speech_prefix(_strip_name_suffixes(" ".join(tokens[3:])))
            if rest:
                return f"{tokens[0]}장대리 {tokens[2]}", _normalize_space(rest)
    if (
        len(tokens) >= 4
        and tokens[0].endswith("위원")
        and tokens[1] == "장"
        and tokens[2] == "대리"
    ):
        if _looks_like_name(tokens[3]):
            rest = _strip_location_speech_prefix(_strip_name_suffixes(" ".join(tokens[4:])))
            if rest:
                return f"{tokens[0]}장대리 {tokens[3]}", _normalize_space(rest)

    # 무공백 직함+이름 (예: 대통령이재명, 의사국의사과신승우)
    compact = _split_compact_title_name_token(tokens[0])
    if compact:
        title, name = compact
        rest = _strip_location_speech_prefix(_strip_name_suffixes(" ".join(tokens[1:])))
        if rest:
            return f"{title} {name}", _normalize_space(rest)

    # 직함 이름
    if _looks_like_title(tokens[0]) and _looks_like_name(tokens[1]):
        rest = _strip_location_speech_prefix(_strip_name_suffixes(" ".join(tokens[2:])))
        if rest:
            return f"{tokens[0]} {tokens[1]}", _normalize_space(rest)

    # 이름 직함
    if _looks_like_name(tokens[0]) and _looks_like_title(tokens[1]):
        rest = _strip_location_speech_prefix(_strip_name_suffixes(" ".join(tokens[2:])))
        if rest:
            return f"{tokens[0]} {tokens[1]}", _normalize_space(rest)

    return None, ""


def _extract_name_and_text(text: str) -> tuple[str | None, str]:
    explicit_name, explicit_text = _extract_explicit_speaker_and_text(text)
    if explicit_name and explicit_text:
        return explicit_name, explicit_text

    txt = normalize_text(text)
    if not txt:
        return None, ""

    tokens = txt.split()
    if len(tokens) < 2:
        return None, ""

    # 기존 방식 (이름 먼저, 직함·호칭은 본문으로 오더라도 suffix 패턴으로 제거)
    m = re.match(r"^([가-힣]{2,4})\s+(.+)$", txt)
    if not m:
        return None, ""

    name = m.group(1)
    rest = _strip_location_speech_prefix(_strip_name_suffixes(m.group(2)))

    if (
        "개정법률" in rest
        or "투표 의원" in rest
        or "투표 결과" in rest
        or "법률안" in rest
        or "의안번호" in rest
    ):
        return None, ""

    if not _looks_like_name(name) or not rest:
        return None, ""
    return name, _normalize_space(rest)


def _repair_bare_name_boundary(name: str, text: str) -> tuple[str, str]:
    normalized_name = normalize_text(name)
    normalized_text = normalize_text(text)
    if not normalized_text:
        return normalized_name, normalized_text

    if not re.fullmatch(r"[가-힣]{2,4}", normalized_name):
        return normalized_name, normalized_text

    minister_interjection = re.match(
        r"^(?P<title>[가-힣]{2,20}(?:장관|차관))\s+"
        r"(?:국무위원석|의석|발언대 옆|단하|단상|의석\s*단말기)\s*(?:에서|상)\s*[―—\-]\s*"
        r"(?P<body>.+)$",
        normalized_text,
    )
    if minister_interjection:
        repaired_body = normalize_text(minister_interjection.group("body"))
        if repaired_body:
            repaired_name = f"{normalized_name} {minister_interjection.group('title')}"
            return repaired_name, repaired_body

    match = LEADING_ROLE_TOKEN_RE.match(normalized_text)
    if not match:
        return normalized_name, normalized_text

    repaired_body = normalize_text(match.group("body"))
    if not repaired_body:
        return normalized_name, normalized_text

    repaired_name = f"{normalized_name} {match.group('title')}"
    return repaired_name, repaired_body


def _is_noise_or_agenda(line: str) -> bool:
    line = normalize_text(line)
    if not line:
        return True
    if re.match(
        r"^\s*(?:\d+\s+)?제?\s*\d+\s*회.*제?\s*\d+\s*차.*\(\s*\d{4}\s*년?\s*\d{1,2}\s*월?\s*\d{1,2}\s*일?\s*\)",
        line,
    ):
        return True
    if re.match(r"^[oOㅇ○◯]\s+", line):
        return True
    if HEADER_MARKER_RE.match(line):
        return True
    if TIME_MARKER_RE.match(line):
        return True
    if AGENDA_LIST_ITEM_RE.match(line):
        return True
    if AGENDA_LIST_WRAP_RE.match(line):
        return True
    if _is_meta_stage_line(line):
        return True
    if _is_agenda_trailing_token_line(line):
        return True
    if ANNEX_SECTION_RE.match(line):
        return True
    if re.fullmatch(r"\d+", line):
        return True
    if re.fullmatch(r"\d+\)", line):
        return True
    if AGENDA_ITEM_RE.match(line):
        return True
    if re.fullmatch(r"[=․·\-]{2,}", line):
        return True
    return False


def _filter_block_session_lines(lines: list[str], in_session: bool) -> tuple[list[str], bool]:
    filtered: list[str] = []
    current_in_session = in_session

    for line in lines:
        if TIME_MARKER_RE.match(line):
            if _is_session_open_marker(line):
                current_in_session = True
            elif _is_session_close_marker(line):
                current_in_session = False
                break
            continue

        if current_in_session:
            filtered.append(line)

    return filtered, current_in_session


def _drop_between_triple_newlines(lines: list[str]) -> list[str]:
    filtered: list[str] = []
    blank_run = 0
    skip_mode = False

    for raw_line in lines:
        line = normalize_text(raw_line)
        if not line:
            blank_run += 1
            if blank_run >= 3:
                skip_mode = True
            continue

        blank_run = 0

        if skip_mode:
            if _is_speaker_header_line(line):
                skip_mode = False
            else:
                continue

        if not skip_mode:
            filtered.append(line)

    return filtered


def _join_wrapped_lines(lines: list[str]) -> list[str]:
    normalized = [normalize_text(raw_line) for raw_line in lines]
    if not normalized:
        return []

    merged: list[str] = []
    pending_blank = 0
    for raw_line in normalized:
        if not raw_line:
            pending_blank += 1
            continue

        if pending_blank >= 3:
            merged.extend(["" for _ in range(pending_blank)])
            pending_blank = 0

        if not merged:
            merged.append(raw_line)
            pending_blank = 0
            continue

        if pending_blank:
            if _should_merge_wrapped_lines(merged[-1], raw_line):
                merged[-1] = _append_fragment(merged[-1], raw_line)
            else:
                if pending_blank:
                    merged.extend(["" for _ in range(pending_blank)])
                    merged.append(raw_line)
            pending_blank = 0
            continue

        if _should_merge_wrapped_lines(merged[-1], raw_line):
            merged[-1] = _append_fragment(merged[-1], raw_line)
        else:
            merged.append(raw_line)

        pending_blank = 0

    return merged


def _trim_leading_page_artifacts(lines: list[str]) -> list[str]:
    start = 0
    while start < len(lines):
        line = normalize_text(lines[start])
        if not line:
            start += 1
            continue

        if (
            ANNEX_SECTION_RE.match(line)
            or AGENDA_LIST_ITEM_RE.match(line)
            or AGENDA_LIST_WRAP_RE.match(line)
            or TIME_MARKER_RE.match(line)
        ):
            start += 1
            continue

        if _is_noise_or_agenda(line):
            stripped = _strip_prefixes(line)
            name, _ = _extract_name_and_text(stripped)
            if name or _extract_unspecified_response(line):
                break
            start += 1
            continue

        break

    return [normalize_text(x) for x in lines[start:] if normalize_text(x)]


def _is_unspecified_followup(line: str) -> bool:
    return bool(UNSPECIFIED_FOLLOWUP_RE.match(normalize_text(line)))


def _looks_like_agenda_item(line: str) -> bool:
    return bool(AGENDA_LIST_ITEM_RE.match(normalize_text(line)))


def _is_session_open_marker(line: str) -> bool:
    line = normalize_text(line)
    return bool(TIME_MARKER_RE.match(line) and SESSION_OPEN_MARKER_RE.search(line))


def _is_session_close_marker(line: str) -> bool:
    line = normalize_text(line)
    return bool(TIME_MARKER_RE.match(line) and SESSION_CLOSE_MARKER_RE.search(line))


def _looks_like_speaker_block(block: str) -> bool:
    lines = [normalize_text(x) for x in block.splitlines() if normalize_text(x)]
    if not lines:
        return False

    start = _speaker_start_index(lines)
    if start >= len(lines):
        return False

    head = _strip_prefixes(lines[start])
    if _extract_unspecified_response(head):
        return True
    return _extract_name_and_text(head)[0] is not None


def _extract_speaker_turns(lines: list[str], start: int) -> list[tuple[str, str]]:
    if start >= len(lines):
        return []

    head = _strip_prefixes(lines[start])
    head = _strip_trailing_agenda_garbage(head)
    name, text = _extract_name_and_text(head)
    if not name and not text:
        unspecified = _extract_unspecified_response(lines[start])
        if not unspecified:
            return []
        unspecified_name, unspecified_text = unspecified
        name = unspecified_name or SPEAKER_UNKNOWN
        text = unspecified_text
    else:
        if not text:
            text = ""

    turns: list[tuple[str, str]] = []
    current_name = name or SPEAKER_UNKNOWN
    current_text = ""
    after_unspecified = False

    def flush_current() -> None:
        nonlocal current_text
        if not current_text:
            return
        text_to_emit = _normalize_punctuation_noise(_normalize_space(current_text))
        if text_to_emit:
            turns.append((current_name, text_to_emit))
        current_text = ""

    def emit_chunks(chunks: list[tuple[str, str, str | None]]) -> None:
        nonlocal current_name, current_text, after_unspecified, turns

        for part_type, part_text, part_speaker in chunks:
            if part_type == "unspecified":
                flush_current()
                if part_text:
                    turns.append(
                        (part_speaker or SPEAKER_UNKNOWN, _normalize_punctuation_noise(part_text))
                    )
                after_unspecified = True
                continue

            part_text = _trim_orphan_brackets(_strip_parenthetical_prefix(part_text))
            if not part_text or _is_noise_or_agenda(part_text):
                continue

            if after_unspecified:
                current_text = _normalize_space(part_text)
                after_unspecified = False
                continue

            if current_text:
                current_text = _append_fragment(current_text, part_text)
            else:
                current_text = _normalize_space(part_text)

    if text:
        emit_chunks(_split_line_with_inline_unspecified(text))

    for line in lines[start + 1 :]:
        if TIME_MARKER_RE.match(line):
            if _is_session_close_marker(line):
                break
            continue
        if _looks_like_agenda_item(line):
            break
        clean = _strip_trailing_agenda_garbage(line)
        if not clean:
            continue

        is_bullet_switch_line = bool(re.match(rf"^\s*[{re.escape(BULLET_CHARS)}]\s*", clean))
        if is_bullet_switch_line:
            prefixed = _strip_prefixes(clean)
            switched_name, switched_text = _extract_explicit_speaker_and_text(prefixed)
            if switched_name and switched_text:
                flush_current()
                maybe_leading = _split_leading_orphan_interjection(switched_text)
                if maybe_leading:
                    leading_text, switched_text = maybe_leading
                    turns.append((current_name, leading_text))
                current_name = switched_name
                after_unspecified = False
                emit_chunks(_split_line_with_inline_unspecified(switched_text))
                continue

        if _is_noise_or_agenda(clean):
            continue

        unspecified = _extract_unspecified_response(clean)
        if unspecified:
            flush_current()
            unspecified_name, unspecified_text = unspecified
            turns.append(
                (
                    unspecified_name or SPEAKER_UNKNOWN,
                    _normalize_punctuation_noise(unspecified_text),
                )
            )
            after_unspecified = True
            continue

        emit_chunks(_split_line_with_inline_unspecified(clean))

    flush_current()
    return turns


def split_blocks(pages: list[str]) -> list[str]:
    blocks: list[str] = []
    normalized_pages = [normalize_text(raw) for raw in pages]
    merged = "\n".join(raw.strip() for raw in normalized_pages if raw)
    if not merged:
        return blocks

    matches = list(SPEAKER_BLOCK_START_RE.finditer(merged))
    if not matches:
        if merged.strip():
            blocks.append(merged.strip())
        return blocks

    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(merged)
        chunk = normalize_text(merged[start:end])
        if not chunk:
            continue
        blocks.append(chunk)
    return blocks


def build_transcripts(blocks: list[str], min_len: int = MIN_TRANSCRIPT_LEN) -> list[dict[str, Any]]:
    transcripts: list[dict[str, Any]] = []
    transcript_id = 1
    in_session = True

    for block in blocks:
        lines = _join_wrapped_lines(block.splitlines())
        if not lines:
            continue

        lines, in_session = _filter_block_session_lines(lines, in_session)
        if not lines:
            continue

        lines = _drop_between_triple_newlines(lines)
        if not lines:
            continue

        lines = _trim_leading_page_artifacts(lines)
        if not lines:
            continue

        block_text = "\n".join(lines)
        if not _looks_like_speaker_block(block_text):
            continue

        lines = [normalize_text(x) for x in lines if normalize_text(x)]
        start = _speaker_start_index(lines)
        if start >= len(lines):
            continue

        turns = _extract_speaker_turns(lines, start)
        if not turns:
            continue

        for turn_name, turn_text in turns:
            turn_name, turn_text = _repair_bare_name_boundary(turn_name, turn_text)
            if not turn_text:
                continue
            for segment in _split_by_sentence_endings(turn_text):
                segment = _normalize_space(segment)
                segment = _normalize_punctuation_noise(segment)
                if not segment or not re.search(r"[가-힣a-zA-Z0-9]", segment):
                    continue

                is_session_close = "산회를 선포" in segment or "폐식을 선포" in segment

                transcripts.append(
                    {
                        "id": str(transcript_id),
                        "name": turn_name,
                        "speaker_name": turn_name,
                        "text": segment,
                        "start_ms": None,
                        "end_ms": None,
                        "is_sparse": len(segment) < min_len,
                    }
                )
                transcript_id += 1

                if is_session_close:
                    in_session = False
                    break
            if not in_session:
                break

    return transcripts


def make_participants(transcripts: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {t["name"] for t in transcripts if t.get("name") and t.get("name") != SPEAKER_UNKNOWN}
    )


def parse_meeting_meta(source_path: Path) -> tuple[str, str | None, str]:
    stem = source_path.stem
    date_match = re.search(r"\((\d{4}\.\d{2}\.\d{2})\)", stem)
    source_date = date_match.group(1) if date_match else None

    title = stem
    if source_date:
        title = title.replace(f" ({source_date})", "").replace(f"({source_date})", "").strip()
    meeting_id = f"raw-pdf-{sha1_short(str(source_path.resolve()))}"
    return title, source_date, meeting_id


def to_file_stem(value: str) -> str:
    stem = re.sub(r"[\\/\n\r\t:*?\"<>|]+", "_", value)
    stem = re.sub(r"\s+", "_", stem).strip("._-")
    return stem or "document"


def _detect_pdf_extractor() -> str:
    try:
        import pdfplumber  # type: ignore

        _ = pdfplumber
        return "pdfplumber"
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pdfplumber가 필요합니다. pip install pdfplumber") from exc


def _extract_pdf_pages(
    path: Path,
    *,
    extractor_name: str,
    use_layout: bool,
    x_tolerance: float,
    y_tolerance: float,
    use_fallback_extract: bool,
) -> list[str]:
    if extractor_name != "pdfplumber":
        raise RuntimeError(f"지원하지 않는 파서입니다: {extractor_name}")

    import pdfplumber  # type: ignore

    result: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            if use_layout:
                page_text = page.extract_text(
                    x_tolerance=x_tolerance, y_tolerance=y_tolerance, layout=True
                )
            else:
                page_text = page.extract_text()

            if use_fallback_extract and not page_text and use_layout:
                page_text = page.extract_text()

            result.append(page_text or "")
    return result


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def write_json(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


@dataclass
class DatasetRecord:
    source_file: str
    meeting_info: dict[str, Any]
    raw_pages: list[dict[str, Any]]
    transcripts: list[dict[str, Any]]
    transform_notes: dict[str, Any]

    def to_raw(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "meeting_info": self.meeting_info,
            "transform_notes": self.transform_notes,
            "raw_pages": self.raw_pages,
        }

    def to_normalized(self) -> dict[str, Any]:
        return {
            "meeting_info": self.meeting_info,
            "transcripts": self.transcripts,
            "transform_notes": self.transform_notes,
        }

    def to_sample(self) -> dict[str, Any]:
        return {
            "meeting_info": self.meeting_info,
            "transcripts": [
                {
                    "name": x["name"],
                    "text": x["text"],
                    "start_ms": x["start_ms"],
                    "end_ms": x["end_ms"],
                }
                for x in self.transcripts
            ],
        }


def process_file(
    path: Path,
    min_transcript_len: int,
    extractor_name: str,
    use_layout: bool,
    x_tolerance: float,
    y_tolerance: float,
    use_fallback_extract: bool,
) -> DatasetRecord:
    title, source_date, meeting_id = parse_meeting_meta(path)
    pages = _extract_pdf_pages(
        path,
        extractor_name=extractor_name,
        use_layout=use_layout,
        x_tolerance=x_tolerance,
        y_tolerance=y_tolerance,
        use_fallback_extract=use_fallback_extract,
    )

    raw_pages = [
        {"page": idx, "text": _strip_page_header(normalize_text(_strip_page_noise(text)))}
        for idx, text in enumerate(pages, start=1)
    ]
    blocks = split_blocks([item["text"] for item in raw_pages])
    transcripts = build_transcripts(blocks, min_len=min_transcript_len)
    participants = make_participants(transcripts)

    meeting_info = {
        "source_file": str(path.name),
        "meeting_id": meeting_id,
        "title": title,
        "source_date": source_date,
        "participants": participants,
        "duration_ms": None,
        "raw_metadata": {
            "path": str(path.resolve()),
            "page_count": len(raw_pages),
            "parser": extractor_name,
            "processed_at": _now_iso(),
        },
    }

    return DatasetRecord(
        source_file=str(path),
        meeting_info=meeting_info,
        raw_pages=raw_pages,
        transcripts=transcripts,
        transform_notes={
            "parser": extractor_name,
            "transcript_count": len(transcripts),
            "min_transcript_len": min_transcript_len,
            "processed_at": _now_iso(),
            "source_date_detected": source_date,
        },
    )


def _process_file_worker(payload: tuple[str, int, str, bool, float, float, bool]) -> DatasetRecord:
    (
        path_str,
        min_transcript_len,
        extractor_name,
        use_layout,
        x_tolerance,
        y_tolerance,
        use_fallback_extract,
    ) = payload
    return process_file(
        path=Path(path_str),
        min_transcript_len=min_transcript_len,
        extractor_name=extractor_name,
        use_layout=use_layout,
        x_tolerance=x_tolerance,
        y_tolerance=y_tolerance,
        use_fallback_extract=use_fallback_extract,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="회의록 PDF를 generate_pr 입력으로 변환")
    parser.add_argument("--input-dir", default="backend/notebook/data/raw", help="PDF 입력 폴더")
    parser.add_argument("--output-dir", default="backend/notebook/datasets", help="출력 폴더")
    parser.add_argument("--raw-output", default="raw_transcripts_raw.jsonl", help="원문 JSONL")
    parser.add_argument(
        "--normalized-output",
        default="raw_transcripts_normalized.jsonl",
        help="정규화 JSONL",
    )
    parser.add_argument("--samples-output", default="samples.json", help="샘플 JSON")
    parser.add_argument("--normalized-dir", default="normalized", help="개별 정규화 JSON 저장 폴더")
    parser.add_argument("--min-transcript-len", type=int, default=MIN_TRANSCRIPT_LEN)
    parser.add_argument("--glob", default="*.pdf")
    parser.add_argument(
        "--workers", type=int, default=DEFAULT_MAX_WORKERS, help="PDF 병렬 처리 워커 수"
    )
    parser.add_argument(
        "--no-layout", action="store_true", help="pdfplumber layout 모드를 끄고 더 빠르게 추출"
    )
    parser.add_argument(
        "--no-fallback-extract",
        action="store_true",
        help="layout 실패 시 기본 추출 fallback 비활성화",
    )
    parser.add_argument("--x-tolerance", type=float, default=1.2, help="layout 추출 x_tolerance")
    parser.add_argument("--y-tolerance", type=float, default=2.0, help="layout 추출 y_tolerance")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    extractor_name = _detect_pdf_extractor()
    pdfs = sorted(input_dir.glob(args.glob))
    if not pdfs:
        raise SystemExit(f"[ERROR] 입력 PDF가 없습니다: {input_dir}")

    workers = max(1, args.workers)
    use_layout = not args.no_layout
    use_fallback_extract = not args.no_fallback_extract

    raw_records: list[dict[str, Any]] = []
    normalized_records: list[dict[str, Any]] = []
    sample_records: list[dict[str, Any]] = []
    normalized_paths: list[Path] = []

    valid_pdfs = [pdf_path for pdf_path in pdfs if pdf_path.is_file()]
    payloads = [
        (
            str(pdf_path),
            args.min_transcript_len,
            extractor_name,
            use_layout,
            args.x_tolerance,
            args.y_tolerance,
            use_fallback_extract,
        )
        for pdf_path in valid_pdfs
    ]

    if workers == 1 or len(payloads) <= 1:
        records = [_process_file_worker(payload) for payload in payloads]
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
            records = list(executor.map(_process_file_worker, payloads))

    for pdf_path, record in zip(valid_pdfs, records):
        raw_records.append(record.to_raw())
        normalized_records.append(record.to_normalized())
        normalized_dir = output_dir / args.normalized_dir
        normalized_path = normalized_dir / f"{to_file_stem(pdf_path.stem)}.json"
        write_json(normalized_path, record.to_normalized())
        normalized_paths.append(normalized_path)
        sample_records.append(record.to_sample())

    raw_output = output_dir / args.raw_output
    normalized_output = output_dir / args.normalized_output
    samples_output = output_dir / args.samples_output

    write_jsonl(raw_output, raw_records)
    write_jsonl(normalized_output, normalized_records)
    with samples_output.open("w", encoding="utf-8") as f:
        json.dump(sample_records, f, ensure_ascii=False, indent=2)

    print(f"[INFO] raw       -> {raw_output}")
    print(f"[INFO] normalized-> {normalized_output}")
    print(f"[INFO] workers   -> {workers}")
    print(f"[INFO] layout    -> {use_layout}")
    print(f"[INFO] fallback  -> {use_fallback_extract}")
    for path in normalized_paths:
        print(f"[INFO] normalized -> {path}")
    print(f"[INFO] samples   -> {samples_output}")


if __name__ == "__main__":
    main()
