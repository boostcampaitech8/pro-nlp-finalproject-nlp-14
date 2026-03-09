import type {
  AddMeetingParticipantRequest,
  CreateMeetingRequest,
  Meeting,
  MeetingListResponse,
  MeetingParticipant,
  MeetingStatus,
  MeetingWithParticipants,
  UpdateMeetingParticipantRequest,
  UpdateMeetingRequest,
} from '@/types';
import api from './api';

export const meetingService = {
  // Meeting CRUD
  async createMeeting(teamId: string, data: CreateMeetingRequest): Promise<Meeting> {
    const response = await api.post<Meeting>(`/teams/${teamId}/meetings`, data);
    return response.data;
  },

  async listTeamMeetings(
    teamId: string,
    page = 1,
    limit = 20,
    status?: MeetingStatus
  ): Promise<MeetingListResponse> {
    const response = await api.get<MeetingListResponse>(`/teams/${teamId}/meetings`, {
      params: { page, limit, status },
    });
    return response.data;
  },

  async getMeeting(meetingId: string): Promise<MeetingWithParticipants> {
    const response = await api.get<MeetingWithParticipants>(`/meetings/${meetingId}`);
    return response.data;
  },

  async updateMeeting(meetingId: string, data: UpdateMeetingRequest): Promise<Meeting> {
    const response = await api.put<Meeting>(`/meetings/${meetingId}`, data);
    return response.data;
  },

  async deleteMeeting(meetingId: string): Promise<void> {
    await api.delete(`/meetings/${meetingId}`);
  },

  // Meeting Participants
  async addParticipant(
    meetingId: string,
    data: AddMeetingParticipantRequest
  ): Promise<MeetingParticipant> {
    const response = await api.post<MeetingParticipant>(
      `/meetings/${meetingId}/participants`,
      data
    );
    return response.data;
  },

  async listParticipants(meetingId: string): Promise<MeetingParticipant[]> {
    const response = await api.get<MeetingParticipant[]>(`/meetings/${meetingId}/participants`);
    return response.data;
  },

  async updateParticipantRole(
    meetingId: string,
    userId: string,
    data: UpdateMeetingParticipantRequest
  ): Promise<MeetingParticipant> {
    const response = await api.put<MeetingParticipant>(
      `/meetings/${meetingId}/participants/${userId}`,
      data
    );
    return response.data;
  },

  async removeParticipant(meetingId: string, userId: string): Promise<void> {
    await api.delete(`/meetings/${meetingId}/participants/${userId}`);
  },
};
