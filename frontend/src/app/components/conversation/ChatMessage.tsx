// 메시지 라우터 컴포넌트
import { UserMessageBubble } from './UserMessageBubble';
import { AgentMessageBubble } from './AgentMessageBubble';
import { SystemMessageBubble } from './SystemMessageBubble';
import type { Message } from '@/app/types/conversation';

interface ChatMessageProps {
  message: Message;
  onFormSubmit?: () => void;
  onFormCancel?: () => void;
  onFieldChange?: (fieldId: string, value: string) => void;
  isProcessing?: boolean;
}

export function ChatMessage({
  message,
  onFormSubmit,
  onFormCancel,
  onFieldChange,
  isProcessing,
}: ChatMessageProps) {
  switch (message.type) {
    case 'user':
      return <UserMessageBubble message={message} />;
    case 'agent':
      return (
        <AgentMessageBubble
          message={message}
          onFormSubmit={onFormSubmit}
          onFormCancel={onFormCancel}
          onFieldChange={onFieldChange}
          isProcessing={isProcessing}
        />
      );
    case 'system':
      return <SystemMessageBubble message={message} />;
    default:
      return null;
  }
}
