// 팀 생성 모달 상태 관리
import { create } from 'zustand';

interface CreateTeamModalState {
  isOpen: boolean;

  // Actions
  openModal: () => void;
  closeModal: () => void;
}

export const useCreateTeamModalStore = create<CreateTeamModalState>((set) => ({
  isOpen: false,

  openModal: () =>
    set({
      isOpen: true,
    }),

  closeModal: () =>
    set({
      isOpen: false,
    }),
}));
