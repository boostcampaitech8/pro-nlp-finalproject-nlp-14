// 우측 사이드바 (400px) - 동적 프리뷰 패널
import { usePreviewStore } from '@/app/stores/previewStore';
import { PreviewHeader } from './PreviewHeader';
import { PreviewContent } from './PreviewContent';
import { PreviewMeta } from './PreviewMeta';
import { ScrollArea } from '@/app/components/ui';

export function RightSidebar() {
  const { previewType, previewData, isLoading } = usePreviewStore();

  return (
    <aside className="w-[400px] glass-sidebar flex flex-col border-l border-glass">
      <PreviewHeader type={previewType} />

      <ScrollArea className="flex-1">
        <div className="p-5 min-h-full">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-mit-primary" />
            </div>
          ) : (
            <PreviewContent type={previewType} data={previewData} />
          )}
        </div>
      </ScrollArea>

      <PreviewMeta data={previewData} />
    </aside>
  );
}
