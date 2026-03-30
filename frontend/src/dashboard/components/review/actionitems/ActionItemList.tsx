/**
 * ActionItem 목록 컴포넌트
 *
 * 필터링 및 상태별 그룹핑
 */

import { useState, useMemo } from 'react';
import { ListTodo, Filter, CheckCircle2, Circle, Clock } from 'lucide-react';
import type { ActionItem, ActionItemStatus, UpdateActionItemRequest } from '@/types';
import { ActionItemCard } from './ActionItemCard';

interface ActionItemListProps {
  items: ActionItem[];
  onUpdate: (itemId: string, data: UpdateActionItemRequest) => Promise<boolean>;
  onDelete: (itemId: string) => Promise<boolean>;
  isLoading?: boolean;
  showFilter?: boolean;
}

type FilterStatus = 'all' | ActionItemStatus;

const FILTER_OPTIONS: { value: FilterStatus; label: string; icon: typeof Circle }[] = [
  { value: 'all', label: '전체', icon: ListTodo },
  { value: 'pending', label: '대기', icon: Circle },
  { value: 'in_progress', label: '진행중', icon: Clock },
  { value: 'completed', label: '완료', icon: CheckCircle2 },
];

export function ActionItemList({
  items,
  onUpdate,
  onDelete,
  isLoading = false,
  showFilter = true,
}: ActionItemListProps) {
  const [filter, setFilter] = useState<FilterStatus>('all');

  const filteredItems = useMemo(() => {
    if (filter === 'all') return items;
    return items.filter((item) => item.status === filter);
  }, [items, filter]);

  const counts = useMemo(() => {
    return {
      all: items.length,
      pending: items.filter((i) => i.status === 'pending').length,
      in_progress: items.filter((i) => i.status === 'in_progress').length,
      completed: items.filter((i) => i.status === 'completed').length,
    };
  }, [items]);

  if (items.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <ListTodo className="w-12 h-12 mx-auto mb-3 text-gray-300" />
        <p>등록된 액션 아이템이 없습니다</p>
      </div>
    );
  }

  return (
    <div>
      {/* 필터 */}
      {showFilter && (
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-4 h-4 text-gray-400" />
          <div className="flex items-center gap-1">
            {FILTER_OPTIONS.map((option) => {
              const Icon = option.icon;
              const isActive = filter === option.value;
              const count = counts[option.value];

              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setFilter(option.value)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                    isActive
                      ? 'bg-blue-100 text-blue-700 font-medium'
                      : 'text-gray-500 hover:bg-gray-100'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{option.label}</span>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded-full ${
                      isActive ? 'bg-blue-200' : 'bg-gray-100'
                    }`}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 목록 */}
      <div className="space-y-2">
        {filteredItems.map((item) => (
          <ActionItemCard
            key={item.id}
            item={item}
            onUpdate={(data) => onUpdate(item.id, data)}
            onDelete={() => onDelete(item.id)}
            isLoading={isLoading}
          />
        ))}
      </div>

      {/* 빈 상태 (필터 적용 시) */}
      {filteredItems.length === 0 && filter !== 'all' && (
        <div className="text-center py-8 text-gray-500">
          <p>'{FILTER_OPTIONS.find((o) => o.value === filter)?.label}' 상태의 항목이 없습니다</p>
        </div>
      )}
    </div>
  );
}
