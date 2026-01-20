// 시스템 메시지 버블 컴포넌트
import { motion } from 'framer-motion';
import { Info } from 'lucide-react';
import { messageVariants } from '@/app/constants/animations';
import type { Message } from '@/app/types/conversation';

interface SystemMessageBubbleProps {
  message: Message;
}

export function SystemMessageBubble({ message }: SystemMessageBubbleProps) {
  return (
    <motion.div
      variants={messageVariants.system}
      initial="initial"
      animate="animate"
      exit="exit"
      className="flex justify-center mb-4"
    >
      <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10">
        <Info className="w-3.5 h-3.5 text-white/40" />
        <span className="text-xs text-white/50">{message.content}</span>
      </div>
    </motion.div>
  );
}
