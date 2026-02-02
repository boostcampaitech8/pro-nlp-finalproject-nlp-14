/**
 * 단일 댓글 컴포넌트
 *
 * 재귀적으로 대댓글 렌더링
 * 삭제 기능 (작성자만)
 * AI 응답 대기 표시
 */

import { useState } from 'react';
import { Reply, Trash2, Bot, Loader2, User } from 'lucide-react';
import type { Comment } from '@/types';
import { isAIAgent, isAIAgentByName, AI_AGENTS } from '@/constants';

// 멘션 분리용 패턴 (split에서 캡처 그룹 사용)
const MENTION_SPLIT_PATTERN = new RegExp(
  `(${AI_AGENTS.map((a) => a.mention.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`,
  'gi'
);

interface CommentItemProps {
  comment: Comment;
  decisionId: string;
  currentUserId?: string;
  depth?: number;
  onReply: (commentId: string, content: string) => Promise<void>;
  onDelete: (commentId: string) => Promise<void>;
}

export function CommentItem({
  comment,
  decisionId,
  currentUserId,
  depth = 0,
  onReply,
  onDelete,
}: CommentItemProps) {
  const [showReplyInput, setShowReplyInput] = useState(false);
  const [replyContent, setReplyContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const isAuthor = currentUserId === comment.author.id;
  const isAI = isAIAgent(comment.author.id) || isAIAgentByName(comment.author.name);
  const maxDepth = 3;
  const canReply = depth < maxDepth;

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

  const handleSubmitReply = async () => {
    if (!replyContent.trim() || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onReply(comment.id, replyContent);
      setReplyContent('');
      setShowReplyInput(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (isDeleting) return;
    setIsDeleting(true);
    try {
      await onDelete(comment.id);
    } finally {
      setIsDeleting(false);
    }
  };

  // @부덕이 등 에이전트 멘션 하이라이트
  const renderContent = (text: string) => {
    const parts = text.split(MENTION_SPLIT_PATTERN);
    return parts.map((part, i) => {
      // AI_AGENTS의 mention과 일치하는지 확인
      const isMention =
        part && AI_AGENTS.some((agent) => agent.mention.toLowerCase() === part.toLowerCase());
      return isMention ? (
        <span key={i} className="text-purple-600 font-medium bg-purple-100 px-1 rounded">
          {part}
        </span>
      ) : (
        <span key={i}>{part}</span>
      );
    });
  };

  return (
    <div
      className={`${depth > 0 ? 'ml-6 pl-4 border-l-2 border-gray-100' : ''}`}
      style={{ marginLeft: depth > 0 ? `${depth * 1.5}rem` : 0 }}
    >
      <div
        className={`group p-3 rounded-lg transition-colors ${
          isAI
            ? 'bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-100'
            : 'bg-gray-50 hover:bg-gray-100'
        }`}
      >
        {/* 헤더 */}
        <div className="flex items-center gap-2 mb-2">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center ${
              isAI ? 'bg-purple-200' : 'bg-blue-200'
            }`}
          >
            {isAI ? (
              <Bot className="w-4 h-4 text-purple-700" />
            ) : (
              <User className="w-4 h-4 text-blue-700" />
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className={`font-medium text-sm ${isAI ? 'text-purple-700' : 'text-gray-900'}`}>
              {comment.author.name}
            </span>
            {isAI && (
              <span className="text-xs bg-purple-200 text-purple-700 px-1.5 py-0.5 rounded-full">
                AI
              </span>
            )}
          </div>
          <span className="text-xs text-gray-400">{formatDate(comment.createdAt)}</span>

          {/* 액션 버튼 */}
          <div className="ml-auto flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {canReply && (
              <button
                type="button"
                onClick={() => setShowReplyInput(!showReplyInput)}
                className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                title="답글"
              >
                <Reply className="w-4 h-4" />
              </button>
            )}
            {isAuthor && (
              <button
                type="button"
                onClick={handleDelete}
                disabled={isDeleting}
                className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                title="삭제"
              >
                {isDeleting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </button>
            )}
          </div>
        </div>

        {/* 내용 */}
        <div className="text-gray-700 text-sm whitespace-pre-wrap">
          {renderContent(comment.content)}
        </div>

        {/* AI 응답 대기 표시 */}
        {comment.pendingAgentReply && (
          <div className="mt-2 flex items-center gap-2 text-purple-600 text-xs">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>AI 응답 생성 중...</span>
          </div>
        )}
      </div>

      {/* 답글 입력 */}
      {showReplyInput && (
        <div className="mt-2 ml-4">
          <div className="flex gap-2">
            <textarea
              value={replyContent}
              onChange={(e) => setReplyContent(e.target.value)}
              placeholder="답글을 입력하세요..."
              rows={2}
              className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:border-blue-400 focus:outline-none resize-none"
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault();
                  handleSubmitReply();
                }
              }}
            />
            <div className="flex flex-col gap-1">
              <button
                type="button"
                onClick={handleSubmitReply}
                disabled={!replyContent.trim() || isSubmitting}
                className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  '전송'
                )}
              </button>
              <button
                type="button"
                onClick={() => setShowReplyInput(false)}
                className="px-3 py-1.5 text-gray-500 text-sm hover:text-gray-700"
              >
                취소
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 대댓글 재귀 렌더링 */}
      {comment.replies.length > 0 && (
        <div className="mt-3 space-y-2">
          {comment.replies.map((reply) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              decisionId={decisionId}
              currentUserId={currentUserId}
              depth={depth + 1}
              onReply={onReply}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}
