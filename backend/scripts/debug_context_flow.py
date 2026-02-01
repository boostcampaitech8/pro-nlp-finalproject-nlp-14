#!/usr/bin/env python
"""Context Engineering + Checkpointer 디버그 스크립트

실행 방법:
    cd backend
    uv run python scripts/debug_context_flow.py <meeting_id>

예시:
    uv run python scripts/debug_context_flow.py 550e8400-e29b-41d4-a716-446655440000
"""

import asyncio
import sys
from uuid import UUID

# 경로 설정
sys.path.insert(0, ".")


async def debug_context_flow(meeting_id: str):
    """전체 컨텍스트 플로우 디버깅"""
    from sqlalchemy import select, func

    from app.core.database import async_session_maker
    from app.infrastructure.context import ContextBuilder, ContextManager
    from app.models.transcript import Transcript

    print("=" * 60)
    print(f"🔍 Meeting ID: {meeting_id}")
    print("=" * 60)

    async with async_session_maker() as db:
        # ========================================
        # 1. DB에서 Transcript 확인
        # ========================================
        print("\n📊 [1] DB Transcripts 확인")
        print("-" * 40)

        count_query = select(func.count()).select_from(Transcript).where(
            Transcript.meeting_id == UUID(meeting_id)
        )
        result = await db.execute(count_query)
        total_count = result.scalar()
        print(f"총 발화 수: {total_count}")

        if total_count == 0:
            print("⚠️  발화 데이터가 없습니다. 미팅을 먼저 진행해주세요.")
            return

        # 최근 5개 발화 샘플
        sample_query = (
            select(Transcript)
            .where(Transcript.meeting_id == UUID(meeting_id))
            .order_by(Transcript.created_at.desc())
            .limit(5)
        )
        result = await db.execute(sample_query)
        samples = result.scalars().all()

        print("\n최근 발화 (최신순 5개):")
        for t in samples:
            user_id = str(t.user_id)[:8]
            text = t.transcript_text[:50] + "..." if len(t.transcript_text) > 50 else t.transcript_text
            print(f"  [user:{user_id}...] {text}")

        # ========================================
        # 2. ContextManager 로드
        # ========================================
        print("\n📥 [2] ContextManager 로드")
        print("-" * 40)

        ctx_manager = ContextManager(meeting_id=meeting_id, db_session=db)
        loaded = await ctx_manager.load_from_db()
        print(f"로드된 발화 수: {loaded}")

        # L0 버퍼 상태
        print(f"\nL0 Raw Buffer (최대 {ctx_manager.config.l0_max_turns}개):")
        print(f"  현재 크기: {len(ctx_manager.l0_buffer)}")
        if ctx_manager.l0_buffer:
            first = ctx_manager.l0_buffer[0]
            last = ctx_manager.l0_buffer[-1]
            print(f"  첫 발화: [{first.speaker_name}] {first.text[:30]}...")
            print(f"  마지막: [{last.speaker_name}] {last.text[:30]}...")

        # L0 토픽 버퍼
        print(f"\nL0 Topic Buffer (현재 토픽: {ctx_manager.current_topic}):")
        print(f"  현재 크기: {len(ctx_manager.l0_topic_buffer)}")

        # ========================================
        # 3. L1 처리 대기
        # ========================================
        print("\n⏳ [3] L1 처리")
        print("-" * 40)

        if ctx_manager.has_pending_l1:
            print("L1 요약 처리 중...")
            await ctx_manager.await_pending_l1()
            print(f"L1 세그먼트 생성 완료: {len(ctx_manager.l1_segments)}개")
        else:
            print("대기 중인 L1 처리 없음")

        # L1 세그먼트 상태
        print(f"\nL1 세그먼트 목록:")
        if ctx_manager.l1_segments:
            for seg in ctx_manager.l1_segments:
                summary = seg.summary[:60] + "..." if len(seg.summary) > 60 else seg.summary
                print(f"  [{seg.name}] {summary}")
        else:
            print("  (세그먼트 없음)")

        # ========================================
        # 4. ContextBuilder 컨텍스트 생성
        # ========================================
        print("\n🏗️  [4] ContextBuilder 컨텍스트 생성")
        print("-" * 40)

        builder = ContextBuilder()
        test_query = "오늘 회의에서 결정된 사항이 뭐야?"
        planning_context = builder.build_planning_input_context(
            ctx_manager, user_query=test_query
        )

        print(f"Planning Context 길이: {len(planning_context)} chars")
        print("\n--- Planning Context (처음 500자) ---")
        print(planning_context[:500])
        if len(planning_context) > 500:
            print("... (생략)")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_context_flow.py <meeting_id>")
        print("\nExample:")
        print("  uv run python scripts/debug_context_flow.py 550e8400-e29b-41d4-a716-446655440000")
        sys.exit(1)

    meeting_id = sys.argv[1]

    # Context 플로우 디버깅
    await debug_context_flow(meeting_id)

    print("\n" + "=" * 60)
    print("✅ 디버깅 완료")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
