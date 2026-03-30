/**
 * 볼륨 슬라이더 컴포넌트
 * 원격 참여자의 오디오 볼륨 조절용
 */

interface VolumeSliderProps {
  value: number; // 0.0 ~ 2.0
  onChange: (value: number) => void;
  disabled?: boolean;
}

export function VolumeSlider({ value, onChange, disabled = false }: VolumeSliderProps) {
  // 0 ~ 200% 범위로 변환하여 표시
  const percentage = Math.round(value * 100);

  return (
    <div className="flex items-center gap-1.5">
      {/* 볼륨 아이콘 */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className={`h-3.5 w-3.5 ${value === 0 ? 'text-gray-500' : 'text-gray-400'}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        {value === 0 ? (
          // 음소거 아이콘
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15zM17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2"
          />
        ) : value < 0.5 ? (
          // 작은 볼륨 아이콘
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15.536 8.464a5 5 0 010 7.072M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
          />
        ) : (
          // 큰 볼륨 아이콘
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
          />
        )}
      </svg>

      {/* 슬라이더 */}
      <input
        type="range"
        min="0"
        max="200"
        value={percentage}
        onChange={(e) => onChange(Number(e.target.value) / 100)}
        disabled={disabled}
        className="w-16 h-1 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
        title={`볼륨: ${percentage}%`}
      />

      {/* 퍼센트 표시 */}
      <span className="text-xs text-gray-500 w-8 text-right tabular-nums">
        {percentage}%
      </span>
    </div>
  );
}
