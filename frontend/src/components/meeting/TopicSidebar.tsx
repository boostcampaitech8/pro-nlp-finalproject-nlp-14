/**
 * TopicSidebar - 왼쪽 고정 토픽 리스트 + 클릭 상세 카드
 */

import {
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { TopicItem } from '@/types';

interface TopicSidebarProps {
  topics: TopicItem[];
  isL1Running: boolean;
  pendingChunks: number;
}

type TopicStatus = 'active' | 'pending' | 'completed';

function getTopicStatus(
  topic: TopicItem,
  latestTurn: number,
  recentWindowStartTurn: number,
  isL1Running: boolean
): TopicStatus {
  const overlapsRecentWindow =
    topic.endTurn >= recentWindowStartTurn && topic.startTurn <= latestTurn;

  if (overlapsRecentWindow) {
    return 'active';
  }

  // 최근 25턴 직전 구간은 처리 중 상태로 표시
  if (
    isL1Running &&
    topic.endTurn < recentWindowStartTurn &&
    topic.endTurn >= recentWindowStartTurn - 25
  ) {
    return 'pending';
  }

  return 'completed';
}

function statusLabel(status: TopicStatus): string {
  switch (status) {
    case 'active':
      return 'Active';
    case 'pending':
      return 'Pending';
    default:
      return 'Completed';
  }
}

function StatusMark({ status }: { status: TopicStatus }) {
  if (status === 'active') {
    return (
      <span
        aria-label="active-topic"
        className="h-[6px] w-[6px] shrink-0 rounded-full bg-green-400"
      />
    );
  }

  return (
    <span
      aria-label={status === 'pending' ? 'pending-topic' : 'completed-topic'}
      className="h-[6px] w-[6px] shrink-0 rounded-full border border-gray-400 bg-transparent"
    />
  );
}

export function TopicSidebar({
  topics,
  isL1Running,
  pendingChunks,
}: TopicSidebarProps) {
  const [selectedTopic, setSelectedTopic] = useState<TopicItem | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<TopicStatus>('completed');

  const hasTopics = topics.length > 0;
  const latestTurn = useMemo(() => {
    if (topics.length === 0) return 0;
    return topics.reduce((max, topic) => Math.max(max, topic.endTurn), 0);
  }, [topics]);
  const recentWindowStartTurn = Math.max(1, latestTurn - 24);

  const processingText = useMemo(() => {
    if (isL1Running || pendingChunks > 0) {
      return `분석 중${pendingChunks > 0 ? ` · ${pendingChunks}` : ''}`;
    }
    return '';
  }, [isL1Running, pendingChunks]);

  useEffect(() => {
    if (selectedTopic && !topics.some((topic) => topic.id === selectedTopic.id)) {
      setSelectedTopic(null);
    }
  }, [selectedTopic, topics]);

  const handleItemClick = (topic: TopicItem, status: TopicStatus) => {
    if (selectedTopic?.id === topic.id) {
      setSelectedTopic(null);
      return;
    }

    setSelectedTopic(topic);
    setSelectedStatus(status);
  };

  return (
    <aside className="w-[270px] shrink-0 border-r border-slate-700 bg-slate-900">
      <div className="flex h-full min-h-0 flex-col">
        <div className="border-b border-slate-700 px-4 py-3">
          <div className="flex items-center justify-between">
            <span className="text-white font-medium flex items-center gap-2">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 8h10M7 12h6m-6 4h10"
                />
              </svg>
              토픽 ({topics.length})
            </span>
            {processingText && (
              <span className="text-xs text-slate-400">{processingText}</span>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {hasTopics && (
            <ul className="space-y-1.5">
              {topics.map((topic) => {
                const status = getTopicStatus(
                  topic,
                  latestTurn,
                  recentWindowStartTurn,
                  isL1Running,
                );

                const isActive = status === 'active';
                const isSelected = selectedTopic?.id === topic.id;

                return (
                  <li key={topic.id}>
                    <button
                      type="button"
                      onClick={() => handleItemClick(topic, status)}
                      aria-pressed={isSelected}
                      className={[
                        'group w-full rounded-lg px-1.5 py-2 text-left',
                        'transition-colors duration-150',
                        isSelected
                          ? 'bg-slate-800/65 text-slate-100'
                          : isActive
                            ? 'bg-transparent text-slate-100 hover:bg-slate-800/55'
                            : 'bg-transparent text-slate-400 hover:bg-slate-800/55 hover:text-slate-100',
                      ].join(' ')}
                    >
                      <div className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-2">
                        <StatusMark status={status} />
                        <span className="min-w-0 flex-1 truncate text-[13.5px] font-medium leading-5">
                          {topic.name}
                        </span>
                      </div>
                    </button>

                    <div
                      className={[
                        'overflow-hidden transition-all duration-200 ease-out',
                        isSelected
                          ? 'mt-2 max-h-72 translate-y-0 opacity-100'
                          : 'max-h-0 -translate-y-1 opacity-0',
                      ].join(' ')}
                    >
                      {isSelected && (
                        <div className="rounded-lg border border-slate-700 bg-slate-800/70 p-3">
                          <p className="mb-2 text-[11px] text-slate-400">
                            {statusLabel(selectedStatus)} · #{topic.startTurn}-{topic.endTurn}
                          </p>

                          <p className="whitespace-pre-wrap text-xs leading-relaxed text-slate-200">
                            {topic.summary}
                          </p>

                          {topic.keywords.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {topic.keywords.slice(0, 6).map((keyword, idx) => (
                                <span
                                  key={`${topic.id}-kw-${idx}`}
                                  className="rounded bg-slate-700/70 px-1.5 py-0.5 text-[10px] text-slate-300"
                                >
                                  {keyword}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </aside>
  );
}
