/**
 * 통합 입력 컴포넌트
 *
 * Comment, Suggestion, Ask 모드를 Shift+Tab으로 전환
 * @부덕이 멘션 지원 (Comment 모드) - Tab으로 자동완성
 */

import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { MessageSquare, Lightbulb, Send, Loader2, Bot } from 'lucide-react';
import {
  AI_AGENTS,
  DEFAULT_AI_AGENT,
  searchAgents,
  hasAgentMention,
  type AIAgent,
} from '@/constants';

type InputMode = 'comment' | 'suggestion' | 'ask';

interface UnifiedInputProps {
  onSubmitComment: (content: string) => Promise<void>;
  onSubmitSuggestion: (content: string) => Promise<void>;
  onSubmitAsk?: (content: string) => Promise<void>;
  isLoading?: boolean;
  placeholder?: string;
  enabledModes?: InputMode[];
  enableMention?: boolean;
}

export function UnifiedInput({
  onSubmitComment,
  onSubmitSuggestion,
  onSubmitAsk,
  isLoading = false,
  placeholder,
  enabledModes = ['comment', 'suggestion', 'ask'],
  enableMention = false,
}: UnifiedInputProps) {
  const [mode, setMode] = useState<InputMode>(enabledModes[0]);
  const [content, setContent] = useState('');
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const modeConfig = {
    comment: {
      icon: MessageSquare,
      label: 'Comment',
      color: 'text-blue-400',
      bgColor: 'bg-blue-500/10',
      borderColor: 'border-blue-500/30 focus-within:border-blue-400',
      placeholder: placeholder || (enableMention
        ? `댓글을 입력하세요... (${DEFAULT_AI_AGENT.mention}으로 AI 멘션)`
        : '댓글을 입력하세요...'),
    },
    suggestion: {
      icon: Lightbulb,
      label: 'Suggestion',
      color: 'text-amber-400',
      bgColor: 'bg-amber-500/10',
      borderColor: 'border-amber-500/30 focus-within:border-amber-400',
      placeholder: placeholder || '수정 제안을 입력하세요...',
    },
    ask: {
      icon: Bot,
      label: 'Ask',
      color: 'text-purple-400',
      bgColor: 'bg-purple-500/10',
      borderColor: 'border-purple-500/30 focus-within:border-purple-400',
      placeholder: placeholder || 'AI에게 질문하세요...',
    },
  };

  const currentConfig = modeConfig[mode];
  const Icon = currentConfig.icon;

  // 자동완성 검색 결과
  const filteredAgents = useMemo(() => {
    if (!mentionQuery) return AI_AGENTS;
    return searchAgents(mentionQuery);
  }, [mentionQuery]);

  const toggleMode = useCallback(() => {
    if (enabledModes.length <= 1) return; // Only one mode, no toggle
    const currentIndex = enabledModes.indexOf(mode);
    const nextIndex = (currentIndex + 1) % enabledModes.length;
    setMode(enabledModes[nextIndex]);
  }, [mode, enabledModes]);

  // @ 뒤의 쿼리 추출
  const extractMentionQuery = useCallback((text: string, cursorPos: number) => {
    const beforeCursor = text.slice(0, cursorPos);
    const match = beforeCursor.match(/@([^\s]*)$/);
    return match ? match[1] : null;
  }, []);

  // 멘션 자동완성 적용
  const applyMention = useCallback(
    (agent: AIAgent) => {
      if (!textareaRef.current) return;

      const cursorPos = textareaRef.current.selectionStart;
      const beforeCursor = content.slice(0, cursorPos);
      const afterCursor = content.slice(cursorPos);

      // @ 위치 찾기
      const atIndex = beforeCursor.lastIndexOf('@');
      if (atIndex === -1) return;

      // @query를 @부덕이로 교체
      const newContent = beforeCursor.slice(0, atIndex) + agent.mention + ' ' + afterCursor;
      setContent(newContent);
      setShowSuggestions(false);
      setMentionQuery('');

      // 커서 위치 조정
      setTimeout(() => {
        if (textareaRef.current) {
          const newCursorPos = atIndex + agent.mention.length + 1;
          textareaRef.current.selectionStart = newCursorPos;
          textareaRef.current.selectionEnd = newCursorPos;
          textareaRef.current.focus();
        }
      }, 0);
    },
    [content]
  );

  const handleSubmit = useCallback(async () => {
    const trimmed = content.trim();
    if (!trimmed || isLoading) return;

    try {
      if (mode === 'comment') {
        await onSubmitComment(trimmed);
      } else if (mode === 'suggestion') {
        await onSubmitSuggestion(trimmed);
      } else if (mode === 'ask') {
        // Ask 모드: @mit prefix를 붙여서 AI 응답 트리거
        const askContent = `${DEFAULT_AI_AGENT.mention} ${trimmed}`;
        if (onSubmitAsk) {
          await onSubmitAsk(askContent);
        } else {
          // onSubmitAsk가 없으면 onSubmitComment로 fallback
          await onSubmitComment(askContent);
        }
      }
      setContent('');
    } catch {
      // 에러는 부모에서 처리
    }
  }, [content, isLoading, mode, onSubmitComment, onSubmitSuggestion, onSubmitAsk]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // 자동완성 드롭다운이 열려있을 때
      if (showSuggestions && filteredAgents.length > 0) {
        if (e.key === 'Tab' || e.key === 'Enter') {
          e.preventDefault();
          applyMention(filteredAgents[selectedIndex]);
          return;
        }
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          setSelectedIndex((prev) => (prev + 1) % filteredAgents.length);
          return;
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault();
          setSelectedIndex((prev) => (prev - 1 + filteredAgents.length) % filteredAgents.length);
          return;
        }
        if (e.key === 'Escape') {
          e.preventDefault();
          setShowSuggestions(false);
          return;
        }
      }

      // Shift+Tab: 모드 전환 (자동완성이 안 열려있을 때만)
      if (e.shiftKey && e.key === 'Tab') {
        e.preventDefault();
        toggleMode();
        return;
      }

      // Cmd/Ctrl+Enter: 제출
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        handleSubmit();
        return;
      }
    },
    [toggleMode, handleSubmit, showSuggestions, filteredAgents, selectedIndex, applyMention]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const newContent = e.target.value;
      const cursorPos = e.target.selectionStart;
      setContent(newContent);

      // enableMention이 활성화되고 Comment 모드일 때만 @ 감지
      if (enableMention && mode === 'comment') {
        const query = extractMentionQuery(newContent, cursorPos);
        if (query !== null) {
          setMentionQuery(query);
          setShowSuggestions(true);
          setSelectedIndex(0);
        } else {
          setShowSuggestions(false);
          setMentionQuery('');
        }
      }
    },
    [mode, extractMentionQuery, enableMention]
  );

  // 자동 높이 조절
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [content]);

  // 멘션 하이라이트 표시
  const showMentionBadge = enableMention && mode === 'comment' && hasAgentMention(content);

  // 입력 중 멘션 하이라이트 렌더링 (overlay용)
  const renderHighlightedContent = useCallback((text: string) => {
    if (!enableMention || mode !== 'comment' || !text) {
      return <span className="whitespace-pre-wrap">{text || '\u00A0'}</span>;
    }

    // 멘션 패턴으로 분리
    const pattern = new RegExp(
      `(${AI_AGENTS.map((a) => a.mention.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`,
      'gi'
    );
    const parts = text.split(pattern);

    return (
      <span className="whitespace-pre-wrap">
        {parts.map((part, i) => {
          const isMention = AI_AGENTS.some(
            (agent) => agent.mention.toLowerCase() === part.toLowerCase()
          );
          return isMention ? (
            <span key={i} className="bg-purple-500/30 text-purple-300">
              {part}
            </span>
          ) : (
            <span key={i}>{part}</span>
          );
        })}
      </span>
    );
  }, [mode, enableMention]);

  return (
    <div className="relative">
      {/* 입력 영역 */}
      <div
        className={`relative rounded-lg border-2 transition-colors ${currentConfig.borderColor} ${currentConfig.bgColor}`}
      >
        <div className="flex items-start gap-2 p-3">
          {/* 모드 인디케이터 (클릭으로 전환 가능) */}
          <button
            type="button"
            onClick={toggleMode}
            disabled={enabledModes.length <= 1}
            className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium transition-colors flex-shrink-0 ${
              mode === 'comment'
                ? 'bg-blue-500/20 text-blue-300'
                : mode === 'suggestion'
                ? 'bg-amber-500/20 text-amber-300'
                : 'bg-purple-500/20 text-purple-300'
            } ${
              enabledModes.length > 1
                ? mode === 'comment'
                  ? 'hover:bg-blue-500/30 cursor-pointer'
                  : mode === 'suggestion'
                  ? 'hover:bg-amber-500/30 cursor-pointer'
                  : 'hover:bg-purple-500/30 cursor-pointer'
                : 'cursor-default'
            }`}
            title={enabledModes.length > 1 ? 'Shift+Tab으로 전환' : ''}
          >
            <Icon className="w-3 h-3" />
            {currentConfig.label}
          </button>
          {/* 텍스트 입력 영역 with 멘션 하이라이트 */}
          <div className="flex-1 relative min-h-[24px]">
            {/* 하이라이트 오버레이 (textarea 뒤에 렌더링) */}
            <div
              className="absolute inset-0 text-sm leading-normal pointer-events-none overflow-hidden text-white/80"
              aria-hidden="true"
            >
              {renderHighlightedContent(content)}
              {!content && (
                <span className="text-white/40">{currentConfig.placeholder}</span>
              )}
            </div>
            {/* 실제 textarea (투명 텍스트, caret만 표시) */}
            <textarea
              ref={textareaRef}
              value={content}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
              placeholder=""
              disabled={isLoading}
              rows={1}
              className="w-full bg-transparent resize-none outline-none min-h-[24px] disabled:opacity-50 text-transparent caret-white text-sm leading-normal"
              style={{ caretColor: '#ffffff' }}
            />
          </div>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!content.trim() || isLoading}
            className={`p-2 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
              mode === 'comment'
                ? 'bg-blue-600 hover:bg-blue-700 text-white'
                : mode === 'suggestion'
                ? 'bg-amber-600 hover:bg-amber-700 text-white'
                : 'bg-purple-600 hover:bg-purple-700 text-white'
            }`}
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* 멘션 자동완성 드롭다운 */}
        {enableMention && showSuggestions && filteredAgents.length > 0 && (
          <div className="absolute left-3 bottom-full mb-1 bg-gray-800 rounded-lg shadow-lg border border-white/10 py-1 z-10 min-w-[180px]">
            {filteredAgents.map((agent, index) => (
              <button
                key={agent.id + agent.mention}
                type="button"
                onClick={() => applyMention(agent)}
                className={`w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors ${
                  index === selectedIndex
                    ? 'bg-purple-500/20 text-purple-300'
                    : 'text-white/80 hover:bg-white/10'
                }`}
              >
                {agent.avatarUrl ? (
                  <img
                    src={agent.avatarUrl}
                    alt={`${agent.displayName} 프로필`}
                    className="w-4 h-4 rounded-full object-cover border border-purple-500/30"
                  />
                ) : (
                  <Bot className="w-4 h-4 text-purple-400" />
                )}
                <div>
                  <div className="font-medium">{agent.displayName}</div>
                  <div className="text-xs text-white/50">{agent.description}</div>
                </div>
              </button>
            ))}
            <div className="px-3 py-1 text-xs text-white/40 border-t border-white/10">
              Tab 또는 Enter로 선택
            </div>
          </div>
        )}

        {/* 멘션 표시 뱃지 */}
        {showMentionBadge && (
          <span className="absolute right-12 top-1/2 -translate-y-1/2 text-xs text-purple-300 bg-purple-500/20 px-2 py-0.5 rounded-full">
            AI 응답 요청
          </span>
        )}
      </div>

      {/* 힌트 */}
      <div className="flex items-center justify-between mt-1.5 text-xs text-white/40">
        <span>Cmd/Ctrl + Enter로 전송</span>
        {mode === 'suggestion' && (
          <span className="text-amber-400">제안 시 새로운 Draft Decision이 생성됩니다</span>
        )}
        {mode === 'ask' && (
          <span className="text-purple-400">AI가 결정사항을 바탕으로 답변합니다</span>
        )}
      </div>
    </div>
  );
}
