// 스트리밍 상태 표시 컴포넌트 (회색 텍스트, 반짝임 효과)
interface StatusIndicatorProps {
  message: string;
}

export function StatusIndicator({ message }: StatusIndicatorProps) {
  return (
    <div className="flex items-center gap-2 py-2 animate-pulse">
      {/* 로딩 점 */}
      <div className="flex gap-1">
        <span
          className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
          style={{ animationDelay: '0ms' }}
        />
        <span
          className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
          style={{ animationDelay: '150ms' }}
        />
        <span
          className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
          style={{ animationDelay: '300ms' }}
        />
      </div>

      {/* 상태 텍스트 */}
      <span className="text-sm text-gray-400 italic">{message}</span>
    </div>
  );
}
