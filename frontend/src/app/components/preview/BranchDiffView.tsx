// Branch Diff View - GT 변경 비교 UI
import { GitBranch, ArrowRight, FileText, Clock } from 'lucide-react';

export interface BranchDiffViewProps {
  target: string;
  currentValue: string;
  proposedValue: string;
  reason?: string;
  branchId: string;
}

export default function BranchDiffView({
  target,
  currentValue,
  proposedValue,
  reason,
  branchId,
}: BranchDiffViewProps) {
  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-mit-primary/20 flex items-center justify-center">
            <GitBranch className="w-4 h-4 text-mit-primary" strokeWidth={2.5} />
          </div>
          <div>
            <h2 className="text-[20px] font-bold text-white leading-tight">{target}</h2>
          </div>
        </div>

        {/* 상태 배지 */}
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-yellow-500/20 border border-yellow-500/30">
          <Clock className="w-3.5 h-3.5 text-yellow-400" />
          <span className="text-[12px] font-bold text-yellow-300 uppercase tracking-wide">
            리뷰 대기중
          </span>
        </div>
      </div>

      {/* 비교 섹션 */}
      <div className="space-y-3">
        {/* 현재 GT */}
        <div className="glass-card p-5 border-l-4 border-white/20">
          <div className="flex items-center gap-2 mb-3">
            <div className="text-[11px] font-bold text-white/40 uppercase tracking-wide">
              Current GT
            </div>
          </div>
          <div className="text-[18px] font-semibold text-white/80 leading-snug">
            {currentValue}
          </div>
        </div>

        {/* 화살표 */}
        <div className="flex justify-center">
          <div className="w-10 h-10 rounded-full bg-mit-primary/20 flex items-center justify-center">
            <ArrowRight className="w-5 h-5 text-mit-primary" strokeWidth={2.5} />
          </div>
        </div>

        {/* 제안 값 */}
        <div className="glass-card p-5 border-l-4 border-mit-primary bg-mit-primary/5">
          <div className="flex items-center gap-2 mb-3">
            <div className="text-[11px] font-bold text-mit-primary uppercase tracking-wide">
              Proposed Value
            </div>
          </div>
          <div className="text-[18px] font-semibold text-white leading-snug">{proposedValue}</div>
        </div>
      </div>

      {/* 변경 사유 */}
      {reason && (
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-white/60" />
            <h3 className="text-[13px] font-bold text-white/80 uppercase tracking-wide">
              Change Reason
            </h3>
          </div>
          <p className="text-[14px] text-white/70 leading-relaxed">{reason}</p>
        </div>
      )}

      {/* Branch 정보 */}
      <div className="pt-4 border-t border-white/10">
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-white/40 uppercase tracking-wide">Branch ID</span>
          <code className="text-[12px] font-mono text-mit-primary bg-black/20 px-2 py-1 rounded">
            {branchId}
          </code>
        </div>
      </div>

      {/* 액션 버튼 영역 (미래 확장용) */}
      <div className="pt-2 flex gap-2">
        <button className="flex-1 py-3 rounded-xl bg-mit-primary/20 border border-mit-primary/40 text-mit-primary font-semibold text-[13px] hover:bg-mit-primary/30 transition-all duration-200">
          View Full Diff
        </button>
        <button className="flex-1 py-3 rounded-xl bg-white/5 border border-white/10 text-white/80 font-semibold text-[13px] hover:bg-white/10 transition-all duration-200">
          View Branch
        </button>
      </div>
    </div>
  );
}
