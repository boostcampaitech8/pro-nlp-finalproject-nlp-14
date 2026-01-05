/**
 * 오디오 컨트롤 컴포넌트
 * 마이크 음소거 토글 버튼
 */

interface AudioControlsProps {
  isAudioMuted: boolean;
  onToggleMute: () => void;
  disabled?: boolean;
}

export function AudioControls({ isAudioMuted, onToggleMute, disabled }: AudioControlsProps) {
  return (
    <div className="flex items-center gap-4">
      <button
        onClick={onToggleMute}
        disabled={disabled}
        className={`
          flex items-center justify-center w-14 h-14 rounded-full
          transition-colors duration-200
          ${
            isAudioMuted
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-gray-700 hover:bg-gray-600 text-white'
          }
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
        title={isAudioMuted ? '마이크 켜기' : '마이크 끄기'}
      >
        {isAudioMuted ? (
          // 마이크 음소거 아이콘
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
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
          // 마이크 아이콘
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
            />
          </svg>
        )}
      </button>
      <span className="text-sm text-gray-400">
        {isAudioMuted ? '음소거됨' : '마이크 켜짐'}
      </span>
    </div>
  );
}
