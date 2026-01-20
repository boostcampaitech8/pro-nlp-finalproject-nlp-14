// 대화 모드 메인 컨테이너
import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { ChatMessageList } from './ChatMessageList';
import { ChatSpotlightInput } from './ChatSpotlightInput';
import { useConversationCommand } from '@/app/hooks/useConversationCommand';
import { useConversationStore } from '@/app/stores/conversationStore';
import { modeTransitionVariants } from '@/app/constants/animations';
import { LAYOUT_CONFIGS } from '@/app/constants/layoutConfig';
import { cn } from '@/lib/utils';

export function ConversationContainer() {
  const { messages, pendingForm, layoutMode, endConversation } = useConversationStore();

  // 글로벌 ESC 키 이벤트로 대화 종료
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        endConversation();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [endConversation]);
  const {
    submitCommand,
    submitForm,
    cancelForm,
    updateFormField,
    isProcessing,
  } = useConversationCommand();

  const config = LAYOUT_CONFIGS[layoutMode];

  return (
    <motion.div
      variants={modeTransitionVariants.conversationContainer}
      initial="initial"
      animate="animate"
      exit="exit"
      className="flex-1 flex flex-col overflow-hidden"
    >
      {/* 대화 영역 */}
      <div className={cn('flex-1 flex flex-col overflow-hidden mx-auto w-full', config.conversationMaxWidth)}>
        {/* 메시지 목록 */}
        <ChatMessageList
          messages={messages}
          onFormSubmit={submitForm}
          onFormCancel={cancelForm}
          onFieldChange={updateFormField}
          isProcessing={isProcessing}
        />

        {/* 하단 입력창 */}
        <ChatSpotlightInput
          onSubmit={submitCommand}
          isProcessing={isProcessing}
          placeholder={pendingForm ? '폼을 작성하거나 새 명령을 입력하세요...' : 'Mit에게 무엇이든 물어보세요...'}
        />
      </div>
    </motion.div>
  );
}
