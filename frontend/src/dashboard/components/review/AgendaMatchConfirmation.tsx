/**
 * 아젠다 매칭 확인 컴포넌트
 *
 * Hybrid Agenda Matcher 결과 확인 UI:
 * - matchStatus가 'needs_confirmation'일 때 확인 배지 표시
 * - 클릭 시 모달로 후보 아젠다 정보와 함께 confirm/ignore 버튼 제공
 */

import { useState, memo } from 'react';
import { AlertCircle, CheckCircle2, X } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import type { AgendaWithDecisions } from '@/types';

export interface AgendaMatchConfirmationProps {
  agenda: AgendaWithDecisions;
  onConfirm: (agendaId: string) => Promise<boolean>;
  onIgnore: (agendaId: string) => Promise<boolean>;
  isLoading: boolean;
}

/**
 * Confirmation Badge - 확인 필요 배지
 */
const ConfirmationBadge = memo<{
  matchScore: number | undefined | null;
  onClick: () => void;
  isLoading: boolean;
}>(({ matchScore, onClick, isLoading }) => (
  <button
    onClick={onClick}
    disabled={isLoading}
    className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-yellow-50 border border-yellow-300 hover:bg-yellow-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
  >
    <AlertCircle className="w-4 h-4 text-yellow-600" />
    <span className="font-medium text-yellow-700">확인 필요</span>
    {matchScore !== undefined && matchScore !== null && (
      <span className="text-xs text-yellow-600 opacity-75">
        (유사도 {(matchScore * 100).toFixed(1)}%)
      </span>
    )}
  </button>
));

ConfirmationBadge.displayName = 'ConfirmationBadge';

/**
 * Confirmation Modal - 매칭 확인 모달
 */
const ConfirmationModal = memo<{
  agenda: AgendaWithDecisions;
  candidateAgendaId: string | undefined | null;
  matchScore: number | undefined | null;
  onConfirm: () => Promise<boolean>;
  onIgnore: () => Promise<boolean>;
  onClose: () => void;
  isLoading: boolean;
}>(
  ({
    agenda,
    candidateAgendaId,
    matchScore,
    onConfirm,
    onIgnore,
    onClose,
    isLoading,
  }) => {
    const [confirmLoading, setConfirmLoading] = useState(false);

    const handleConfirm = async () => {
      setConfirmLoading(true);
      try {
        const success = await onConfirm();
        if (success) {
          onClose();
        }
      } finally {
        setConfirmLoading(false);
      }
    };

    const handleIgnore = async () => {
      setConfirmLoading(true);
      try {
        const success = await onIgnore();
        if (success) {
          onClose();
        }
      } finally {
        setConfirmLoading(false);
      }
    };

    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
        <div className="bg-white rounded-lg shadow-lg max-w-2xl w-full mx-4 max-h-[80vh] overflow-auto">
          {/* Header */}
          <div className="sticky top-0 flex items-center justify-between p-6 border-b bg-white">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-yellow-600" />
              아젠다 매칭 확인
            </h2>
            <button
              onClick={onClose}
              disabled={isLoading}
              className="p-1 hover:bg-gray-100 rounded-full disabled:opacity-50"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="p-6 space-y-6">
            {/* Confidence Score */}
            {matchScore !== undefined && matchScore !== null && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-sm text-blue-700">
                  <span className="font-semibold">유사도 점수:</span>{' '}
                  {(matchScore * 100).toFixed(1)}%
                </p>
                <p className="text-xs text-blue-600 mt-1">
                  시스템이 감지한 유사도이지만, 최종 판단은 사용자가 결정합니다.
                </p>
              </div>
            )}

            {/* Current Agenda */}
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-gray-700">현재 아젠다</h3>
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <h4 className="font-semibold text-gray-900">{agenda.topic}</h4>
                {agenda.description && (
                  <p className="text-sm text-gray-600 mt-2">{agenda.description}</p>
                )}
              </div>
            </div>

            {/* Candidate Agenda */}
            {candidateAgendaId && (
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-gray-700">매칭된 기존 아젠다</h3>
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="flex items-start gap-2">
                    <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-green-700 font-medium mb-1">
                        Agenda ID: {candidateAgendaId}
                      </p>
                      <p className="text-sm text-gray-600 break-words">
                        기존 아젠다와 유사한 것으로 감지되었습니다.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Guidance */}
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <p className="text-sm text-amber-800">
                <span className="font-semibold">안내:</span> 이 아젠다가 기존 아젠다와 동일하거나
                매우 유사한가요? 맞으면 &quot;확인&quot;을 누르고, 다르면 &quot;새 아젠다로
                생성&quot;을 누르세요.
              </p>
            </div>
          </div>

          {/* Footer */}
          <div className="sticky bottom-0 flex items-center justify-end gap-3 p-6 border-t bg-white">
            <Button
              variant="secondary"
              onClick={onClose}
              disabled={isLoading || confirmLoading}
            >
              취소
            </Button>
            <Button
              variant="secondary"
              onClick={handleIgnore}
              disabled={isLoading || confirmLoading}
              isLoading={confirmLoading}
            >
              새 아젠다로 생성
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={isLoading || confirmLoading}
              isLoading={confirmLoading}
            >
              확인
            </Button>
          </div>
        </div>
      </div>
    );
  }
);

ConfirmationModal.displayName = 'ConfirmationModal';

/**
 * Main Component
 */
export const AgendaMatchConfirmation = memo<AgendaMatchConfirmationProps>(
  ({ agenda, onConfirm, onIgnore, isLoading }) => {
    const [showModal, setShowModal] = useState(false);

    if (agenda.matchStatus !== 'needs_confirmation') {
      return null;
    }

    const handleConfirm = async () => {
      return await onConfirm(agenda.id);
    };

    const handleIgnore = async () => {
      return await onIgnore(agenda.id);
    };

    return (
      <>
        <ConfirmationBadge
          matchScore={agenda.matchScore}
          onClick={() => setShowModal(true)}
          isLoading={isLoading}
        />

        {showModal && (
          <ConfirmationModal
            agenda={agenda}
            candidateAgendaId={agenda.candidateAgendaId}
            matchScore={agenda.matchScore}
            onConfirm={handleConfirm}
            onIgnore={handleIgnore}
            onClose={() => setShowModal(false)}
            isLoading={isLoading}
          />
        )}
      </>
    );
  }
);

AgendaMatchConfirmation.displayName = 'AgendaMatchConfirmation';
