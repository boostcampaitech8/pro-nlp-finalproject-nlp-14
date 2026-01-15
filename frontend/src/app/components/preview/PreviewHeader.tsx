// 프리뷰 헤더 컴포넌트
import { X } from 'lucide-react';
import type { PreviewType } from '@/app/stores/previewStore';
import { usePreviewStore } from '@/app/stores/previewStore';
import { PREVIEW_TITLES } from '@/app/constants';

interface PreviewHeaderProps {
  type: PreviewType;
}

export function PreviewHeader({ type }: PreviewHeaderProps) {
  const { clearPreview } = usePreviewStore();

  return (
    <div className="flex items-center justify-between px-5 py-4 border-b border-glass">
      <h2 className="text-[15px] font-semibold text-white">
        {PREVIEW_TITLES[type]}
      </h2>

      <div className="flex items-center gap-1">
        {type !== 'empty' && (
          <button className="action-btn" onClick={clearPreview}>
            <X className="w-4 h-4 text-white/60" />
          </button>
        )}
      </div>
    </div>
  );
}
