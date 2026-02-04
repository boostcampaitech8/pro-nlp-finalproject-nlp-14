// 채팅 메시지 흐름 컴포넌트
import { useEffect, useRef } from 'react';
import { useCommandStore } from '@/app/stores/commandStore';
import { useCommand } from '@/app/hooks/useCommand';
import { ChatBubble } from './ChatBubble';
import { PlanBubble } from './PlanBubble';
import { StatusIndicator } from './StatusIndicator';

export function ChatFlow() {
  const { chatMessages, isStreaming, statusMessage, setStreaming } = useCommandStore();
  const { approvePlan } = useCommand();
  const scrollRef = useRef<HTMLDivElement>(null);

  // 새 메시지 또는 상태 변경 시 하단 자동 스크롤
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatMessages, isStreaming, statusMessage]);

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto px-8 py-6">
      <div className="max-w-3xl mx-auto space-y-4">
        {chatMessages.map((msg, index) => {
          // 마지막 에이전트 메시지이면서 스트리밍 중인 경우
          const isLastAgent =
            msg.role === 'agent' && index === chatMessages.length - 1 && isStreaming;

          // plan 타입 메시지
          if (msg.type === 'plan') {
            return (
              <PlanBubble
                key={msg.id}
                message={msg}
                streaming={isLastAgent}
                onStreamComplete={isLastAgent ? () => setStreaming(false) : undefined}
                onApprove={approvePlan}
              />
            );
          }

          return (
            <ChatBubble
              key={msg.id}
              message={msg}
              streaming={isLastAgent}
              onStreamComplete={isLastAgent ? () => setStreaming(false) : undefined}
            />
          );
        })}

        {/* 상태 메시지 표시 (회색 텍스트, 반짝임 효과) */}
        {statusMessage && <StatusIndicator message={statusMessage} />}
      </div>
    </div>
  );
}
