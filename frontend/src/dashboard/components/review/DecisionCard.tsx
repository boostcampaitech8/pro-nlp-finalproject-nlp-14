/**
 * 개별 Decision 카드 컴포넌트
 *
 * 결정사항 내용, 상태, 승인/거절 버튼 표시
 */

import type { Decision, PRParticipant } from '@/types';
import { Button } from '@/components/ui/Button';
import { usePRReviewStore } from '@/stores/prReviewStore';

interface DecisionCardProps {
  decision: Decision;
  currentUserId?: string;
  participants: PRParticipant[];
}

const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  latest: 'bg-blue-100 text-blue-800',
  outdated: 'bg-gray-100 text-gray-800',
};

const STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  approved: 'Approved',
  rejected: 'Rejected',
  latest: 'Latest',
  outdated: 'Outdated',
};

export function DecisionCard({
  decision,
  currentUserId,
  participants,
}: DecisionCardProps) {
  const { approveDecision, rejectDecision, actionLoading } = usePRReviewStore();

  const isLoading = actionLoading[decision.id] || false;
  const hasApproved = currentUserId
    ? decision.approvers.includes(currentUserId)
    : false;
  const hasRejected = currentUserId
    ? decision.rejectors.includes(currentUserId)
    : false;
  const canAct =
    decision.status === 'draft' ||
    (!hasApproved && !hasRejected);

  const handleApprove = async () => {
    await approveDecision(decision.id);
  };

  const handleReject = async () => {
    await rejectDecision(decision.id);
  };

  // 참여자별 승인 상태 표시
  const getParticipantStatus = (participantId: string) => {
    if (decision.approvers.includes(participantId)) return 'approved';
    if (decision.rejectors.includes(participantId)) return 'rejected';
    return 'pending';
  };

  return (
    <div className="border border-gray-200 rounded-lg p-4">
      {/* 상태 배지 */}
      <div className="flex items-center justify-between mb-3">
        <span
          className={`px-2 py-1 text-xs font-medium rounded-full ${
            STATUS_STYLES[decision.status] || STATUS_STYLES.draft
          }`}
        >
          {STATUS_LABELS[decision.status] || decision.status}
        </span>

        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span>{decision.approvers.length} approved</span>
          <span>/</span>
          <span>{participants.length} total</span>
        </div>
      </div>

      {/* 결정 내용 */}
      <p className="text-gray-900 font-medium mb-2">{decision.content}</p>
      {decision.context && (
        <p className="text-gray-600 text-sm mb-3">{decision.context}</p>
      )}

      {/* 참여자별 상태 */}
      <div className="flex flex-wrap gap-2 mb-4">
        {participants.map((p) => {
          const status = getParticipantStatus(p.id);
          return (
            <div
              key={p.id}
              className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs ${
                status === 'approved'
                  ? 'bg-green-50 text-green-700'
                  : status === 'rejected'
                    ? 'bg-red-50 text-red-700'
                    : 'bg-gray-50 text-gray-500'
              }`}
            >
              {status === 'approved' && (
                <svg
                  className="w-3 h-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              )}
              {status === 'rejected' && (
                <svg
                  className="w-3 h-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              )}
              {status === 'pending' && (
                <svg
                  className="w-3 h-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              )}
              <span>{p.name}</span>
            </div>
          );
        })}
      </div>

      {/* 액션 버튼 */}
      {canAct && currentUserId && (
        <div className="flex gap-2">
          <Button
            variant={hasApproved ? 'primary' : 'outline'}
            onClick={handleApprove}
            disabled={isLoading || hasApproved}
            className="flex items-center gap-1"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
            {hasApproved ? 'Approved' : 'Approve'}
          </Button>
          <Button
            variant={hasRejected ? 'secondary' : 'outline'}
            onClick={handleReject}
            disabled={isLoading || hasRejected}
            className="flex items-center gap-1"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
            {hasRejected ? 'Rejected' : 'Reject'}
          </Button>
        </div>
      )}
    </div>
  );
}
