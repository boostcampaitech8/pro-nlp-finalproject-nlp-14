"""generate_pr Hard Gate 노드.

최소 근거 검증:
- agenda/decision에 evidence가 존재해야 함
- evidence의 utterance id가 입력 발화 목록에 존재해야 함
"""

import logging

from app.infrastructure.graph.workflows.generate_pr.state import GeneratePrState

logger = logging.getLogger(__name__)


def _is_valid_span(span: dict, valid_utt_ids: set[str]) -> bool:
    start_utt_id = str(span.get("start_utt_id", "")).strip()
    end_utt_id = str(span.get("end_utt_id", "")).strip()
    if not start_utt_id or not end_utt_id:
        return False
    return start_utt_id in valid_utt_ids and end_utt_id in valid_utt_ids


def _filter_valid_evidence(evidence: list[dict], valid_utt_ids: set[str]) -> list[dict]:
    return [span for span in evidence if _is_valid_span(span, valid_utt_ids)]


async def validate_hard_gate(state: GeneratePrState) -> GeneratePrState:
    """근거 존재/유효성 검증 후 통과 agenda만 저장 단계로 전달."""
    utterances = state.get("generate_pr_transcript_utterances", [])
    agendas = state.get("generate_pr_agendas", [])

    if not agendas:
        return GeneratePrState(generate_pr_agendas=[])

    valid_utt_ids = {
        str(item.get("id"))
        for item in utterances
        if item.get("id") is not None
    }

    if not valid_utt_ids:
        logger.warning("Hard Gate skipped: utterance ids not found")
        return GeneratePrState(generate_pr_agendas=agendas)

    passed_agendas: list[dict] = []

    for agenda in agendas:
        agenda_evidence = _filter_valid_evidence(
            list(agenda.get("evidence", []) or []),
            valid_utt_ids,
        )

        decision = agenda.get("decision")
        if decision:
            decision_evidence = _filter_valid_evidence(
                list(decision.get("evidence", []) or []),
                valid_utt_ids,
            )
            if not decision_evidence:
                # decision은 agenda evidence로 fallback
                decision_evidence = agenda_evidence

            if decision_evidence:
                decision = {
                    **decision,
                    "evidence": decision_evidence,
                }
            else:
                decision = None

        if not agenda_evidence and decision is None:
            continue

        passed_agendas.append({
            **agenda,
            "evidence": agenda_evidence,
            "decision": decision,
        })

    logger.info(
        "Hard Gate finished: input=%d, passed=%d",
        len(agendas),
        len(passed_agendas),
    )

    return GeneratePrState(generate_pr_agendas=passed_agendas)

