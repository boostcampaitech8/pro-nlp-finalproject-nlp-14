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
    color: 'text-gray-500',
    bgColor: 'bg-gray-100',
  },
  in_progress: {
    icon: Clock,
    label: '진행중',
    color: 'text-blue-600',
    bgColor: 'bg-blue-100',
  },
  completed: {
    icon: CheckCircle2,
    label: '완료',
    color: 'text-green-600',
    bgColor: 'bg-green-100',
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
          ? 'bg-gray-50 border-gray-200'
          : 'bg-white border-gray-200 hover:border-gray-300 hover:shadow-sm'
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
              <div className="absolute top-full left-0 mt-1 py-1 bg-white rounded-lg shadow-lg border border-gray-200 z-20 min-w-[120px]">
                {(Object.keys(STATUS_CONFIG) as ActionItemStatus[]).map((status) => {
                  const cfg = STATUS_CONFIG[status];
                  const Icon = cfg.icon;
                  return (
                    <button
                      key={status}
                      type="button"
                      onClick={() => handleStatusChange(status)}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-gray-50 transition-colors ${
                        status === item.status ? 'bg-gray-50' : ''
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
          {/* 제목 */}
          <EditableText
            value={item.title}
            onSave={async (title) => onUpdate({ title })}
            className={`font-medium ${
              item.status === 'completed' ? 'line-through text-gray-400' : 'text-gray-900'
            }`}
            disabled={isLoading}
          />

          {/* 설명 */}
          {item.description && (
            <p
              className={`mt-1 text-sm ${
                item.status === 'completed' ? 'text-gray-400' : 'text-gray-600'
              }`}
            >
              {item.description}
            </p>
          )}

          {/* 메타 정보 */}
          <div className="flex items-center gap-4 mt-2">
            {/* 담당자 */}
            {item.assigneeId && (
              <div className="flex items-center gap-1 text-xs text-gray-500">
                <User className="w-3 h-3" />
                <span>담당자 지정됨</span>
              </div>
            )}

            {/* 기한 */}
            {dueInfo && (
              <div
                className={`flex items-center gap-1 text-xs ${
                  dueInfo.isOverdue ? 'text-red-600' : 'text-gray-500'
                }`}
              >
                <Calendar className="w-3 h-3" />
                <span>{dueInfo.text}</span>
                {dueInfo.isOverdue && (
                  <span className="text-red-600 font-medium">지남</span>
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
          className="p-2 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
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
