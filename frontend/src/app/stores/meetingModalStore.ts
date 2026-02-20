// 회의 생성 모달 상태 관리
import { create } from 'zustand';

export type MeetingModalStep = 'info' | 'invite' | 'success';

interface MeetingModalState {
  isOpen: boolean;
  step: MeetingModalStep;
  createdMeetingId: string | null;
  createdMeetingTitle: string | null;

  // Actions
  openModal: () => void;
  closeModal: () => void;
  setStep: (step: MeetingModalStep) => void;
  setCreatedMeeting: (id: string, title: string) => void;
  reset: () => void;
}

export const useMeetingModalStore = create<MeetingModalState>((set) => ({
  isOpen: false,
  step: 'info',
  createdMeetingId: null,
  createdMeetingTitle: null,

  openModal: () =>
    set({
      isOpen: true,
      step: 'info',
      createdMeetingId: null,
      createdMeetingTitle: null,
    }),

  closeModal: () =>
    set({
      isOpen: false,
      step: 'info',
      createdMeetingId: null,
      createdMeetingTitle: null,
    }),

  setStep: (step) => set({ step }),

  setCreatedMeeting: (id, title) =>
    set({ createdMeetingId: id, createdMeetingTitle: title }),

  reset: () =>
    set({
      step: 'info',
      createdMeetingId: null,
      createdMeetingTitle: null,
    }),
}));
