// Action Items View - Action Item 체크리스트 UI
import { CheckCircle2, Circle, Calendar, User, AlertCircle } from 'lucide-react';

export interface ActionItem {
  id: string;
  title: string;
  assignee: string;
  dueDate: string;
  completed: boolean;
}

interface ActionItemsViewProps {
  items: ActionItem[];
}

function ActionItemComponent({ item }: { item: ActionItem }) {
  // 기한 체크 (단순 날짜 문자열 비교)
  const today = new Date().toISOString().split('T')[0];
  const isOverdue = !item.completed && item.dueDate < today;
  const isDueSoon = !item.completed && item.dueDate === today;

  return (
    <div
      className={`
        group relative p-4 rounded-xl border-2 transition-all duration-200
        ${
          item.completed
            ? 'bg-white/[0.02] border-white/5 opacity-60'
            : 'glass-card border-glass-light hover:border-mit-primary/40 hover:bg-card-hover'
        }
      `}
    >
      {/* Overdue 인디케이터 */}
      {isOverdue && (
        <div className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-mit-warning flex items-center justify-center shadow-lg">
          <AlertCircle className="w-3 h-3 text-white" strokeWidth={2.5} />
        </div>
      )}

      <div className="flex items-start gap-3">
        {/* 체크박스 */}
        <button
          className={`
            mt-0.5 flex-shrink-0 transition-all duration-200
            ${item.completed ? 'text-mit-success' : 'text-white/30 hover:text-mit-primary'}
          `}
        >
          {item.completed ? (
            <CheckCircle2 className="w-5 h-5" strokeWidth={2.5} />
          ) : (
            <Circle className="w-5 h-5 group-hover:scale-110 transition-transform" strokeWidth={2} />
          )}
        </button>

        {/* 콘텐츠 */}
        <div className="flex-1 min-w-0">
          {/* 제목 */}
          <h3
            className={`
              text-[14px] font-medium mb-3 leading-snug
              ${item.completed ? 'line-through text-white/40' : 'text-white'}
            `}
          >
            {item.title}
          </h3>

          {/* 메타 정보 */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            {/* 담당자 */}
            <div className="flex items-center gap-1.5">
              <User className="w-3.5 h-3.5 text-white/40" />
              <span className="text-[12px] text-white/60">{item.assignee}</span>
            </div>

            {/* 기한 */}
            <div
              className={`
                flex items-center gap-1.5
                ${
                  isOverdue
                    ? 'text-mit-warning'
                    : isDueSoon
                      ? 'text-yellow-400'
                      : item.completed
                        ? 'text-white/40'
                        : 'text-white/60'
                }
              `}
            >
              <Calendar className="w-3.5 h-3.5" />
              <span className="text-[12px] font-mono">{item.dueDate}</span>
              {isOverdue && (
                <span className="text-[10px] font-bold uppercase tracking-wide">Overdue</span>
              )}
              {isDueSoon && (
                <span className="text-[10px] font-bold uppercase tracking-wide">Today</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ActionItemsView({ items }: ActionItemsViewProps) {
  const completedCount = items.filter((item) => item.completed).length;
  const totalCount = items.length;
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <div className="w-16 h-16 rounded-full bg-mit-primary/10 flex items-center justify-center mb-4">
          <CheckCircle2 className="w-8 h-8 text-white/30" />
        </div>
        <p className="text-[14px] text-white/60">액션 아이템이 없습니다</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 헤더 + 프로그레스 */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[20px] font-bold text-white">Action Items</h2>
          <div className="text-[13px] font-semibold">
            <span className="text-mit-success">{completedCount}</span>
            <span className="text-white/40 mx-1">/</span>
            <span className="text-white/60">{totalCount}</span>
          </div>
        </div>

        {/* 프로그레스 바 */}
        <div className="relative h-2 bg-black/30 rounded-full overflow-hidden">
          <div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-mit-success to-mit-primary transition-all duration-500 rounded-full"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="mt-1 text-right">
          <span className="text-[11px] text-white/40 font-mono">{progressPercent}% complete</span>
        </div>
      </div>

      {/* 액션 아이템 리스트 */}
      <div className="space-y-3">
        {items.map((item) => (
          <ActionItemComponent key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}
