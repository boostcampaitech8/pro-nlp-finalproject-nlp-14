/**
 * 단일 ActionItem 카드 컴포넌트
 *
 * 인라인 편집, 상태 변경, 삭제 기능
 */

import { useState } from 'react';
import {
  CheckCircle2,
  Circle,
  Clock,
  Trash2,
  Loader2,
  User,
  Calendar,
} from 'lucide-react';
import type { ActionItem, ActionItemStatus, UpdateActionItemRequest } from '@/types';
import { EditableText } from '../EditableText';

interface ActionItemCardProps {
  item: ActionItem;
  onUpdate: (data: UpdateActionItemRequest) => Promise<boolean>;
  onDelete: () => Promise<boolean>;
  isLoading?: boolean;
}

const STATUS_CONFIG: Record<
  ActionItemStatus,
  { icon: typeof Circle; label: string; color: string; bgColor: string }
> = {
  pending: {
    icon: Circle,
    label: '대기',
    color: 'text-white/50',
    bgColor: 'bg-white/10',
  },
  in_progress: {
    icon: Clock,
    label: '진행중',
    color: 'text-blue-400',
    bgColor: 'bg-blue-500/20',
  },
  completed: {
    icon: CheckCircle2,
    label: '완료',
    color: 'text-green-400',
    bgColor: 'bg-green-500/20',
  },
};

export function ActionItemCard({
  item,
  onUpdate,
  onDelete,
  isLoading = false,
}: ActionItemCardProps) {
  const [showStatusMenu, setShowStatusMenu] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const config = STATUS_CONFIG[item.status];
  const StatusIcon = config.icon;

  const handleStatusChange = async (newStatus: ActionItemStatus) => {
    setShowStatusMenu(false);
    if (newStatus !== item.status) {
      await onUpdate({ status: newStatus });
    }
  };

  const handleDelete = async () => {
    if (isDeleting) return;
    setIsDeleting(true);
    try {
      await onDelete();
    } finally {
      setIsDeleting(false);
    }
  };

  const formatDueDate = (date: string | null) => {
    if (!date) return null;
    const d = new Date(date);
    const now = new Date();
    const isOverdue = d < now && item.status !== 'completed';
    return {
      text: d.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' }),
      isOverdue,
    };
  };

  const dueInfo = formatDueDate(item.dueDate);

  return (
    <div
      className={`group p-4 rounded-xl border transition-all ${
        item.status === 'completed'
          ? 'bg-white/5 border-white/10'
          : 'bg-white/5 border-white/10 hover:border-white/20 hover:bg-white/10'
      }`}
    >
      <div className="flex items-start gap-3">
        {/* 상태 선택 드롭다운 */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowStatusMenu(!showStatusMenu)}
            disabled={isLoading}
            className={`p-2 rounded-lg transition-colors ${config.bgColor} ${config.color} hover:opacity-80`}
          >
            <StatusIcon className="w-5 h-5" />
          </button>

          {showStatusMenu && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setShowStatusMenu(false)}
              />
              <div className="absolute top-full left-0 mt-1 py-1 bg-gray-800 rounded-lg shadow-lg border border-white/10 z-20 min-w-[120px]">
                {(Object.keys(STATUS_CONFIG) as ActionItemStatus[]).map((status) => {
                  const cfg = STATUS_CONFIG[status];
                  const Icon = cfg.icon;
                  return (
                    <button
                      key={status}
                      type="button"
                      onClick={() => handleStatusChange(status)}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-white/10 transition-colors ${
                        status === item.status ? 'bg-white/10' : ''
                      }`}
                    >
                      <Icon className={`w-4 h-4 ${cfg.color}`} />
                      <span>{cfg.label}</span>
                    </button>
                  );
                })}
              </div>
            </>
          )}
        </div>
        {/* 내용 */}
        <div className="flex-1 min-w-0">
          <EditableText
            value={item.content}
            onSave={async (content) => onUpdate({ content })}
            className={`font-medium ${
              item.status === 'completed' ? 'line-through text-white/40' : 'text-white'
            }`}
            disabled={isLoading}
          />

          {/* 메타 정보 */}
          <div className="flex items-center gap-4 mt-2">
            {/* 담당자 */}
            {item.assigneeId && (
              <div className="flex items-center gap-1 text-xs text-white/50">
                <User className="w-3 h-3" />
                <span>담당자 지정됨</span>
              </div>
            )}

            {/* 기한 */}
            {dueInfo && (
              <div
                className={`flex items-center gap-1 text-xs ${
                  dueInfo.isOverdue ? 'text-red-400' : 'text-white/50'
                }`}
              >
                <Calendar className="w-3 h-3" />
                <span>{dueInfo.text}</span>
                {dueInfo.isOverdue && (
                  <span className="text-red-400 font-medium">지남</span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* 삭제 버튼 */}
        <button
          type="button"
          onClick={handleDelete}
          disabled={isDeleting || isLoading}
          className="p-2 text-white/30 hover:text-red-400 hover:bg-red-500/20 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
        >
          {isDeleting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Trash2 className="w-4 h-4" />
          )}
        </button>
      </div>
    </div>
  );
}
