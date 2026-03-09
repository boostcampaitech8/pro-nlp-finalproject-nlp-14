#!/usr/bin/env python3
"""정규화 transcripts JSONL을 evaluate_pr 입력(JSONL)으로 변환.

파이프라인:
1) transcripts(json) -> utterances 정규화
2) generate_pr extraction (route -> extract -> gate)
3) evaluate_pr 입력 포맷(record_id, utterances, extraction_output) 저장

주의:
- 이 스크립트는 KG 저장(persistence) 노드를 실행하지 않습니다.
- generate_pr 추출 LLM 호출을 위해 Clova API 키가 필요합니다.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# backend/를 import path에 추가
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.graph.workflows.generate_pr.nodes.extraction import (  # noqa: E402
    extract_chunked,
    extract_single,
)
from app.infrastructure.graph.workflows.generate_pr.nodes.gate import (  # noqa: E402
    validate_hard_gate,
)
from app.infrastructure.graph.workflows.generate_pr.nodes.routing import (  # noqa: E402
    route_by_token_count,
)

load_dotenv()


class DailyQuotaExceededError(RuntimeError):
    """RPD/일일 쿼터 제한 감지 시 전체 실행 중단용 예외."""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"⚠️  라인 {line_num} JSON 파싱 실패: {e}")
    return records


def init_jsonl(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8"):
        pass


def append_jsonl_record(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False))
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())


def default_diagnostics_output_path(output_path: Path) -> Path:
    if output_path.suffix:
        return output_path.with_suffix(".diagnostics.json")
    return Path(f"{output_path}.diagnostics.json")


def make_record_id(record: dict[str, Any], index: int) -> str:
    meeting_info = record.get("meeting_info") or {}
    return str(meeting_info.get("meeting_id") or f"record-{index}")


def normalize_extraction_diagnostics(value: Any) -> dict[str, Any]:
    diagnostics = value if isinstance(value, dict) else {}
    available = isinstance(value, dict) and any(
        key in diagnostics
        for key in (
            "keyword_parse_ok_raw",
            "keyword_parse_repaired",
            "decision_array_split_count",
            "schema_violation_count",
            "repair_notes",
        )
    )
    repair_notes_raw = diagnostics.get("repair_notes", [])
    if isinstance(repair_notes_raw, list):
        repair_notes = [str(note) for note in repair_notes_raw if str(note).strip()]
    elif repair_notes_raw in (None, ""):
        repair_notes = []
    else:
        repair_notes = [str(repair_notes_raw)]

    return {
        "available": available,
        "keyword_parse_ok_raw": bool(diagnostics.get("keyword_parse_ok_raw", False)),
        "keyword_parse_repaired": bool(diagnostics.get("keyword_parse_repaired", False)),
        "decision_array_split_count": int(diagnostics.get("decision_array_split_count", 0)),
        "schema_violation_count": int(diagnostics.get("schema_violation_count", 0)),
        "repair_notes": repair_notes,
    }


def compute_strict_status(
    diagnostics: dict[str, Any],
    *,
    strict_fail_on_repair: bool,
    has_error: bool,
    has_diagnostics: bool,
) -> str:
    if has_error:
        return "fail"
    if not has_diagnostics:
        # 구버전 generate_pr는 diagnostics를 기록하지 않으므로
        # 에러가 없으면 strict pass로 간주한다.
        return "pass"

    raw_ok = bool(diagnostics.get("keyword_parse_ok_raw", False))
    repaired = bool(diagnostics.get("keyword_parse_repaired", False))

    if raw_ok and not repaired:
        return "pass"
    if not raw_ok:
        return "fail"
    if repaired and strict_fail_on_repair:
        return "fail"
    return "pass"


def build_record_diagnostics_entry(
    *,
    record_id: str,
    diagnostics: Any,
    error: str | None,
    strict_fail_on_repair: bool,
) -> dict[str, Any]:
    normalized = normalize_extraction_diagnostics(diagnostics)
    has_error = bool(error)

    if not normalized.get("available", False) and not has_error:
        normalized["keyword_parse_ok_raw"] = True
        normalized["keyword_parse_repaired"] = False
        notes = list(normalized.get("repair_notes", []))
        legacy_note = "legacy_generate_pr_no_diagnostics"
        if legacy_note not in notes:
            notes.append(legacy_note)
        normalized["repair_notes"] = notes

    strict_status = compute_strict_status(
        normalized,
        strict_fail_on_repair=strict_fail_on_repair,
        has_error=has_error,
        has_diagnostics=bool(normalized.get("available", False)),
    )

    return {
        "record_id": record_id,
        "strict_status": strict_status,
        "keyword_parse_ok_raw": normalized["keyword_parse_ok_raw"],
        "keyword_parse_repaired": normalized["keyword_parse_repaired"],
        "repair_counts": {
            "decision_array_split": normalized["decision_array_split_count"],
            "schema_violation": normalized["schema_violation_count"],
        },
        "repair_notes": normalized["repair_notes"],
        "diagnostics_available": bool(normalized.get("available", False)),
        "error": str(error or "") or None,
    }


def build_diagnostics_report(
    *,
    total_records: int,
    diagnostics_entries: dict[str, dict[str, Any]],
    strict_fail_on_repair: bool,
) -> dict[str, Any]:
    records = sorted(
        diagnostics_entries.values(),
        key=lambda item: str(item.get("record_id", "")),
    )

    strict_pass = sum(1 for entry in records if entry.get("strict_status") == "pass")
    strict_fail = sum(1 for entry in records if entry.get("strict_status") == "fail")
    strict_unknown = max(total_records - strict_pass - strict_fail, 0)

    split_total = sum(
        int(entry.get("repair_counts", {}).get("decision_array_split", 0)) for entry in records
    )
    schema_violation_total = sum(
        int(entry.get("repair_counts", {}).get("schema_violation", 0)) for entry in records
    )

    pass_rate = (strict_pass / total_records) if total_records else 0.0
    fail_rate = (strict_fail / total_records) if total_records else 0.0

    return {
        "total_records": total_records,
        "processed_records": len(records),
        "strict_fail_on_repair": strict_fail_on_repair,
        "strict": {
            "pass": strict_pass,
            "fail": strict_fail,
            "unknown": strict_unknown,
            "pass_rate": round(pass_rate, 4),
            "fail_rate": round(fail_rate, 4),
        },
        "repair_counts": {
            "decision_array_split": split_total,
            "schema_violation": schema_violation_total,
        },
        "records": records,
    }


def load_diagnostics_entries(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(f"⚠️  diagnostics 파일 로드 실패({path}): {e}")
        return {}

    records = payload.get("records", []) if isinstance(payload, dict) else []
    entries: dict[str, dict[str, Any]] = {}
    if not isinstance(records, list):
        return entries

    for item in records:
        if not isinstance(item, dict):
            continue
        record_id = str(item.get("record_id") or "").strip()
        if not record_id:
            continue
        entries[record_id] = item
    return entries


def _to_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_utterances(transcripts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """normalized transcripts를 generate_pr/evaluate 공용 utterances 스키마로 변환."""
    utterances: list[dict[str, Any]] = []

    for idx, transcript in enumerate(transcripts, start=1):
        text = str(transcript.get("text", "") or "").strip()
        if not text:
            continue

        speaker_name = (
            str(transcript.get("speaker_name") or "").strip()
            or str(transcript.get("name") or "").strip()
            or "Unknown"
        )

        utterances.append(
            {
                "id": str(transcript.get("id") or idx),
                "speaker_name": speaker_name,
                "text": text,
                "start_ms": _to_int_or_none(transcript.get("start_ms")),
                "end_ms": _to_int_or_none(transcript.get("end_ms")),
            }
        )

    return utterances


def build_transcript_text(utterances: list[dict[str, Any]]) -> str:
    """라우팅 토큰 카운트용 transcript text 생성."""
    lines: list[str] = []
    for utterance in utterances:
        lines.append(f"[{utterance['id']}] {utterance['speaker_name']}: {utterance['text']}")
    return "\n".join(lines)


async def run_generate_pr_extraction(
    utterances: list[dict[str, Any]],
    transcript_text: str,
    realtime_topics: list[dict[str, Any]] | None,
    apply_gate: bool,
) -> dict[str, Any]:
    """generate_pr의 extraction 단계만 실행 (persistence 제외)."""
    state: dict[str, Any] = {
        "generate_pr_transcript_text": transcript_text,
        "generate_pr_transcript_utterances": utterances,
        "generate_pr_realtime_topics": realtime_topics or [],
    }

    route_state = await route_by_token_count(state)
    state.update(route_state)

    if state.get("generate_pr_route") == "long":
        extracted_state = await extract_chunked(state)
    else:
        extracted_state = await extract_single(state)
    state.update(extracted_state)

    if apply_gate:
        gated_state = await validate_hard_gate(state)
        state.update(gated_state)

    return {
        "summary": state.get("generate_pr_summary", "") or "",
        "agendas": state.get("generate_pr_agendas", []) or [],
        "diagnostics": normalize_extraction_diagnostics(state.get("generate_pr_diagnostics")),
    }


async def convert_record(
    record: dict[str, Any],
    index: int,
    apply_gate: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    meeting_info = record.get("meeting_info") or {}
    meeting_id = make_record_id(record, index)
    transcripts = list(record.get("transcripts") or [])
    realtime_topics = list(record.get("realtime_topics") or [])

    utterances = normalize_utterances(transcripts)
    if not utterances:
        return (
            {
                "record_id": meeting_id,
                "meeting_info": meeting_info,
                "utterances": [],
                "extraction_output": {"summary": "", "agendas": []},
                "error": "EMPTY_UTTERANCES",
            },
            None,
        )

    transcript_text = build_transcript_text(utterances)
    extraction_result = await run_generate_pr_extraction(
        utterances=utterances,
        transcript_text=transcript_text,
        realtime_topics=realtime_topics,
        apply_gate=apply_gate,
    )

    output_record = {
        "record_id": meeting_id,
        "meeting_info": meeting_info,
        "utterances": utterances,
        "extraction_output": {
            "summary": extraction_result.get("summary", "") or "",
            "agendas": extraction_result.get("agendas", []) or [],
        },
    }
    return output_record, extraction_result.get("diagnostics")


def _convert_record_sync(
    record: dict[str, Any],
    index: int,
    apply_gate: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Thread worker용 sync 래퍼."""
    return asyncio.run(
        convert_record(
            record=record,
            index=index,
            apply_gate=apply_gate,
        )
    )


def _is_rate_limit_error(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "429" in message
        or "too many requests" in message
        or "rate exceeded" in message
        or "rate limit" in message
    )


def _is_daily_quota_error(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "requests per day" in message
        or "rpd" in message
        or "daily quota" in message
        or "insufficient_quota" in message
        or "billing_hard_limit_reached" in message
    )


async def _process_one_record(
    progress_idx: int,
    total: int,
    record_index: int,
    record_id: str,
    record: dict[str, Any],
    apply_gate: bool,
    fail_fast: bool,
    rate_limit_cooldown_sec: int,
    rate_limit_retries: int,
) -> tuple[int, dict[str, Any], dict[str, Any] | None]:
    meeting_info = record.get("meeting_info") or {}

    print(f"\n[{progress_idx}/{total}] 처리 중: {record_id}")
    attempt = 1
    max_attempts = 1 + max(0, rate_limit_retries)

    while True:
        try:
            converted, diagnostics = await asyncio.to_thread(
                _convert_record_sync,
                record,
                record_index,
                apply_gate,
            )
            agendas = converted.get("extraction_output", {}).get("agendas", [])
            print(f"  ✓ 완료 (agendas={len(agendas)})")
            return progress_idx, converted, diagnostics
        except Exception as e:
            if _is_daily_quota_error(e):
                raise DailyQuotaExceededError(str(e)) from e

            if _is_rate_limit_error(e) and attempt < max_attempts:
                print(
                    "  ⚠️  rate limit 감지: "
                    f"record={record_id} attempt={attempt}/{max_attempts} "
                    f"cooldown={rate_limit_cooldown_sec}s"
                )
                await asyncio.sleep(rate_limit_cooldown_sec)
                attempt += 1
                continue

            if fail_fast:
                raise

            print(f"  ❌ 실패: {e}")
            fallback = {
                "record_id": record_id,
                "meeting_info": meeting_info,
                "utterances": normalize_utterances(list(record.get("transcripts") or [])),
                "extraction_output": {"summary": "", "agendas": []},
                "error": str(e),
            }
            return progress_idx, fallback, None


async def main_async(args: argparse.Namespace) -> int:
    if not args.input.exists():
        print(f"❌ 입력 파일을 찾을 수 없습니다: {args.input}")
        return 1

    records = load_jsonl(args.input)
    if args.limit is not None:
        records = records[: args.limit]

    print(f"📥 입력 로드: {len(records)} records")
    print(f"⚙️  hard gate: {'ON' if not args.no_gate else 'OFF'}")

    total = len(records)
    target_record_ids = {make_record_id(record, idx) for idx, record in enumerate(records, start=1)}

    workers = max(1, args.workers)
    print(f"🚀 workers: {workers}")
    print(
        "⏱️  rate-limit policy: "
        f"cooldown={max(1, args.rate_limit_cooldown_sec)}s, "
        f"retries={max(0, args.rate_limit_retries)}"
    )
    records_per_batch = max(0, args.records_per_batch)
    batch_cooldown_sec = max(1, args.batch_cooldown_sec)
    if records_per_batch > 0:
        print(
            "📦 batch policy: "
            f"records_per_batch={records_per_batch}, cooldown={batch_cooldown_sec}s"
        )
    else:
        print("📦 batch policy: OFF")
    print("💾 저장 방식: record 완료 즉시 append")
    print(f"🧪 strict 판정: {'복구 발생 시 fail' if args.strict_fail_on_repair else '복구 허용'}")

    diagnostics_output = (
        args.diagnostics_output
        if args.diagnostics_output is not None
        else default_diagnostics_output_path(args.output)
    )
    print(f"📝 diagnostics 출력: {diagnostics_output}")

    processed_ids: set[str] = set()
    existing_output_rows: list[dict[str, Any]] = []
    if args.resume and args.output.exists():
        existing_output_rows = load_jsonl(args.output)
        for row in existing_output_rows:
            rid = str(row.get("record_id") or "").strip()
            if rid and rid in target_record_ids:
                processed_ids.add(rid)
        print(f"♻️  resume: 기존 {len(processed_ids)} records 감지")

    diagnostics_entries: dict[str, dict[str, Any]] = {}
    if args.resume and diagnostics_output.exists():
        loaded_entries = load_diagnostics_entries(diagnostics_output)
        diagnostics_entries = {
            rid: entry for rid, entry in loaded_entries.items() if rid in target_record_ids
        }
        print(f"♻️  resume diagnostics: {len(diagnostics_entries)} records 감지")

    for row in existing_output_rows:
        rid = str(row.get("record_id") or "").strip()
        if not rid or rid not in target_record_ids or rid in diagnostics_entries:
            continue
        diagnostics_entries[rid] = build_record_diagnostics_entry(
            record_id=rid,
            diagnostics=None,
            error=str(row.get("error") or "") or None,
            strict_fail_on_repair=args.strict_fail_on_repair,
        )

    def upsert_diagnostics(
        converted: dict[str, Any],
        diagnostics: dict[str, Any] | None,
    ) -> None:
        rid = str(converted.get("record_id") or "").strip()
        if not rid or rid not in target_record_ids:
            return
        diagnostics_entries[rid] = build_record_diagnostics_entry(
            record_id=rid,
            diagnostics=diagnostics,
            error=str(converted.get("error") or "") or None,
            strict_fail_on_repair=args.strict_fail_on_repair,
        )

    def write_diagnostics_snapshot() -> None:
        report = build_diagnostics_report(
            total_records=total,
            diagnostics_entries=diagnostics_entries,
            strict_fail_on_repair=args.strict_fail_on_repair,
        )
        write_json(diagnostics_output, report)

    indexed_records: list[tuple[int, str, dict[str, Any]]] = []
    skipped = 0
    for idx, record in enumerate(records, start=1):
        record_id = make_record_id(record, idx)
        if record_id in processed_ids:
            skipped += 1
            continue
        indexed_records.append((idx, record_id, record))

    pending_total = len(indexed_records)
    print(f"📌 처리 대상: {pending_total} records (skip={skipped})")

    if not args.resume or not args.output.exists():
        init_jsonl(args.output)
        saved_count = 0
    else:
        saved_count = len(processed_ids)

    def iter_record_batches() -> list[tuple[int, int, int, list[tuple[int, str, dict[str, Any]]]]]:
        if records_per_batch <= 0 or pending_total <= records_per_batch:
            return [(1, 1, 0, indexed_records)]

        batches: list[tuple[int, int, int, list[tuple[int, str, dict[str, Any]]]]] = []
        num_batches = math.ceil(pending_total / records_per_batch)
        for batch_idx in range(num_batches):
            start = batch_idx * records_per_batch
            end = min(start + records_per_batch, pending_total)
            batches.append(
                (
                    batch_idx + 1,
                    num_batches,
                    start,
                    indexed_records[start:end],
                )
            )
        return batches

    batches = iter_record_batches()
    stopped_by_daily_quota = False
    daily_quota_message = ""

    if workers == 1 or pending_total <= 1:
        for batch_idx, num_batches, start_offset, batch_records in batches:
            if records_per_batch > 0:
                print(f"\n📦 배치 {batch_idx}/{num_batches}: {len(batch_records)} records")

            for local_idx, (record_index, record_id, record) in enumerate(batch_records):
                progress_idx = start_offset + local_idx + 1
                try:
                    _, converted, diagnostics = await _process_one_record(
                        progress_idx=progress_idx,
                        total=pending_total,
                        record_index=record_index,
                        record_id=record_id,
                        record=record,
                        apply_gate=not args.no_gate,
                        fail_fast=args.fail_fast,
                        rate_limit_cooldown_sec=max(1, args.rate_limit_cooldown_sec),
                        rate_limit_retries=max(0, args.rate_limit_retries),
                    )
                except DailyQuotaExceededError as e:
                    stopped_by_daily_quota = True
                    daily_quota_message = str(e)
                    print(
                        "\n🛑 일일 쿼터(RPD) 제한 감지로 중단합니다. "
                        "출력은 지금까지 저장되었고, --resume 으로 재개할 수 있습니다."
                    )
                    break

                append_jsonl_record(args.output, converted)
                upsert_diagnostics(converted, diagnostics)
                write_diagnostics_snapshot()
                saved_count += 1
                print(f"  💾 저장 완료 ({saved_count}/{total})")

            if stopped_by_daily_quota:
                break

            if records_per_batch > 0 and batch_idx < num_batches:
                print(f"⏳ 배치 cooldown {batch_cooldown_sec}s")
                await asyncio.sleep(batch_cooldown_sec)
    else:
        semaphore = asyncio.Semaphore(workers)

        async def bounded_process(
            progress_idx: int,
            record_index: int,
            record_id: str,
            record: dict[str, Any],
        ) -> tuple[int, dict[str, Any], dict[str, Any] | None]:
            async with semaphore:
                return await _process_one_record(
                    progress_idx=progress_idx,
                    total=pending_total,
                    record_index=record_index,
                    record_id=record_id,
                    record=record,
                    apply_gate=not args.no_gate,
                    fail_fast=args.fail_fast,
                    rate_limit_cooldown_sec=max(1, args.rate_limit_cooldown_sec),
                    rate_limit_retries=max(0, args.rate_limit_retries),
                )

        for batch_idx, num_batches, start_offset, batch_records in batches:
            if records_per_batch > 0:
                print(f"\n📦 배치 {batch_idx}/{num_batches}: {len(batch_records)} records")

            tasks = [
                asyncio.create_task(
                    bounded_process(
                        start_offset + local_idx + 1,
                        record_index,
                        record_id,
                        record,
                    )
                )
                for local_idx, (record_index, record_id, record) in enumerate(batch_records)
            ]

            for future in asyncio.as_completed(tasks):
                try:
                    _, converted, diagnostics = await future
                except DailyQuotaExceededError as e:
                    stopped_by_daily_quota = True
                    daily_quota_message = str(e)
                    print(
                        "\n🛑 일일 쿼터(RPD) 제한 감지로 중단합니다. "
                        "출력은 지금까지 저장되었고, --resume 으로 재개할 수 있습니다."
                    )
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    break

                append_jsonl_record(args.output, converted)
                upsert_diagnostics(converted, diagnostics)
                write_diagnostics_snapshot()
                saved_count += 1
                print(f"  💾 저장 완료 ({saved_count}/{total})")

            if stopped_by_daily_quota:
                break

            if records_per_batch > 0 and batch_idx < num_batches:
                print(f"⏳ 배치 cooldown {batch_cooldown_sec}s")
                await asyncio.sleep(batch_cooldown_sec)

    write_diagnostics_snapshot()
    final_report = build_diagnostics_report(
        total_records=total,
        diagnostics_entries=diagnostics_entries,
        strict_fail_on_repair=args.strict_fail_on_repair,
    )
    strict_stats = final_report.get("strict", {})

    print(f"\n💾 출력 저장: {args.output}")
    print(f"📝 diagnostics 저장: {diagnostics_output}")
    print(
        "🧪 strict 결과: "
        f"pass={strict_stats.get('pass', 0)} "
        f"fail={strict_stats.get('fail', 0)} "
        f"unknown={strict_stats.get('unknown', 0)}"
    )
    print(f"✅ 완료: {saved_count} records")
    if stopped_by_daily_quota:
        if daily_quota_message:
            print(f"ℹ️  quota message: {daily_quota_message}")
        return 2

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="normalized transcripts JSONL -> evaluate_pr 입력 JSONL"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        required=True,
        help="입력 JSONL (raw_transcripts_normalized.jsonl)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="출력 JSONL (evaluate_pr 입력 포맷)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="처리 레코드 수 제한",
    )
    parser.add_argument(
        "--no-gate",
        action="store_true",
        help="hard gate 검증 비활성화",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="첫 에러에서 즉시 종료",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="동시 처리 워커 수 (권장: 2~3)",
    )
    parser.add_argument(
        "--rate-limit-cooldown-sec",
        type=int,
        default=60,
        help="rate limit 감지 시 대기 시간(초)",
    )
    parser.add_argument(
        "--rate-limit-retries",
        type=int,
        default=1,
        help="record 단위 rate limit 재시도 횟수",
    )
    parser.add_argument(
        "--records-per-batch",
        type=int,
        default=0,
        help="배치당 처리할 record 수 (0이면 배치 OFF)",
    )
    parser.add_argument(
        "--batch-cooldown-sec",
        type=int,
        default=60,
        help="배치 처리 후 대기 시간(초)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="기존 출력 JSONL에 이어서 실행 (이미 처리한 record_id는 skip)",
    )
    parser.add_argument(
        "--diagnostics-output",
        type=Path,
        default=None,
        help="Strict/Salvaged 진단 리포트 출력 경로 (기본: <output>.diagnostics.json)",
    )
    parser.add_argument(
        "--strict-fail-on-repair",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="복구가 발생하면 strict를 fail로 판정 (기본: true)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        code = asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n중단됨")
        code = 130
    sys.exit(code)


if __name__ == "__main__":
    main()
