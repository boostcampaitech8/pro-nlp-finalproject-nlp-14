// [미사용] 채팅 모드 통합으로 비활성화 (2025.01)
// 추후 실제 회의 생성 API 연동 시 재활용 가능
// 회의 모달 상태 관리
import { create } from 'zustand';

interface MeetingModalData {
  title?: string;
  description?: string;
  scheduledAt?: string;
  teamId?: string;
}

interface MeetingModalState {
  isOpen: boolean;
  initialData: MeetingModalData | null;

  // Actions
  openModal: (data?: MeetingModalData) => void;
  closeModal: () => void;
}

export const useMeetingModalStore = create<MeetingModalState>((set) => ({
  isOpen: false,
  initialData: null,

  openModal: (data) =>
    set({
      isOpen: true,
      initialData: data || null,
    }),

  closeModal: () =>
    set({
      isOpen: false,
      initialData: null,
    }),
}));
