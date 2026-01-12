/**
 * 참여자 목록 컴포넌트
 */

import type { RoomParticipant } from '@/types/webrtc';
import type { AudioLevel } from '@/hooks/useAudioLevel';
import { VolumeSlider } from './VolumeSlider';

interface ParticipantListProps {
  participants: Map<string, RoomParticipant>;
  currentUserId: string;
  audioLevels?: Map<string, AudioLevel>;
  localMuteState: boolean; // 현재 사용자의 로컬 음소거 상태
  remoteVolumes: Map<string, number>; // 원격 참여자별 볼륨
  onVolumeChange: (userId: string, volume: number) => void;
  isHost?: boolean; // 현재 사용자가 Host인지 여부
  onForceMute?: (userId: string, muted: boolean) => void; // Host의 강제 음소거 콜백
}

/**
 * 3단계 오디오 레벨 인디케이터
 */
function AudioLevelIndicator({ level }: { level: AudioLevel }) {
  return (
    <div className="flex items-center gap-0.5" aria-label={`발화 레벨: ${level}`}>
      {/* 바 1 (낮음) */}
      <div
        className={`w-1 h-2 rounded-sm transition-colors duration-100 ${
          level >= 1 ? 'bg-green-400' : 'bg-gray-600'
        }`}
      />
      {/* 바 2 (중간) */}
      <div
        className={`w-1 h-3 rounded-sm transition-colors duration-100 ${
          level >= 2 ? 'bg-green-400' : 'bg-gray-600'
        }`}
      />
      {/* 바 3 (높음) */}
      <div
        className={`w-1 h-4 rounded-sm transition-colors duration-100 ${
          level >= 3 ? 'bg-green-400' : 'bg-gray-600'
        }`}
      />
    </div>
  );
}

export function ParticipantList({
  participants,
  currentUserId,
  audioLevels,
  localMuteState,
  remoteVolumes,
  onVolumeChange,
  isHost = false,
  onForceMute,
}: ParticipantListProps) {
  const participantArray = Array.from(participants.values());

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className="text-lg font-semibold text-white mb-3">
        참여자 ({participantArray.length}명)
      </h3>
      <ul className="space-y-2">
        {participantArray.map((participant) => {
          const audioLevel = audioLevels?.get(participant.userId) ?? 0;
          // 현재 사용자의 경우 로컬 음소거 상태 사용 (실시간 반영)
          const isCurrentUser = participant.userId === currentUserId;
          const isMuted = isCurrentUser ? localMuteState : participant.audioMuted;
          const isSpeaking = audioLevel > 0 && !isMuted;

          return (
            <li
              key={participant.userId}
              className={`p-2 rounded transition-colors ${
                isSpeaking ? 'bg-gray-600 ring-1 ring-green-400' : 'bg-gray-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {/* 아바타 - 발화 시 테두리 효과 */}
                  <div
                    className={`w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-medium transition-all flex-shrink-0 ${
                      isSpeaking ? 'ring-2 ring-green-400 ring-offset-1 ring-offset-gray-700' : ''
                    }`}
                  >
                    {participant.userName.charAt(0).toUpperCase()}
                  </div>
                  {/* 이름 */}
                  <span className="text-white text-sm truncate max-w-24">
                    {participant.userName}
                    {isCurrentUser && (
                      <span className="text-gray-400 text-xs ml-1">(나)</span>
                    )}
                  </span>
                  {/* 역할 배지 */}
                  {participant.role === 'host' && (
                    <span className="px-1.5 py-0.5 text-xs bg-yellow-500 text-black rounded flex-shrink-0">
                      Host
                    </span>
                  )}
                </div>

                {/* 오디오 상태 */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  {/* 발화 인디케이터 (음소거 아닐 때만) */}
                  {!isMuted && (
                    <AudioLevelIndicator level={audioLevel} />
                  )}

                  {/* 음소거 상태 */}
                  {isMuted ? (
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-4 w-4 text-red-400"
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
                      className={`h-4 w-4 transition-colors ${
                        isSpeaking ? 'text-green-400' : 'text-gray-400'
                      }`}
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
              </div>

              {/* 원격 참여자용 볼륨 슬라이더 (현재 사용자 제외) */}
              {!isCurrentUser && (
                <div className="mt-2 pl-10 flex items-center gap-2">
                  <VolumeSlider
                    value={remoteVolumes.get(participant.userId) ?? 1.0}
                    onChange={(volume) => onVolumeChange(participant.userId, volume)}
                  />
                  {/* Host만 다른 참여자 강제 음소거 가능 */}
                  {isHost && onForceMute && (
                    <button
                      type="button"
                      onClick={() => onForceMute(participant.userId, !isMuted)}
                      className={`px-2 py-1 text-xs rounded transition-colors ${
                        isMuted
                          ? 'bg-green-600 hover:bg-green-700 text-white'
                          : 'bg-red-600 hover:bg-red-700 text-white'
                      }`}
                      aria-label={isMuted ? 'Unmute' : 'Mute'}
                    >
                      {isMuted ? 'Unmute' : 'Mute'}
                    </button>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
