/**
 * 단일 제안 컴포넌트
 *
 * 제안 내용과 생성된 Draft Decision 링크 표시
 */

import { Lightbulb, ArrowRight, FileText, User } from 'lucide-react';
import type { Suggestion } from '@/types';

interface SuggestionItemProps {
  suggestion: Suggestion;
  onViewDecision?: (decisionId: string) => void;
}

export function SuggestionItem({ suggestion, onViewDecision }: SuggestionItemProps) {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return '방금 전';
    if (minutes < 60) return `${minutes}분 전`;
    if (hours < 24) return `${hours}시간 전`;
    if (days < 7) return `${days}일 전`;
    return date.toLocaleDateString('ko-KR');
  };

  const statusLabel = (status: string) => {
    const labels: Record<string, { text: string; color: string }> = {
      draft: { text: 'Draft', color: 'bg-yellow-100 text-yellow-700' },
      latest: { text: 'Latest', color: 'bg-blue-100 text-blue-700' },
      approved: { text: 'Approved', color: 'bg-green-100 text-green-700' },
      rejected: { text: 'Rejected', color: 'bg-red-100 text-red-700' },
      outdated: { text: 'Outdated', color: 'bg-gray-100 text-gray-600' },
    };
    return labels[status] || labels.draft;
  };

  return (
    <div className="group p-4 bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl border border-amber-100 hover:border-amber-200 transition-colors">
      {/* 헤더 */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-full bg-amber-200 flex items-center justify-center">
          <Lightbulb className="w-4 h-4 text-amber-700" />
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-gray-200 flex items-center justify-center">
            <User className="w-3 h-3 text-gray-600" />
          </div>
          <span className="font-medium text-sm text-gray-900">{suggestion.author.name}</span>
          <span className="text-amber-600 text-xs font-medium px-2 py-0.5 bg-amber-100 rounded-full">
            제안
          </span>
        </div>
        <span className="text-xs text-gray-400 ml-auto">{formatDate(suggestion.createdAt)}</span>
      </div>

      {/* 제안 내용 */}
      <div className="text-gray-700 whitespace-pre-wrap mb-3 pl-10">
        {suggestion.content}
      </div>

      {/* 생성된 Decision 링크 */}
      {suggestion.createdDecision && (
        <div className="ml-10 mt-3">
          <div className="inline-flex items-center gap-2 px-3 py-2 bg-white rounded-lg border border-amber-200 shadow-sm">
            <ArrowRight className="w-4 h-4 text-amber-500" />
            <FileText className="w-4 h-4 text-gray-500" />
            <div className="flex flex-col">
              <span className="text-xs text-gray-500">새 Decision 생성됨</span>
              <span className="text-sm font-medium text-gray-900 line-clamp-1 max-w-xs">
                {suggestion.createdDecision.content.substring(0, 50)}
                {suggestion.createdDecision.content.length > 50 && '...'}
              </span>
            </div>
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${
                statusLabel(suggestion.createdDecision.status).color
              }`}
            >
              {statusLabel(suggestion.createdDecision.status).text}
            </span>
            {onViewDecision && (
              <button
                type="button"
                onClick={() => onViewDecision(suggestion.createdDecision!.id)}
                className="text-xs text-amber-600 hover:text-amber-700 font-medium ml-2"
              >
                보기
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
