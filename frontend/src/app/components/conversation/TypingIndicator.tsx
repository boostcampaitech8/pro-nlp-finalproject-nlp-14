// 타이핑 인디케이터 컴포넌트
import { motion } from 'framer-motion';
import { typingIndicatorVariants, typingDotVariants } from '@/app/constants/animations';

export function TypingIndicator() {
  return (
    <motion.div
      variants={typingIndicatorVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className="flex items-center gap-1 px-4 py-3"
    >
      <div className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            variants={typingDotVariants}
            animate="animate"
            style={{ animationDelay: `${i * 0.15}s` }}
            className="w-2 h-2 rounded-full bg-white/40"
          />
        ))}
      </div>
      <span className="ml-2 text-sm text-white/40">Mit이 생각하고 있습니다...</span>
    </motion.div>
  );
}
