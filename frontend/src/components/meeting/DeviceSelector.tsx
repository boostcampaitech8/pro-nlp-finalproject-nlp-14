/**
 * 오디오 장치 선택 드롭다운 컴포넌트
 */

import type { AudioDevice } from '@/hooks/useAudioDevices';

interface DeviceSelectorProps {
  label: string;
  devices: AudioDevice[];
  selectedDeviceId: string | null;
  onDeviceChange: (deviceId: string) => void;
  disabled?: boolean;
  disabledMessage?: string;
  icon: 'mic' | 'speaker';
}

export function DeviceSelector({
  label,
  devices,
  selectedDeviceId,
  onDeviceChange,
  disabled = false,
  disabledMessage,
  icon,
}: DeviceSelectorProps) {
  return (
    <div className="flex items-center gap-2">
      {/* 아이콘 */}
      {icon === 'mic' ? (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-4 w-4 text-gray-400"
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
      ) : (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-4 w-4 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
          />
        </svg>
      )}

      {/* 드롭다운 */}
      <div className="relative">
        <select
          value={selectedDeviceId || ''}
          onChange={(e) => onDeviceChange(e.target.value)}
          disabled={disabled}
          className={`
            appearance-none bg-gray-700 text-white text-sm rounded px-3 py-1.5 pr-8
            border border-gray-600 focus:border-blue-500 focus:outline-none
            ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-gray-600'}
          `}
          title={disabled && disabledMessage ? disabledMessage : label}
        >
          {devices.length === 0 ? (
            <option value="">장치 없음</option>
          ) : (
            devices.map((device) => (
              <option key={device.deviceId} value={device.deviceId}>
                {device.label}
              </option>
            ))
          )}
        </select>

        {/* 화살표 아이콘 */}
        <div className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
          <svg
            className="h-4 w-4 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </div>

      {/* 비활성화 메시지 */}
      {disabled && disabledMessage && (
        <span className="text-xs text-gray-500" title={disabledMessage}>
          (미지원)
        </span>
      )}
    </div>
  );
}
