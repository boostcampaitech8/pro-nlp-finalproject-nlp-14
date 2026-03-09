// 대기 중인 메시지 큐 표시 컴포넌트 (입력창 위에 표시)
import { motion, AnimatePresence } from 'framer-motion';
import { useCommand } from '@/app/hooks/useCommand';
import { useCommandStore } from '@/app/stores/commandStore';
import { Loader2, X } from 'lucide-react';

export function PendingMessageQueue() {
  const pendingMessages = useCommandStore((s) => s.pendingMessages);
  const { cancelPendingMessage } = useCommand();

  if (pendingMessages.length === 0) return null;

  return (
    <div className="flex flex-col gap-1.5 mb-2">
      <AnimatePresence mode="popLayout">
        {pendingMessages.map((pending) => (
          <motion.div
            key={pending.id}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="flex justify-end items-center gap-2"
          >
            <Loader2 className="w-3 h-3 text-white/30 animate-spin flex-shrink-0" />
            <div className="px-3 py-2 rounded-2xl rounded-br-md bg-mit-primary/40 border border-mit-primary/20 text-white/60 text-sm max-w-[75%] truncate">
              {pending.text}
            </div>
            <button
              type="button"
              onClick={() => cancelPendingMessage(pending.id)}
              className="p-1 text-white/40 hover:text-white/70 transition-colors"
              title="보내기 취소"
              aria-label="메시지 보내기 취소"
            >
              <X className="w-3 h-3" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
