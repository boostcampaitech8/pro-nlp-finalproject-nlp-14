/**
 * 회의록 헤더 컴포넌트
 *
 * 회의록 제목, 설명, 참여자 정보 표시
 */

import type { PRParticipant } from '@/types';

interface MinutesHeaderProps {
  title: string;
  description?: string | null;
  createdAt: string;
  participants: PRParticipant[];
}

export function MinutesHeader({
  title,
  description,
  createdAt,
  participants,
}: MinutesHeaderProps) {
  const formattedDate = new Date(createdAt).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="bg-white rounded-xl shadow-sm p-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-2">{title}</h2>

      {description && <p className="text-gray-600 mb-4">{description}</p>}

      <div className="flex items-center gap-6 text-sm text-gray-500 mb-4">
        <div className="flex items-center gap-1">
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
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>{formattedDate}</span>
        </div>
        <div className="flex items-center gap-1">
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
              d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
            />
          </svg>
          <span>{participants.length} participants</span>
        </div>
      </div>

      {/* 참여자 목록 */}
      <div className="flex flex-wrap gap-2">
        {participants.map((p) => (
          <span
            key={p.id}
            className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full"
          >
            {p.name}
          </span>
        ))}
      </div>
    </div>
  );
}
