// 로고 컴포넌트
import { Layers } from 'lucide-react';

export function Logo() {
  return (
    <div className="flex items-center gap-3 mb-5">
      <div className="icon-container">
        <Layers className="w-5 h-5 text-white" />
      </div>
      <div>
        <h1 className="text-lg font-bold text-white tracking-tight" aria-label="Mit - 회의 지능 도구">Mit</h1>
        <p className="text-[11px] text-white/40">Meeting Intelligence</p>
      </div>
    </div>
  );
}
