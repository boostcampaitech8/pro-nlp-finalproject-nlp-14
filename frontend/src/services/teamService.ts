import type {
  CreateTeamRequest,
  InviteTeamMemberRequest,
  Team,
  TeamListResponse,
  TeamMember,
  TeamWithMembers,
  UpdateTeamMemberRequest,
  UpdateTeamRequest,
} from '@/types';
import api from './api';

export const teamService = {
  // Team CRUD
  async createTeam(data: CreateTeamRequest): Promise<Team> {
    const response = await api.post<Team>('/teams', data);
    return response.data;
  },

  async listMyTeams(page = 1, limit = 20): Promise<TeamListResponse> {
    const response = await api.get<TeamListResponse>('/teams', {
      params: { page, limit },
    });
    return response.data;
  },

  async getTeam(teamId: string): Promise<TeamWithMembers> {
    const response = await api.get<TeamWithMembers>(`/teams/${teamId}`);
    return response.data;
  },

  async updateTeam(teamId: string, data: UpdateTeamRequest): Promise<Team> {
    const response = await api.put<Team>(`/teams/${teamId}`, data);
    return response.data;
  },

  async deleteTeam(teamId: string): Promise<void> {
    await api.delete(`/teams/${teamId}`);
  },

  // Team Members
  async inviteMember(teamId: string, data: InviteTeamMemberRequest): Promise<TeamMember> {
    const response = await api.post<TeamMember>(`/teams/${teamId}/members`, data);
    return response.data;
  },

  async listMembers(teamId: string): Promise<TeamMember[]> {
    const response = await api.get<TeamMember[]>(`/teams/${teamId}/members`);
    return response.data;
  },

  async updateMemberRole(
    teamId: string,
    userId: string,
    data: UpdateTeamMemberRequest
  ): Promise<TeamMember> {
    const response = await api.put<TeamMember>(`/teams/${teamId}/members/${userId}`, data);
    return response.data;
  },

  async removeMember(teamId: string, userId: string): Promise<void> {
    await api.delete(`/teams/${teamId}/members/${userId}`);
  },
};
