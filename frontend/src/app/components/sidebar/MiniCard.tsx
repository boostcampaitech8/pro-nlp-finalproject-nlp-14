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
          <p className="text-[13px] font-medium text-white">Quick Actions</p>
          <p className="text-[11px] text-white/40">Keyboard shortcuts</p>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[12px] text-white/60">New meeting</span>
          <div className="flex gap-1">
            <span className="shortcut-key">Cmd</span>
            <span className="shortcut-key">N</span>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[12px] text-white/60">Search</span>
          <div className="flex gap-1">
            <span className="shortcut-key">Cmd</span>
            <span className="shortcut-key">K</span>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[12px] text-white/60">Dashboard</span>
          <div className="flex gap-1">
            <span className="shortcut-key">Cmd</span>
            <span className="shortcut-key">D</span>
          </div>
        </div>
      </div>
    </div>
  );
}
