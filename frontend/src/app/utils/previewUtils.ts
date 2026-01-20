// 프리뷰 관련 유틸리티
import type { PreviewType } from '@/app/stores/previewStore';

// 유효한 프리뷰 타입 목록
export const VALID_PREVIEW_TYPES: PreviewType[] = [
  'meeting',
  'document',
  'command-result',
  'search-result',
  'timeline',
  'action-items',
  'branch-diff',
];

// 타입 가드: 유효한 프리뷰 타입인지 확인
export function isValidPreviewType(type: string): type is PreviewType {
  return VALID_PREVIEW_TYPES.includes(type as PreviewType);
}

// 프리뷰 데이터 생성 및 스토어 업데이트
export interface PreviewDataInput {
  type: string;
  title: string;
  content: string;
}

export interface PreviewDataOutput {
  title: string;
  content: string;
  createdAt: string;
}

export function createPreviewData(input: PreviewDataInput): {
  previewType: PreviewType;
  data: PreviewDataOutput;
} {
  const previewType = isValidPreviewType(input.type) ? input.type : 'command-result';

  return {
    previewType,
    data: {
      title: input.title,
      content: input.content,
      createdAt: new Date().toISOString(),
    },
  };
}

// 프리뷰 스토어 업데이트 헬퍼
export function updatePreviewStore(
  setPreview: (type: PreviewType, data: PreviewDataOutput) => void,
  input: PreviewDataInput
): void {
  const { previewType, data } = createPreviewData(input);
  setPreview(previewType, data);
}
