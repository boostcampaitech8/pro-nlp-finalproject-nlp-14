/**
 * 단일 제안 컴포넌트
 *
 * 제안 내용과 생성된 Draft Decision 링크 표시
 */

import { Lightbulb, ArrowRight, FileText, User, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Suggestion } from '@/types';

interface SuggestionItemProps {
  suggestion: Suggestion;
  onViewDecision?: (decisionId: string) => void;
}

/**
 * AI 생성 중 여부 판단
 * - createdDecision이 있고
 * - status가 'draft'이고
 * - suggestion content와 decision content가 동일하면 → AI가 아직 처리 중
 */
function isAIGenerating(suggestion: Suggestion): boolean {
  if (!suggestion.createdDecision) return false;
  if (suggestion.createdDecision.status !== 'draft') return false;
  return suggestion.content === suggestion.createdDecision.content;
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
      draft: { text: 'Draft', color: 'bg-yellow-500/20 text-yellow-300' },
      latest: { text: 'Latest', color: 'bg-blue-500/20 text-blue-300' },
      approved: { text: 'Approved', color: 'bg-green-500/20 text-green-300' },
      rejected: { text: '부결', color: 'bg-red-500/20 text-red-300' },
      outdated: { text: 'Outdated', color: 'bg-white/10 text-white/50' },
    };
    return labels[status] || labels.draft;
  };

  return (
    <div className="group p-4 bg-gradient-to-r from-amber-500/10 to-orange-500/10 rounded-xl border border-amber-500/20 hover:border-amber-500/30 transition-colors">
      {/* 헤더 */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-full bg-amber-500/20 flex items-center justify-center">
          <Lightbulb className="w-4 h-4 text-amber-400" />
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center">
            <User className="w-3 h-3 text-white/60" />
          </div>
          <span className="font-medium text-sm text-white">{suggestion.author.name}</span>
          <span className="text-amber-400 text-xs font-medium px-2 py-0.5 bg-amber-500/20 rounded-full">
            제안
          </span>
        </div>
        <span className="text-xs text-white/40 ml-auto">{formatDate(suggestion.createdAt)}</span>
      </div>

      {/* 제안 내용 */}
      <div className="text-white/80 mb-3 pl-10 prose prose-sm prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{suggestion.content}</ReactMarkdown>
      </div>

      {/* 생성된 Decision 링크 */}
      {suggestion.createdDecision && (
        <div className="ml-10 mt-3">
          {isAIGenerating(suggestion) ? (
            /* AI 생성 중 - 숨쉬는 애니메이션 + 안내 텍스트 */
            <div className="inline-flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-amber-500/10 to-yellow-500/10 rounded-lg border border-amber-500/30 shadow-sm animate-pulse">
              <div className="relative">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-amber-400 rounded-full animate-ping" />
              </div>
              <div className="flex flex-col">
                <span className="text-xs text-white/50">AI가 새 Decision을 작성하고 있습니다</span>
                <span className="text-sm text-white/50 italic">
                  잠시만 기다려 주세요...
                </span>
              </div>
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400">
                생성 중
              </span>
            </div>
          ) : (
            /* AI 생성 완료 */
            <div className="inline-flex items-center gap-2 px-3 py-2 bg-white/5 rounded-lg border border-amber-500/30 shadow-sm">
              <ArrowRight className="w-4 h-4 text-amber-400" />
              <FileText className="w-4 h-4 text-white/50" />
              <div className="flex flex-col">
                <span className="text-xs text-white/50">새 Decision 생성됨</span>
                <span className="text-sm font-medium text-white line-clamp-1 max-w-xs">
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
                  className="text-xs text-amber-400 hover:text-amber-300 font-medium ml-2"
                >
                  보기
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
