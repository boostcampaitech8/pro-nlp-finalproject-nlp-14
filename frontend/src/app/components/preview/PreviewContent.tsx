// 프리뷰 콘텐츠 컴포넌트
import { FileText, Calendar, Users } from 'lucide-react';
import type { PreviewType, PreviewData } from '@/app/stores/previewStore';
import TimelineView from './TimelineView';
import ActionItemsView from './ActionItemsView';
import BranchDiffView from './BranchDiffView';

interface PreviewContentProps {
  type: PreviewType;
  data: PreviewData | null;
}

function EmptyPreview() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <div className="icon-container-sm mb-4">
        <FileText className="w-6 h-6 text-white/40" />
      </div>
      <p className="text-[14px] text-white/60 mb-2">
        항목을 선택하면 여기에 표시됩니다
      </p>
      <p className="text-[12px] text-white/40">
        명령어를 입력하거나 목록에서 선택하세요
      </p>
    </div>
  );
}

function MeetingPreview({ data }: { data: PreviewData }) {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-xl font-semibold text-white mb-2">
          {data.title || '회의 제목'}
        </h3>
        {data.description && (
          <p className="text-[14px] text-white/60 leading-relaxed">
            {data.description}
          </p>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-3 text-[13px] text-white/60">
          <Calendar className="w-4 h-4" />
          <span>{data.createdAt || '날짜 정보 없음'}</span>
        </div>
        <div className="flex items-center gap-3 text-[13px] text-white/60">
          <Users className="w-4 h-4" />
          <span>참여자 정보</span>
        </div>
      </div>

      {data.content && (
        <div className="glass-card p-4">
          <p className="text-[13px] text-white/80 whitespace-pre-wrap">
            {data.content}
          </p>
        </div>
      )}
    </div>
  );
}

function DocumentPreview({ data }: { data: PreviewData }) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-white">
        {data.title || '문서 제목'}
      </h3>
      {data.content && (
        <div className="glass-card p-4">
          <p className="text-[13px] text-white/80 whitespace-pre-wrap leading-relaxed">
            {data.content}
          </p>
        </div>
      )}
    </div>
  );
}

function CommandResultPreview({ data }: { data: PreviewData }) {
  return (
    <div className="space-y-4">
      <div className="glass-card p-4">
        <p className="text-[11px] text-white/40 uppercase tracking-wide mb-2">
          Result
        </p>
        <p className="text-[14px] text-white/80 whitespace-pre-wrap">
          {data.content || '결과가 없습니다'}
        </p>
      </div>
    </div>
  );
}

export function PreviewContent({ type, data }: PreviewContentProps) {
  if (type === 'empty' || !data) {
    return <EmptyPreview />;
  }

  switch (type) {
    case 'meeting':
      return <MeetingPreview data={data} />;
    case 'document':
    case 'search-result':
      return <DocumentPreview data={data} />;
    case 'command-result':
      return <CommandResultPreview data={data} />;
    case 'timeline':
      try {
        const timelineItems = data.content ? JSON.parse(data.content) : [];
        return <TimelineView items={timelineItems} title={data.title || '변경 이력'} />;
      } catch (error) {
        console.error('Failed to parse timeline data:', error);
        return <CommandResultPreview data={{ content: '타임라인 데이터를 불러올 수 없습니다' }} />;
      }
    case 'action-items':
      try {
        const actionItems = data.content ? JSON.parse(data.content) : [];
        return <ActionItemsView items={actionItems} />;
      } catch (error) {
        console.error('Failed to parse action items data:', error);
        return <CommandResultPreview data={{ content: '액션 아이템 데이터를 불러올 수 없습니다' }} />;
      }
    case 'branch-diff':
      try {
        const diffData = data.content ? JSON.parse(data.content) : {};
        return <BranchDiffView {...diffData} />;
      } catch (error) {
        console.error('Failed to parse branch diff data:', error);
        return <CommandResultPreview data={{ content: '브랜치 비교 데이터를 불러올 수 없습니다' }} />;
      }
    default:
      return <EmptyPreview />;
  }
}
