/**
 * PR 상태 배지 컴포넌트
 *
 * PR의 open/closed 상태와 진행률 표시
 */

import type { PRStatus } from '@/types';

interface PRStatusBadgeProps {
  status: PRStatus;
}

export function PRStatusBadge({ status }: PRStatusBadgeProps) {
  const isOpen = status.status === 'open';

  return (
    <div
      className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${
        isOpen ? 'bg-green-500/20 text-green-300' : 'bg-purple-500/20 text-purple-300'
      }`}
    >
      {isOpen ? (
        // GitPullRequest icon
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
            d="M7 7h10M7 11h10M7 15h10M7 19h10"
          />
        </svg>
      ) : (
        // CheckCircle icon
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
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      )}
      <span>
        {isOpen ? 'Open' : 'Closed'} - {status.approvedDecisions}/
        {status.totalDecisions} approved
      </span>
    </div>
  );
}
