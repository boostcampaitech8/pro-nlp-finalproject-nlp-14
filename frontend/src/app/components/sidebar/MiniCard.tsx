// 하단 미니 카드 (단축키 힌트 등)
import { Command } from 'lucide-react';

export function MiniCard() {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-3 mb-3">
        <div className="icon-container-sm">
          <Command className="w-5 h-5 text-mit-primary" />
        </div>
        <div>
          <p className="text-[13px] font-medium text-white">빠른 실행</p>
          <p className="text-[11px] text-white/40">키보드 단축키</p>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[12px] text-white/60">검색</span>
          <div className="flex gap-1">
            <span className="shortcut-key">Cmd</span>
            <span className="shortcut-key">K</span>
          </div>
        </div>
      </div>
    </div>
  );
}
