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
