/**
 * 단일 댓글 컴포넌트
 *
 * 재귀적으로 대댓글 렌더링
 * 삭제 기능 (작성자만)
 * AI 응답 대기 표시
 * SSE를 통한 실시간 업데이트
 */

import { useState, useEffect, useRef } from 'react';
import { Reply, Trash2, Bot, Loader2, User, AlertCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Comment } from '@/types';
import { isAIAgent, isAIAgentByName } from '@/constants';
import { UnifiedInput } from './UnifiedInput';

interface CommentItemProps {
  comment: Comment;
  decisionId: string;
  currentUserId?: string;
  depth?: number;
  onReply: (commentId: string, content: string) => Promise<void>;
  onDelete: (commentId: string) => Promise<void>;
  onRefresh?: () => void;
}

export function CommentItem({
  comment,
  decisionId,
  currentUserId,
  depth = 0,
  onReply,
  onDelete,
  onRefresh,
}: CommentItemProps) {
  const [showReplyInput, setShowReplyInput] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [displayedContent, setDisplayedContent] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const typingIntervalRef = useRef<number | null>(null);
  const previousContentRef = useRef<string>('');

  const isAuthor = currentUserId === comment.author.id;
  const isAI = isAIAgent(comment.author.id) || isAIAgentByName(comment.author.name);
  const maxDepth = 3;
  const canReply = depth < maxDepth;

  // Typing effect for AI responses
  useEffect(() => {
    // Only apply typing effect to AI comments
    if (!isAI || comment.isErrorResponse) {
      setDisplayedContent(comment.content);
      return;
    }

    // Check if this is a new or updated AI response
    const isNewContent = previousContentRef.current !== comment.content;
    previousContentRef.current = comment.content;

    if (!isNewContent) {
      setDisplayedContent(comment.content);
      return;
    }

    // Start typing effect
    setIsTyping(true);
    setDisplayedContent('');
    let index = 0;
    const content = comment.content;
    const typingSpeed = 15; // milliseconds per character

    // Clear any existing interval
    if (typingIntervalRef.current) {
      clearInterval(typingIntervalRef.current);
    }

    typingIntervalRef.current = setInterval(() => {
      if (index < content.length) {
        setDisplayedContent(content.slice(0, index + 1));
        index++;
      } else {
        if (typingIntervalRef.current) {
          clearInterval(typingIntervalRef.current);
          typingIntervalRef.current = null;
        }
        setIsTyping(false);
      }
    }, typingSpeed);

    // Cleanup on unmount or when dependencies change
    return () => {
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current);
        typingIntervalRef.current = null;
      }
    };
  }, [comment.content, isAI, comment.isErrorResponse]);

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

  const handleSubmitReply = async (content: string) => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onReply(comment.id, content);
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

  return (
    <div
      className={`${depth > 0 ? 'ml-6 pl-4 border-l-2 border-gray-100' : ''}`}
      style={{ marginLeft: depth > 0 ? `${depth * 1.5}rem` : 0 }}
    >
      <div
        className={`group p-3 rounded-lg transition-colors ${
          comment.isErrorResponse
            ? 'bg-red-50 border border-red-200'
            : isAI
              ? 'bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-100'
              : 'bg-gray-50 hover:bg-gray-100'
        }`}
      >
        {/* 헤더 */}
        <div className="flex items-center gap-2 mb-2">
          <div
            className={`w-7 h-7 rounded-full flex items-center justify-center ${
              comment.isErrorResponse
                ? 'bg-red-200'
                : isAI
                  ? 'bg-purple-200'
                  : 'bg-blue-200'
            }`}
          >
            {comment.isErrorResponse ? (
              <AlertCircle className="w-4 h-4 text-red-700" />
            ) : isAI ? (
              <Bot className="w-4 h-4 text-purple-700" />
            ) : (
              <User className="w-4 h-4 text-blue-700" />
            )}
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`font-medium text-sm ${
                comment.isErrorResponse
                  ? 'text-red-700'
                  : isAI
                    ? 'text-purple-700'
                    : 'text-gray-900'
              }`}
            >
              {comment.author.name}
            </span>
            {comment.isErrorResponse && (
              <span className="text-xs bg-red-200 text-red-700 px-1.5 py-0.5 rounded-full">
                에러
              </span>
            )}
            {isAI && !comment.isErrorResponse && (
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
        <div
          className={`text-sm ${
            comment.isErrorResponse ? 'text-red-700' : 'text-gray-700'
          }`}
        >
          {/* 모든 댓글에 마크다운 렌더링 적용 */}
          <div className="prose prose-sm max-w-none prose-gray prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-headings:my-2 prose-headings:text-gray-800 prose-strong:text-gray-800 prose-code:text-purple-700 prose-code:bg-purple-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none prose-pre:bg-gray-800 prose-pre:text-gray-100">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {isAI && !comment.isErrorResponse ? displayedContent : comment.content}
            </ReactMarkdown>
            {isTyping && (
              <span className="inline-block w-1 h-4 ml-0.5 bg-purple-600 animate-pulse" />
            )}
          </div>
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
          <UnifiedInput
            onSubmitComment={handleSubmitReply}
            onSubmitSuggestion={async () => {}}
            onSubmitAsk={handleSubmitReply}
            enabledModes={['comment', 'ask']}
            isLoading={isSubmitting}
            placeholder="답글을 입력하세요..."
          />
          <button
            type="button"
            onClick={() => setShowReplyInput(false)}
            className="mt-1 px-3 py-1 text-gray-500 text-xs hover:text-gray-700"
          >
            취소
          </button>
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
              onRefresh={onRefresh}
            />
          ))}
        </div>
      )}
    </div>
  );
}
