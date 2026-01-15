import type {
  CreateMeetingRequest,
  Meeting,
  MeetingListResponse,
  MeetingStatus,
  MeetingWithParticipants,
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
};
