// 사용자 메시지 버블 컴포넌트
import { motion } from 'framer-motion';
import { User } from 'lucide-react';
import { messageVariants } from '@/app/constants/animations';
import type { Message } from '@/app/types/conversation';
import { formatRelativeTime } from '@/app/utils/dateUtils';

interface UserMessageBubbleProps {
  message: Message;
}

export function UserMessageBubble({ message }: UserMessageBubbleProps) {
  return (
    <motion.div
      variants={messageVariants.user}
      initial="initial"
      animate="animate"
      exit="exit"
      className="flex justify-end mb-4"
    >
      <div className="flex items-end gap-3 max-w-[80%]">
        {/* 메시지 내용 */}
        <div className="flex flex-col items-end">
          <div className="chat-bubble-user px-4 py-3 rounded-2xl rounded-br-md">
            <p className="text-[15px] text-white leading-relaxed">{message.content}</p>

            {/* 폼 요약 (폼 제출 후 표시) */}
            {message.userData?.formSummary && (
              <div className="mt-2 pt-2 border-t border-white/10">
                {Object.entries(message.userData.formSummary).map(([key, value]) => (
                  <div key={key} className="text-xs text-white/60">
                    <span className="text-white/40">{key}:</span> {value}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 타임스탬프 */}
          <span className="text-[11px] text-white/30 mt-1 mr-1">
            {formatRelativeTime(message.timestamp)}
          </span>
        </div>

        {/* 아바타 */}
        <div className="w-8 h-8 rounded-full bg-mit-primary/30 flex items-center justify-center flex-shrink-0">
          <User className="w-4 h-4 text-mit-primary" />
        </div>
      </div>
    </motion.div>
  );
}
