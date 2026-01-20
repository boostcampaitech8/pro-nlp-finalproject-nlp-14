// 에이전트 메시지 버블 컴포넌트
import { motion, AnimatePresence } from 'framer-motion';
import { Bot } from 'lucide-react';
import { messageVariants } from '@/app/constants/animations';
import { TypingIndicator } from './TypingIndicator';
import { EmbeddedForm } from './EmbeddedForm';
import { MarkdownRenderer } from '@/components/ui/MarkdownRenderer';
import type { Message } from '@/app/types/conversation';
import { formatRelativeTime } from '@/app/utils/dateUtils';

interface AgentMessageBubbleProps {
  message: Message;
  onFormSubmit?: () => void;
  onFormCancel?: () => void;
  onFieldChange?: (fieldId: string, value: string) => void;
  isProcessing?: boolean;
}

export function AgentMessageBubble({
  message,
  onFormSubmit,
  onFormCancel,
  onFieldChange,
  isProcessing = false,
}: AgentMessageBubbleProps) {
  const { agentData } = message;
  const isLoading = agentData?.responseType === 'loading';
  const hasForm = agentData?.responseType === 'form' && agentData.form;

  return (
    <motion.div
      variants={messageVariants.agent}
      initial="initial"
      animate="animate"
      exit="exit"
      className="flex justify-start mb-4"
    >
      <div className="flex items-end gap-3 max-w-[80%]">
        {/* 아바타 */}
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-mit-primary to-mit-purple flex items-center justify-center flex-shrink-0">
          <Bot className="w-4 h-4 text-white" />
        </div>

        {/* 메시지 내용 */}
        <div className="flex flex-col items-start">
          <div className="chat-bubble-agent px-4 py-3 rounded-2xl rounded-bl-md">
            <AnimatePresence mode="wait">
              {isLoading ? (
                <TypingIndicator key="loading" />
              ) : (
                <motion.div
                  key="content"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.2 }}
                >
                  {/* 마크다운 콘텐츠가 있으면 렌더링, 없으면 텍스트 메시지 */}
                  {agentData?.responseType === 'result' && agentData.previewData?.content ? (
                    <MarkdownRenderer
                      content={agentData.previewData.content}
                      className="chat-bubble-markdown"
                    />
                  ) : (
                    message.content && (
                      <p className="text-[15px] text-white leading-relaxed">{message.content}</p>
                    )
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* 임베디드 폼 */}
          <AnimatePresence>
            {hasForm && agentData.form && onFormSubmit && onFormCancel && onFieldChange && (
              <EmbeddedForm
                command={agentData.form}
                onSubmit={onFormSubmit}
                onCancel={onFormCancel}
                onFieldChange={onFieldChange}
                isProcessing={isProcessing}
              />
            )}
          </AnimatePresence>

          {/* 타임스탬프 (로딩 아닐 때만) */}
          {!isLoading && (
            <span className="text-[11px] text-white/30 mt-1 ml-1">
              {formatRelativeTime(message.timestamp)}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
