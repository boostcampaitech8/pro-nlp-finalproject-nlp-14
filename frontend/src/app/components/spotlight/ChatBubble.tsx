// 채팅 메시지 버블 컴포넌트
import { useState, useEffect, useRef } from 'react';
import { Bot } from 'lucide-react';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { STREAMING_CHAR_SPEED } from '@/app/constants';
import type { ChatMessage } from '@/app/types/command';
import { Avatar, AvatarFallback, AvatarImage } from '@/app/components/ui';
import { DEFAULT_AI_AGENT } from '@/constants';
import { cn } from '@/lib/utils';

interface ChatBubbleProps {
  message: ChatMessage;
  streaming?: boolean;
  onStreamComplete?: () => void;
}

export function ChatBubble({ message, streaming = false, onStreamComplete }: ChatBubbleProps) {
  const [displayedText, setDisplayedText] = useState(streaming ? '' : message.content);
  const streamingRef = useRef(streaming);

  useEffect(() => {
    streamingRef.current = streaming;
  }, [streaming]);

  // 스트리밍 타이핑 애니메이션
  useEffect(() => {
    if (!streaming) {
      setDisplayedText(message.content);
      return;
    }

    let index = 0;
    setDisplayedText('');

    const timer = setInterval(() => {
      if (index < message.content.length) {
        setDisplayedText(message.content.slice(0, index + 1));
        index++;
      } else {
        clearInterval(timer);
        onStreamComplete?.();
      }
    }, STREAMING_CHAR_SPEED);

    return () => clearInterval(timer);
  }, [message.content, streaming, onStreamComplete]);

  const isUser = message.role === 'user';
  const agentAvatarUrl = DEFAULT_AI_AGENT.avatarUrl;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}
    >
      <div
        className={cn(
          'flex w-full items-end gap-3',
          isUser ? 'justify-end' : 'justify-start'
        )}
      >
        {!isUser && (
          <Avatar className="h-8 w-8 border border-purple-500/30 bg-purple-500/10">
            {agentAvatarUrl ? (
              <AvatarImage src={agentAvatarUrl} alt="부덕이 프로필" />
            ) : null}
            <AvatarFallback className="bg-purple-500/20 text-purple-300">
              <Bot className="w-4 h-4" />
            </AvatarFallback>
          </Avatar>
        )}
        <div
          className={cn(
            'max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
            isUser
              ? 'bg-mit-primary text-white rounded-br-md'
              : 'glass-card text-white/90 rounded-bl-md'
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{displayedText}</p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
              <ReactMarkdown>{displayedText}</ReactMarkdown>
              {streaming && displayedText.length < message.content.length && (
                <span className="inline-block w-0.5 h-4 bg-white/70 ml-0.5 animate-pulse" />
              )}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
