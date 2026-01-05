/**
 * 참여자 목록 컴포넌트
 */

import type { RoomParticipant } from '@/types/webrtc';

interface ParticipantListProps {
  participants: Map<string, RoomParticipant>;
  currentUserId: string;
}

export function ParticipantList({ participants, currentUserId }: ParticipantListProps) {
  const participantArray = Array.from(participants.values());

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-lg font-semibold text-white mb-3">
        참여자 ({participantArray.length}명)
      </h3>
      <ul className="space-y-2">
        {participantArray.map((participant) => (
          <li
            key={participant.userId}
            className="flex items-center justify-between p-2 rounded bg-gray-700"
          >
            <div className="flex items-center gap-2">
              {/* 아바타 */}
              <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-medium">
                {participant.userName.charAt(0).toUpperCase()}
              </div>
              {/* 이름 */}
              <span className="text-white">
                {participant.userName}
                {participant.userId === currentUserId && (
                  <span className="text-gray-400 text-sm ml-1">(나)</span>
                )}
              </span>
              {/* 역할 배지 */}
              {participant.role === 'host' && (
                <span className="px-2 py-0.5 text-xs bg-yellow-500 text-black rounded">
                  Host
                </span>
              )}
            </div>
            {/* 음소거 상태 */}
            <div className="flex items-center">
              {participant.audioMuted ? (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-5 w-5 text-red-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-label="음소거됨"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2"
                  />
                </svg>
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-5 w-5 text-green-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-label="마이크 켜짐"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
                  />
                </svg>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
