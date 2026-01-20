// 메시지 목록 컴포넌트 (자동 스크롤)
import { useEffect, useRef } from 'react';
import { AnimatePresence } from 'framer-motion';
import { ChatMessage } from './ChatMessage';
import { ScrollArea } from '@/app/components/ui';
import type { Message } from '@/app/types/conversation';

interface ChatMessageListProps {
  messages: Message[];
  onFormSubmit?: () => void;
  onFormCancel?: () => void;
  onFieldChange?: (fieldId: string, value: string) => void;
  isProcessing?: boolean;
}

export function ChatMessageList({
  messages,
  onFormSubmit,
  onFormCancel,
  onFieldChange,
  isProcessing,
}: ChatMessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // 새 메시지 시 자동 스크롤
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // 마지막 에이전트 메시지 찾기 (폼 처리용)
  const lastAgentMessageIndex = messages.reduce(
    (lastIndex: number, msg: Message, index: number) =>
      msg.type === 'agent' ? index : lastIndex,
    -1
  );

  return (
    <ScrollArea className="flex-1 px-4">
      <div ref={scrollRef} className="py-6 space-y-2">
        <AnimatePresence mode="popLayout">
          {messages.map((message, index) => (
            <ChatMessage
              key={message.id}
              message={message}
              // 마지막 에이전트 메시지에만 폼 핸들러 전달
              onFormSubmit={index === lastAgentMessageIndex ? onFormSubmit : undefined}
              onFormCancel={index === lastAgentMessageIndex ? onFormCancel : undefined}
              onFieldChange={index === lastAgentMessageIndex ? onFieldChange : undefined}
              isProcessing={index === lastAgentMessageIndex ? isProcessing : undefined}
            />
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
