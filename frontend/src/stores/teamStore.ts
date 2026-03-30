import type {
  AcceptInviteResponse,
  AddMeetingParticipantRequest,
  CreateMeetingRequest,
  CreateTeamRequest,
  ErrorResponse,
  InviteLinkResponse,
  InviteTeamMemberRequest,
  Meeting,
  MeetingParticipant,
  MeetingStatus,
  MeetingWithParticipants,
  Team,
  TeamMember,
  TeamWithMembers,
  UpdateMeetingParticipantRequest,
  UpdateMeetingRequest,
  UpdateTeamMemberRequest,
  UpdateTeamRequest,
} from '@/types';
import axios from 'axios';
import { create } from 'zustand';

import { meetingService } from '@/services/meetingService';
import { teamService } from '@/services/teamService';

// API 에러에서 사용자 친화적 메시지 추출
function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error) && error.response?.data) {
    const data = error.response.data;
    if (data.detail?.message) {
      return data.detail.message;
    }
    if ((data as ErrorResponse).message) {
      return (data as ErrorResponse).message;
    }
  }
  return fallback;
}

interface TeamState {
  // 팀 상태
  teams: Team[];
  currentTeam: TeamWithMembers | null;
  teamsLoading: boolean;
  teamError: string | null;

  // 회의 상태
  meetings: Meeting[];
  currentMeeting: MeetingWithParticipants | null;
  meetingsLoading: boolean;
  meetingError: string | null;

  // 팀 액션
  fetchTeams: () => Promise<void>;
  fetchTeam: (teamId: string) => Promise<void>;
  createTeam: (data: CreateTeamRequest) => Promise<Team>;
  updateTeam: (teamId: string, data: UpdateTeamRequest) => Promise<void>;
  deleteTeam: (teamId: string) => Promise<void>;

  // 팀 멤버 액션
  inviteMember: (teamId: string, data: InviteTeamMemberRequest) => Promise<TeamMember>;
  updateMemberRole: (teamId: string, userId: string, data: UpdateTeamMemberRequest) => Promise<void>;
  removeMember: (teamId: string, userId: string) => Promise<void>;

  // 초대 링크 상태
  inviteLink: InviteLinkResponse | null;
  inviteLinkLoading: boolean;

  // 초대 링크 액션
  generateInviteLink: (teamId: string) => Promise<InviteLinkResponse>;
  fetchInviteLink: (teamId: string) => Promise<void>;
  deactivateInviteLink: (teamId: string) => Promise<void>;
  acceptInvite: (code: string) => Promise<AcceptInviteResponse>;

  // 회의 액션
  fetchMeetings: (teamId: string, status?: MeetingStatus) => Promise<void>;
  fetchMeeting: (meetingId: string) => Promise<void>;
  createMeeting: (teamId: string, data: CreateMeetingRequest) => Promise<Meeting>;
  updateMeeting: (meetingId: string, data: UpdateMeetingRequest) => Promise<void>;
  deleteMeeting: (meetingId: string) => Promise<void>;

  // 회의 참여자 액션
  addParticipant: (meetingId: string, data: AddMeetingParticipantRequest) => Promise<MeetingParticipant>;
  updateParticipantRole: (meetingId: string, userId: string, data: UpdateMeetingParticipantRequest) => Promise<void>;
  removeParticipant: (meetingId: string, userId: string) => Promise<void>;

  // 에러 클리어
  clearErrors: () => void;
}

export const useTeamStore = create<TeamState>((set) => ({
  // 초기 상태
  teams: [],
  currentTeam: null,
  teamsLoading: false,
  teamError: null,

  meetings: [],
  currentMeeting: null,
  meetingsLoading: false,
  meetingError: null,

  inviteLink: null,
  inviteLinkLoading: false,

  // 팀 액션
  fetchTeams: async () => {
    set({ teamsLoading: true, teamError: null });
    try {
      const response = await teamService.listMyTeams();
      set({ teams: response.items, teamsLoading: false });
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to fetch teams');
      set({ teamError: message, teamsLoading: false });
    }
  },

  fetchTeam: async (teamId: string) => {
    set({ teamsLoading: true, teamError: null });
    try {
      const team = await teamService.getTeam(teamId);
      set({ currentTeam: team, teamsLoading: false });
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to fetch team');
      set({ teamError: message, teamsLoading: false });
    }
  },

  createTeam: async (data: CreateTeamRequest) => {
    set({ teamsLoading: true, teamError: null });
    try {
      const team = await teamService.createTeam(data);
      set((state) => ({
        teams: [team, ...state.teams],
        teamsLoading: false,
      }));
      return team;
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to create team');
      set({ teamError: message, teamsLoading: false });
      throw error;
    }
  },

  updateTeam: async (teamId: string, data: UpdateTeamRequest) => {
    set({ teamsLoading: true, teamError: null });
    try {
      const team = await teamService.updateTeam(teamId, data);
      set((state) => ({
        teams: state.teams.map((t) => (t.id === teamId ? team : t)),
        currentTeam: state.currentTeam?.id === teamId
          ? { ...state.currentTeam, ...team }
          : state.currentTeam,
        teamsLoading: false,
      }));
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to update team');
      set({ teamError: message, teamsLoading: false });
      throw error;
    }
  },

  deleteTeam: async (teamId: string) => {
    set({ teamsLoading: true, teamError: null });
    try {
      await teamService.deleteTeam(teamId);
      set((state) => ({
        teams: state.teams.filter((t) => t.id !== teamId),
        currentTeam: state.currentTeam?.id === teamId ? null : state.currentTeam,
        teamsLoading: false,
      }));
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to delete team');
      set({ teamError: message, teamsLoading: false });
      throw error;
    }
  },

  // 팀 멤버 액션
  inviteMember: async (teamId: string, data: InviteTeamMemberRequest) => {
    set({ teamsLoading: true, teamError: null });
    try {
      const member = await teamService.inviteMember(teamId, data);
      set((state) => ({
        currentTeam: state.currentTeam?.id === teamId
          ? { ...state.currentTeam, members: [...state.currentTeam.members, member] }
          : state.currentTeam,
        teamsLoading: false,
      }));
      return member;
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to invite member');
      set({ teamError: message, teamsLoading: false });
      throw error;
    }
  },

  updateMemberRole: async (teamId: string, userId: string, data: UpdateTeamMemberRequest) => {
    set({ teamsLoading: true, teamError: null });
    try {
      const updatedMember = await teamService.updateMemberRole(teamId, userId, data);
      set((state) => ({
        currentTeam: state.currentTeam?.id === teamId
          ? {
              ...state.currentTeam,
              members: state.currentTeam.members.map((m) =>
                m.userId === userId ? updatedMember : m
              ),
            }
          : state.currentTeam,
        teamsLoading: false,
      }));
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to update member role');
      set({ teamError: message, teamsLoading: false });
      throw error;
    }
  },

  removeMember: async (teamId: string, userId: string) => {
    set({ teamsLoading: true, teamError: null });
    try {
      await teamService.removeMember(teamId, userId);
      set((state) => ({
        currentTeam: state.currentTeam?.id === teamId
          ? {
              ...state.currentTeam,
              members: state.currentTeam.members.filter((m) => m.userId !== userId),
            }
          : state.currentTeam,
        teamsLoading: false,
      }));
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to remove member');
      set({ teamError: message, teamsLoading: false });
      throw error;
    }
  },

  // 회의 액션
  fetchMeetings: async (teamId: string, status?: MeetingStatus) => {
    set({ meetingsLoading: true, meetingError: null });
    try {
      const response = await meetingService.listTeamMeetings(teamId, 1, 100, status);
      set({ meetings: response.items, meetingsLoading: false });
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to fetch meetings');
      set({ meetingError: message, meetingsLoading: false });
    }
  },

  fetchMeeting: async (meetingId: string) => {
    set({ meetingsLoading: true, meetingError: null });
    try {
      const meeting = await meetingService.getMeeting(meetingId);
      set({ currentMeeting: meeting, meetingsLoading: false });
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to fetch meeting');
      set({ meetingError: message, meetingsLoading: false });
    }
  },

  createMeeting: async (teamId: string, data: CreateMeetingRequest) => {
    set({ meetingsLoading: true, meetingError: null });
    try {
      const meeting = await meetingService.createMeeting(teamId, data);
      set((state) => ({
        meetings: [meeting, ...state.meetings],
        meetingsLoading: false,
      }));
      return meeting;
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to create meeting');
      set({ meetingError: message, meetingsLoading: false });
      throw error;
    }
  },

  updateMeeting: async (meetingId: string, data: UpdateMeetingRequest) => {
    set({ meetingsLoading: true, meetingError: null });
    try {
      const meeting = await meetingService.updateMeeting(meetingId, data);
      set((state) => ({
        meetings: state.meetings.map((m) => (m.id === meetingId ? meeting : m)),
        currentMeeting: state.currentMeeting?.id === meetingId
          ? { ...state.currentMeeting, ...meeting }
          : state.currentMeeting,
        meetingsLoading: false,
      }));
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to update meeting');
      set({ meetingError: message, meetingsLoading: false });
      throw error;
    }
  },

  deleteMeeting: async (meetingId: string) => {
    set({ meetingsLoading: true, meetingError: null });
    try {
      await meetingService.deleteMeeting(meetingId);
      set((state) => ({
        meetings: state.meetings.filter((m) => m.id !== meetingId),
        currentMeeting: state.currentMeeting?.id === meetingId ? null : state.currentMeeting,
        meetingsLoading: false,
      }));
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to delete meeting');
      set({ meetingError: message, meetingsLoading: false });
      throw error;
    }
  },

  // 회의 참여자 액션
  addParticipant: async (meetingId: string, data: AddMeetingParticipantRequest) => {
    set({ meetingsLoading: true, meetingError: null });
    try {
      const participant = await meetingService.addParticipant(meetingId, data);
      set((state) => ({
        currentMeeting: state.currentMeeting?.id === meetingId
          ? {
              ...state.currentMeeting,
              participants: [...state.currentMeeting.participants, participant],
            }
          : state.currentMeeting,
        meetingsLoading: false,
      }));
      return participant;
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to add participant');
      set({ meetingError: message, meetingsLoading: false });
      throw error;
    }
  },

  updateParticipantRole: async (
    meetingId: string,
    userId: string,
    data: UpdateMeetingParticipantRequest
  ) => {
    set({ meetingsLoading: true, meetingError: null });
    try {
      const updatedParticipant = await meetingService.updateParticipantRole(
        meetingId,
        userId,
        data
      );
      set((state) => ({
        currentMeeting: state.currentMeeting?.id === meetingId
          ? {
              ...state.currentMeeting,
              participants: state.currentMeeting.participants.map((p) =>
                p.userId === userId ? updatedParticipant : p
              ),
            }
          : state.currentMeeting,
        meetingsLoading: false,
      }));
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to update participant role');
      set({ meetingError: message, meetingsLoading: false });
      throw error;
    }
  },

  removeParticipant: async (meetingId: string, userId: string) => {
    set({ meetingsLoading: true, meetingError: null });
    try {
      await meetingService.removeParticipant(meetingId, userId);
      set((state) => ({
        currentMeeting: state.currentMeeting?.id === meetingId
          ? {
              ...state.currentMeeting,
              participants: state.currentMeeting.participants.filter(
                (p) => p.userId !== userId
              ),
            }
          : state.currentMeeting,
        meetingsLoading: false,
      }));
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to remove participant');
      set({ meetingError: message, meetingsLoading: false });
      throw error;
    }
  },

  // 초대 링크 액션
  generateInviteLink: async (teamId: string) => {
    set({ inviteLinkLoading: true, teamError: null });
    try {
      const link = await teamService.generateInviteLink(teamId);
      set({ inviteLink: link, inviteLinkLoading: false });
      return link;
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to generate invite link');
      set({ teamError: message, inviteLinkLoading: false });
      throw error;
    }
  },

  fetchInviteLink: async (teamId: string) => {
    set({ inviteLinkLoading: true });
    try {
      const link = await teamService.getInviteLink(teamId);
      set({ inviteLink: link, inviteLinkLoading: false });
    } catch (error) {
      set({ inviteLink: null, inviteLinkLoading: false });
    }
  },

  deactivateInviteLink: async (teamId: string) => {
    set({ inviteLinkLoading: true, teamError: null });
    try {
      await teamService.deactivateInviteLink(teamId);
      set({ inviteLink: null, inviteLinkLoading: false });
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to deactivate invite link');
      set({ teamError: message, inviteLinkLoading: false });
      throw error;
    }
  },

  acceptInvite: async (code: string) => {
    set({ teamsLoading: true, teamError: null });
    try {
      const result = await teamService.acceptInvite(code);
      set({ teamsLoading: false });
      return result;
    } catch (error) {
      const message = getErrorMessage(error, 'Failed to accept invite');
      set({ teamError: message, teamsLoading: false });
      throw error;
    }
  },

  clearErrors: () => set({ teamError: null, meetingError: null }),
}));
