// 우측 프리뷰 패널 상태 관리
import { create } from 'zustand';

export type PreviewType =
  | 'empty'
  | 'meeting'
  | 'document'
  | 'search-result'
  | 'command-result';

export interface PreviewData {
  id?: string;
  title?: string;
  description?: string;
  content?: string;
  metadata?: Record<string, unknown>;
  createdAt?: string;
  updatedAt?: string;
}

interface PreviewState {
  previewType: PreviewType;
  previewData: PreviewData | null;
  isLoading: boolean;

  // Actions
  setPreview: (type: PreviewType, data: PreviewData | null) => void;
  clearPreview: () => void;
  setLoading: (loading: boolean) => void;
}

export const usePreviewStore = create<PreviewState>((set) => ({
  previewType: 'empty',
  previewData: null,
  isLoading: false,

  setPreview: (type, data) =>
    set({
      previewType: type,
      previewData: data,
      isLoading: false,
    }),

  clearPreview: () =>
    set({
      previewType: 'empty',
      previewData: null,
      isLoading: false,
    }),

  setLoading: (loading) => set({ isLoading: loading }),
}));
