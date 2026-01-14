// 새 서비스 메인 페이지 (Spotlight UI)
// Phase 4에서 Spotlight 컴포넌트 전체 구현 예정

import { Command } from 'lucide-react';

export function MainPage() {
  return (
    <div className="flex-1 flex flex-col">
      {/* 상단: 추천 명령어 영역 (Phase 4에서 구현) */}
      <section className="flex-1 flex items-end justify-center px-12 pb-8">
        <div className="text-center">
          <p className="text-white/40 text-sm mb-4">
            추천 명령어가 여기에 표시됩니다
          </p>
        </div>
      </section>

      {/* 중앙: Spotlight 입력 영역 */}
      <section className="px-12 py-8 bg-black/20 border-y border-glass">
        <div className="max-w-2xl mx-auto">
          {/* Spotlight 입력창 플레이스홀더 */}
          <div className="glass-input flex items-center gap-4 px-6 py-4">
            <Command className="w-5 h-5 text-white/40" />
            <input
              type="text"
              placeholder="무엇을 도와드릴까요? (예: '새 회의 시작', '지난 회의록 검색')"
              className="flex-1 bg-transparent text-white placeholder:text-white/40 outline-none text-[15px]"
              disabled
            />
            <div className="flex gap-1">
              <span className="shortcut-key">Cmd</span>
              <span className="shortcut-key">K</span>
            </div>
          </div>

          <p className="text-center text-white/30 text-xs mt-4">
            Phase 4에서 Spotlight 기능이 구현됩니다
          </p>
        </div>
      </section>

      {/* 하단: 히스토리 영역 (Phase 4에서 구현) */}
      <section className="flex-1 flex items-start justify-center px-12 pt-8">
        <div className="text-center">
          <p className="text-white/40 text-sm">
            명령 히스토리가 여기에 표시됩니다
          </p>
        </div>
      </section>
    </div>
  );
}
