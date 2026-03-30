// Plan 응답 버블 컴포넌트
// ==값== 패턴을 파싱하여 인라인 편집 가능한 필드로 렌더링
import { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Check } from 'lucide-react';
import { STREAMING_CHAR_SPEED, PLAN_FIELD_REGEX } from '@/app/constants';
import type { ChatMessage, PlanSegment } from '@/app/types/command';
import { cn } from '@/lib/utils';

interface PlanBubbleProps {
  message: ChatMessage;
  streaming?: boolean;
  onStreamComplete?: () => void;
  onApprove?: (messageId: string) => void;
}

// ==값== 패턴을 PlanSegment 배열로 파싱
function parsePlanContent(content: string): PlanSegment[] {
  const segments: PlanSegment[] = [];
  const regex = new RegExp(PLAN_FIELD_REGEX.source, 'g');
  let lastIndex = 0;
  let fieldIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(content)) !== null) {
    // match 이전 텍스트
    if (match.index > lastIndex) {
      segments.push({ type: 'text', value: content.slice(lastIndex, match.index) });
    }
    // 필드
    segments.push({
      type: 'field',
      id: `field-${fieldIndex++}`,
      defaultValue: match[1],
    });
    lastIndex = regex.lastIndex;
  }

  // 나머지 텍스트
  if (lastIndex < content.length) {
    segments.push({ type: 'text', value: content.slice(lastIndex) });
  }

  return segments;
}

export function PlanBubble({
  message,
  streaming = false,
  onStreamComplete,
  onApprove,
}: PlanBubbleProps) {
  const [displayedText, setDisplayedText] = useState(streaming ? '' : message.content);
  const [isStreamingDone, setIsStreamingDone] = useState(!streaming);
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({});
  const streamingRef = useRef(streaming);

  useEffect(() => {
    streamingRef.current = streaming;
  }, [streaming]);

  // 스트리밍 타이핑 애니메이션
  useEffect(() => {
    if (!streaming) {
      setDisplayedText(message.content);
      setIsStreamingDone(true);
      return;
    }

    let index = 0;
    setDisplayedText('');
    setIsStreamingDone(false);

    const timer = setInterval(() => {
      if (index < message.content.length) {
        setDisplayedText(message.content.slice(0, index + 1));
        index++;
      } else {
        clearInterval(timer);
        setIsStreamingDone(true);
        onStreamComplete?.();
      }
    }, STREAMING_CHAR_SPEED);

    return () => clearInterval(timer);
  }, [message.content, streaming, onStreamComplete]);

  const segments = isStreamingDone ? parsePlanContent(message.content) : [];

  const handleFieldChange = useCallback((fieldId: string, value: string) => {
    setFieldValues((prev) => ({ ...prev, [fieldId]: value }));
  }, []);

  const handleApprove = useCallback(() => {
    onApprove?.(message.id);
  }, [onApprove, message.id]);

  const isApproved = message.approved === true;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex w-full justify-start"
    >
      <div className="max-w-[85%] rounded-2xl px-5 py-4 glass-card text-white/90 rounded-bl-md">
        {/* 스트리밍 중: 일반 텍스트 타이핑 */}
        {!isStreamingDone && (
          <div className="text-sm leading-relaxed whitespace-pre-wrap">
            {displayedText}
            <span className="inline-block w-0.5 h-4 bg-white/70 ml-0.5 animate-pulse" />
          </div>
        )}

        {/* 스트리밍 완료: 세그먼트 파싱 + 인라인 필드 */}
        {isStreamingDone && (
          <>
            <div className="text-sm leading-relaxed whitespace-pre-wrap">
              {segments.map((seg) => {
                if (seg.type === 'text') {
                  return <span key={seg.value.slice(0, 20) + segments.indexOf(seg)}>{seg.value}</span>;
                }
                // 필드 세그먼트
                const currentValue = fieldValues[seg.id] ?? seg.defaultValue;
                return (
                  <input
                    key={seg.id}
                    type="text"
                    value={currentValue}
                    onChange={(e) => handleFieldChange(seg.id, e.target.value)}
                    onFocus={(e) => e.target.select()}
                    disabled={isApproved}
                    className={cn(
                      'inline-block bg-yellow-400/20 border border-yellow-400/30 rounded px-1.5 py-0.5',
                      'text-yellow-200 text-sm outline-none transition-all',
                      'focus:border-yellow-400/60 focus:ring-1 focus:ring-yellow-400/30',
                      'min-w-[60px]',
                      isApproved && 'opacity-60 cursor-default'
                    )}
                    style={{ width: `${Math.max(currentValue.length + 2, 6)}ch` }}
                  />
                );
              })}
            </div>

            {/* 승인 버튼 영역 */}
            <div className="mt-4 flex justify-end items-center gap-2">
              {isApproved ? (
                <span className="flex items-center gap-1 text-xs text-mit-success">
                  <Check className="w-3.5 h-3.5" />
                  승인됨
                </span>
              ) : (
                <button
                  onClick={handleApprove}
                  className={cn(
                    'px-4 py-1.5 rounded-lg text-sm font-medium transition-all',
                    'bg-mit-primary hover:bg-mit-primary/80 text-white',
                    'focus:outline-none focus:ring-2 focus:ring-mit-primary/40'
                  )}
                >
                  승인
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </motion.div>
  );
}
