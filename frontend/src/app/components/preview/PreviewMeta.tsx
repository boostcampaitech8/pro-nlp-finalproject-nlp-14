// 프리뷰 메타 정보 컴포넌트
import { Clock } from 'lucide-react';
import type { PreviewData } from '@/app/stores/previewStore';

interface PreviewMetaProps {
  data: PreviewData | null;
}

export function PreviewMeta({ data }: PreviewMetaProps) {
  if (!data) return null;

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return null;
    try {
      return new Date(dateStr).toLocaleString('ko-KR', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  const updatedAt = formatDate(data.updatedAt);
  const createdAt = formatDate(data.createdAt);

  if (!updatedAt && !createdAt) return null;

  return (
    <div className="px-5 py-3 border-t border-glass">
      <div className="flex items-center gap-2 text-[11px] text-white/40">
        <Clock className="w-3.5 h-3.5" />
        <span>
          {updatedAt ? `Updated ${updatedAt}` : `Created ${createdAt}`}
        </span>
      </div>
    </div>
  );
}
