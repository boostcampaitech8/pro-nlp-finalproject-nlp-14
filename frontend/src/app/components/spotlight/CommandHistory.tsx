// 명령 히스토리 컴포넌트
import { useCommandStore } from '@/app/stores/commandStore';
import { usePreviewStore } from '@/app/stores/previewStore';
import type { HistoryItem } from '@/app/types/command';
import { cn } from '@/lib/utils';

interface CommandCardProps {
  item: HistoryItem;
  onClick: () => void;
}

function CommandCard({ item, onClick }: CommandCardProps) {
  const statusColors = {
    success: 'bg-mit-success/20 text-mit-success',
    error: 'bg-mit-warning/20 text-mit-warning',
    pending: 'bg-mit-primary/20 text-mit-primary',
  };

  const formatTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);

    if (minutes < 1) return '방금 전';
    if (minutes < 60) return `${minutes}분 전`;

    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}시간 전`;

    return date.toLocaleDateString('ko-KR', {
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <button
      onClick={onClick}
      className="glass-card-hover p-4 w-full text-left group"
    >
      <div className="flex items-center gap-3">
        <div className="icon-container-sm flex-shrink-0">
          <span className="text-lg">{item.icon}</span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-card-title truncate group-hover:text-mit-primary transition-colors">
              {item.command}
            </h3>
            <span
              className={cn(
                'px-2 py-0.5 rounded-full text-[10px] font-medium uppercase',
                statusColors[item.status]
              )}
            >
              {item.status === 'success' ? '완료' : item.status === 'error' ? '실패' : '진행'}
            </span>
          </div>
          <p className="text-card-desc truncate">{item.result}</p>
        </div>

        <span className="text-meta flex-shrink-0">
          {formatTime(item.timestamp)}
        </span>
      </div>
    </button>
  );
}

export function CommandHistory() {
  const { history } = useCommandStore();
  const { setPreview } = usePreviewStore();

  const handleClick = (item: HistoryItem) => {
    setPreview('command-result', {
      title: item.command,
      content: item.result,
      createdAt: item.timestamp.toISOString(),
    });
  };

  if (history.length === 0) {
    return (
      <div className="w-full max-w-4xl mx-auto text-center py-8">
        <p className="text-white/40 text-sm">
          아직 실행한 명령이 없습니다
        </p>
        <p className="text-white/30 text-xs mt-1">
          위의 추천 명령을 클릭하거나 직접 입력해보세요
        </p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mx-auto">
      <h2 className="text-section-header text-center mb-4">
        최근 활동
      </h2>

      <div className="space-y-2">
        {history.map((item) => (
          <CommandCard
            key={item.id}
            item={item}
            onClick={() => handleClick(item)}
          />
        ))}
      </div>
    </div>
  );
}
