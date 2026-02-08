"""validate_hard_gate 테스트 — 의미 기반 검증."""

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from app.infrastructure.graph.workflows.generate_pr.nodes.gate import (
    _build_lookup,
    _embed,
    _grounded,
    _resolve_spans,
    validate_hard_gate,
)
from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState

GATE_MOD = "app.infrastructure.graph.workflows.generate_pr.nodes.gate"


# ============================================================================
# 헬퍼
# ============================================================================


def _utts(texts: list[str]) -> list[dict]:
    return [
        {"id": f"utt-{i+1}", "text": t, "speaker_name": "화자", "start_ms": 0, "end_ms": 1000}
        for i, t in enumerate(texts)
    ]


def _agenda(topic, spans, description="", decision=None):
    return {
        "topic": topic,
        "description": description,
        "evidence": [{"start_utt_id": s, "end_utt_id": e} for s, e in spans],
        "decision": decision,
    }


def _decision(content, spans, context=""):
    return {
        "content": content,
        "context": context,
        "evidence": [{"start_utt_id": s, "end_utt_id": e} for s, e in spans],
    }


def _vec(seed=0):
    rng = np.random.RandomState(seed)
    v = rng.randn(1024).astype(np.float32)
    return v / np.linalg.norm(v)


def _sim(base, seed=1, scale=0.01):
    noise = np.random.RandomState(seed).randn(1024).astype(np.float32) * scale
    v = base + noise
    return v / np.linalg.norm(v)


# ============================================================================
# _resolve_spans
# ============================================================================


class TestResolveSpans:
    def test_basic(self):
        id_text, ordered = _build_lookup(_utts(["Redis 도입", "캐시 전략", "결론"]))
        result = _resolve_spans(
            [{"start_utt_id": "utt-1", "end_utt_id": "utt-2"}], id_text, ordered
        )
        assert "Redis" in result
        assert "캐시" in result
        assert "결론" not in result

    def test_invalid_span_skipped(self):
        id_text, ordered = _build_lookup(_utts(["텍스트"]))
        assert _resolve_spans(
            [{"start_utt_id": "utt-999", "end_utt_id": "utt-1"}], id_text, ordered
        ) == ""

    def test_empty(self):
        assert _resolve_spans([], {}, []) == ""


# ============================================================================
# _grounded
# ============================================================================


class TestGrounded:
    def test_similar_pass(self):
        v = _vec(0)
        assert _grounded("a", "b", {"a": v, "b": _sim(v)}, 0.7) is True

    def test_dissimilar_fail(self):
        assert _grounded("a", "b", {"a": _vec(0), "b": _vec(42)}, 0.5) is False

    def test_missing_embedding_passes(self):
        assert _grounded("a", "b", {}, 0.65) is True

    def test_empty_claim_fails(self):
        assert _grounded("", "b", {}, 0.65) is False

    def test_empty_evidence_fails(self):
        assert _grounded("a", "", {}, 0.65) is False


# ============================================================================
# _embed
# ============================================================================


class TestEmbed:
    @pytest.mark.asyncio
    async def test_unavailable(self):
        with patch(f"{GATE_MOD}.TopicEmbedder") as mock_cls:
            mock_cls.return_value.is_available = False
            assert await _embed(["text"]) == {}

    @pytest.mark.asyncio
    async def test_success(self):
        v = _vec(0)
        with patch(f"{GATE_MOD}.TopicEmbedder") as mock_cls:
            mock_cls.return_value.is_available = True
            mock_cls.return_value.embed_batch_async = AsyncMock(return_value=[v])
            result = await _embed(["text"])
            assert "text" in result

    @pytest.mark.asyncio
    async def test_dedup(self):
        with patch(f"{GATE_MOD}.TopicEmbedder") as mock_cls:
            mock_cls.return_value.is_available = True
            mock_cls.return_value.embed_batch_async = AsyncMock(return_value=[_vec(0)])
            await _embed(["same", "same", "same"])
            assert len(mock_cls.return_value.embed_batch_async.call_args.args[0]) == 1

    @pytest.mark.asyncio
    async def test_zero_vec_filtered(self):
        with patch(f"{GATE_MOD}.TopicEmbedder") as mock_cls:
            mock_cls.return_value.is_available = True
            mock_cls.return_value.embed_batch_async = AsyncMock(
                return_value=[np.zeros(1024, dtype=np.float32)]
            )
            assert "text" not in await _embed(["text"])


# ============================================================================
# validate_hard_gate
# ============================================================================


class TestValidateHardGate:
    @pytest.mark.asyncio
    async def test_empty_agendas(self):
        state = GeneratePrState(generate_pr_agendas=[])
        result = await validate_hard_gate(state)
        assert result.get("generate_pr_agendas") == []

    @pytest.mark.asyncio
    async def test_no_utterances(self):
        ag = _agenda("주제", [("utt-1", "utt-1")])
        state = GeneratePrState(generate_pr_agendas=[ag], generate_pr_transcript_utterances=[])
        result = await validate_hard_gate(state)
        assert len(result.get("generate_pr_agendas", [])) == 1

    @pytest.mark.asyncio
    async def test_valid_agenda_passes(self):
        v = _vec(0)
        state = GeneratePrState(
            generate_pr_agendas=[_agenda("Redis 캐시 도입 검토", [("utt-1", "utt-1")])],
            generate_pr_transcript_utterances=_utts(["Redis 캐시 도입을 검토합시다"]),
        )
        with patch(f"{GATE_MOD}._embed", new_callable=AsyncMock) as m:
            m.return_value = {
                "Redis 캐시 도입 검토": v,
                "Redis 캐시 도입을 검토합시다": _sim(v),
            }
            result = await validate_hard_gate(state)
        assert len(result.get("generate_pr_agendas", [])) == 1

    @pytest.mark.asyncio
    async def test_invalid_evidence_dropped(self):
        state = GeneratePrState(
            generate_pr_agendas=[_agenda("주제", [("utt-999", "utt-999")])],
            generate_pr_transcript_utterances=_utts(["텍스트"]),
        )
        with patch(f"{GATE_MOD}._embed", new_callable=AsyncMock, return_value={}):
            result = await validate_hard_gate(state)
        assert result.get("generate_pr_agendas") == []

    @pytest.mark.asyncio
    async def test_ungrounded_topic_dropped(self):
        state = GeneratePrState(
            generate_pr_agendas=[_agenda("Redis 캐시 도입", [("utt-1", "utt-1")])],
            generate_pr_transcript_utterances=_utts(["배포 일정을 확정합시다"]),
        )
        with patch(f"{GATE_MOD}._embed", new_callable=AsyncMock) as m:
            m.return_value = {
                "Redis 캐시 도입": _vec(0),
                "배포 일정을 확정합시다": _vec(42),
            }
            result = await validate_hard_gate(state)
        assert result.get("generate_pr_agendas") == []

    @pytest.mark.asyncio
    async def test_ungrounded_description_cleared(self):
        v = _vec(0)
        state = GeneratePrState(
            generate_pr_agendas=[
                _agenda("Redis 캐시 도입 검토", [("utt-1", "utt-1")], description="완전히 다른 내용")
            ],
            generate_pr_transcript_utterances=_utts(["Redis 캐시 도입을 검토합시다"]),
        )
        with patch(f"{GATE_MOD}._embed", new_callable=AsyncMock) as m:
            m.return_value = {
                "Redis 캐시 도입 검토": v,
                "Redis 캐시 도입을 검토합시다": _sim(v),
                "완전히 다른 내용": _vec(99),
            }
            result = await validate_hard_gate(state)
        ags = result.get("generate_pr_agendas", [])
        assert len(ags) == 1
        assert ags[0]["description"] == ""

    @pytest.mark.asyncio
    async def test_decision_passes(self):
        v = _vec(0)
        sv = _sim(v)
        dec = _decision("Redis 캐시를 도입하기로 결정", [("utt-1", "utt-1")], context="성능 개선")
        state = GeneratePrState(
            generate_pr_agendas=[_agenda("Redis 캐시 도입", [("utt-1", "utt-1")], decision=dec)],
            generate_pr_transcript_utterances=_utts(["Redis 캐시를 도입하기로 결정합시다"]),
        )
        with patch(f"{GATE_MOD}._embed", new_callable=AsyncMock) as m:
            m.return_value = {
                "Redis 캐시 도입": v,
                "Redis 캐시를 도입하기로 결정합시다": sv,
                "Redis 캐시를 도입하기로 결정": sv,
                "성능 개선": sv,
            }
            result = await validate_hard_gate(state)
        ags = result.get("generate_pr_agendas", [])
        assert len(ags) == 1
        assert ags[0]["decision"]["content"] == "Redis 캐시를 도입하기로 결정"

    @pytest.mark.asyncio
    async def test_ungrounded_decision_dropped(self):
        v = _vec(0)
        dec = _decision("Redis 캐시를 도입하기로 결정", [("utt-1", "utt-1")])
        state = GeneratePrState(
            generate_pr_agendas=[_agenda("배포 일정 확정", [("utt-1", "utt-1")], decision=dec)],
            generate_pr_transcript_utterances=_utts(["배포 일정을 확정합시다"]),
        )
        with patch(f"{GATE_MOD}._embed", new_callable=AsyncMock) as m:
            m.return_value = {
                "배포 일정 확정": v,
                "배포 일정을 확정합시다": _sim(v),
                "Redis 캐시를 도입하기로 결정": _vec(99),
            }
            result = await validate_hard_gate(state)
        ags = result.get("generate_pr_agendas", [])
        assert len(ags) == 1
        assert ags[0]["decision"] is None

    @pytest.mark.asyncio
    async def test_embedding_unavailable(self):
        state = GeneratePrState(
            generate_pr_agendas=[_agenda("Redis 캐시 도입 검토", [("utt-1", "utt-1")])],
            generate_pr_transcript_utterances=_utts(["Redis 캐시 도입을 검토합시다"]),
        )
        with patch(f"{GATE_MOD}._embed", new_callable=AsyncMock, return_value={}):
            result = await validate_hard_gate(state)
        assert len(result.get("generate_pr_agendas", [])) == 1

    @pytest.mark.asyncio
    async def test_decision_evidence_fallback(self):
        v = _vec(0)
        sv = _sim(v)
        dec = {"content": "Redis 캐시를 도입하기로 결정", "context": "", "evidence": []}
        state = GeneratePrState(
            generate_pr_agendas=[_agenda("Redis 캐시 도입", [("utt-1", "utt-1")], decision=dec)],
            generate_pr_transcript_utterances=_utts(["Redis 캐시를 도입하기로 결정합시다"]),
        )
        with patch(f"{GATE_MOD}._embed", new_callable=AsyncMock) as m:
            m.return_value = {
                "Redis 캐시 도입": v,
                "Redis 캐시를 도입하기로 결정합시다": sv,
                "Redis 캐시를 도입하기로 결정": sv,
            }
            result = await validate_hard_gate(state)
        ags = result.get("generate_pr_agendas", [])
        assert len(ags) == 1
        assert ags[0]["decision"] is not None

    @pytest.mark.asyncio
    async def test_ungrounded_context_cleared(self):
        v = _vec(0)
        sv = _sim(v)
        dec = _decision("Redis 캐시를 도입하기로 결정", [("utt-1", "utt-1")], context="완전히 다른 맥락")
        state = GeneratePrState(
            generate_pr_agendas=[_agenda("Redis 캐시 도입", [("utt-1", "utt-1")], decision=dec)],
            generate_pr_transcript_utterances=_utts(["Redis 캐시를 도입하기로 결정합시다"]),
        )
        with patch(f"{GATE_MOD}._embed", new_callable=AsyncMock) as m:
            m.return_value = {
                "Redis 캐시 도입": v,
                "Redis 캐시를 도입하기로 결정합시다": sv,
                "Redis 캐시를 도입하기로 결정": sv,
                "완전히 다른 맥락": _vec(99),
            }
            result = await validate_hard_gate(state)
        ags = result.get("generate_pr_agendas", [])
        assert len(ags) == 1
        assert ags[0]["decision"]["context"] == ""

    @pytest.mark.asyncio
    async def test_multiple_agendas_partial(self):
        v = _vec(0)
        state = GeneratePrState(
            generate_pr_agendas=[
                _agenda("Redis 캐시 도입 검토", [("utt-1", "utt-1")]),
                _agenda("완전히 무관한 주제", [("utt-2", "utt-2")]),
            ],
            generate_pr_transcript_utterances=_utts(["Redis 캐시 도입을 검토합시다", "배포 일정 확정"]),
        )
        with patch(f"{GATE_MOD}._embed", new_callable=AsyncMock) as m:
            m.return_value = {
                "Redis 캐시 도입 검토": v,
                "Redis 캐시 도입을 검토합시다": _sim(v),
                "완전히 무관한 주제": _vec(10),
                "배포 일정 확정": _vec(20),
            }
            result = await validate_hard_gate(state)
        ags = result.get("generate_pr_agendas", [])
        assert len(ags) == 1
        assert ags[0]["topic"] == "Redis 캐시 도입 검토"
