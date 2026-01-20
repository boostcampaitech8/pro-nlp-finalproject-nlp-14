// Timeline View - Blame 히스토리 타임라인 UI
import { Clock, User, FileText, CheckCircle2 } from 'lucide-react';

export interface TimelineItem {
  date: string;
  value: string;
  author: string;
  reason: string;
  meetingId?: string;
  isFinal?: boolean;
}

interface TimelineViewProps {
  items: TimelineItem[];
  title: string;
}

function TimelineItemComponent({ item, isFirst }: { item: TimelineItem; isFirst: boolean }) {
  return (
    <div className="relative flex gap-4 group">
      {/* 타임라인 라인 */}
      {!isFirst && (
        <div className="absolute left-[15px] top-0 w-[2px] h-6 bg-gradient-to-b from-mit-primary/60 to-transparent" />
      )}

      {/* 타임라인 노드 */}
      <div className="relative z-10 mt-6">
        <div
          className={`
            w-8 h-8 rounded-full flex items-center justify-center
            border-2 transition-all duration-300
            ${
              item.isFinal
                ? 'bg-mit-success border-mit-success shadow-[0_0_20px_rgba(34,197,94,0.4)]'
                : 'bg-mit-primary/20 border-mit-primary/60 group-hover:border-mit-primary group-hover:bg-mit-primary/30'
            }
          `}
        >
          {item.isFinal ? (
            <CheckCircle2 className="w-4 h-4 text-white" strokeWidth={2.5} />
          ) : (
            <div className="w-2 h-2 rounded-full bg-mit-primary" />
          )}
        </div>
      </div>

      {/* 카드 콘텐츠 */}
      <div className="flex-1 mt-4 mb-8">
        <div
          className={`
            glass-card p-5 group-hover:bg-card-hover transition-all duration-300
            ${item.isFinal ? 'border-mit-success/30 bg-mit-success/5' : ''}
          `}
        >
          {/* 헤더 */}
          <div className="flex items-start justify-between gap-4 mb-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <Clock className="w-3.5 h-3.5 text-white/40 flex-shrink-0" />
                <span className="text-[11px] text-white/40 font-mono">{item.date}</span>
                {item.isFinal && (
                  <span className="px-2 py-0.5 rounded-full bg-mit-success/20 text-mit-success text-[10px] font-bold uppercase tracking-wide">
                    Final
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* 값 - 강조 표시 */}
          <div className="mb-4 p-3 bg-black/20 rounded-lg border border-white/5">
            <div className="text-[11px] text-white/40 uppercase tracking-wide mb-1">Value</div>
            <div className="text-[16px] font-semibold text-white break-words">{item.value}</div>
          </div>

          {/* 작성자 */}
          <div className="flex items-center gap-2 mb-3">
            <User className="w-3.5 h-3.5 text-white/60" />
            <span className="text-[13px] text-white/80">{item.author}</span>
          </div>

          {/* 사유 */}
          {item.reason && (
            <div className="pt-3 border-t border-white/5">
              <div className="text-[11px] text-white/40 uppercase tracking-wide mb-2">Reason</div>
              <p className="text-[13px] text-white/70 leading-relaxed">{item.reason}</p>
            </div>
          )}

          {/* 회의 링크 */}
          {item.meetingId && (
            <div className="mt-3 pt-3 border-t border-white/5">
              <button className="flex items-center gap-2 text-[12px] text-mit-primary hover:text-mit-primary/80 transition-colors">
                <FileText className="w-3.5 h-3.5" />
                <span>View Meeting #{item.meetingId}</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function TimelineView({ items, title }: TimelineViewProps) {
  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <div className="w-16 h-16 rounded-full bg-mit-primary/10 flex items-center justify-center mb-4">
          <Clock className="w-8 h-8 text-white/30" />
        </div>
        <p className="text-[14px] text-white/60">타임라인 항목이 없습니다</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {/* 헤더 */}
      <div className="mb-6 pb-4 border-b border-white/10">
        <h2 className="text-[20px] font-bold text-white mb-1">{title}</h2>
        <p className="text-[12px] text-white/50">
          {items.length} {items.length === 1 ? 'revision' : 'revisions'}
        </p>
      </div>

      {/* 타임라인 */}
      <div className="space-y-0">
        {items.map((item, index) => (
          <TimelineItemComponent key={index} item={item} isFirst={index === 0} />
        ))}
      </div>
    </div>
  );
}
