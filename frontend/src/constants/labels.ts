/**
 * UI 라벨 상수
 * 회의 상태, 역할 등의 표시 라벨 중앙화
 */

import type { MeetingStatus, ParticipantRole, RecordingStatus, TeamRole } from '@/types';

// 회의 상태 라벨
export const MEETING_STATUS_LABELS: Record<MeetingStatus, string> = {
  scheduled: 'Scheduled',
  ongoing: 'Ongoing',
  completed: 'Completed',
  in_review: 'In Review',
  confirmed: 'Confirmed',
  cancelled: 'Cancelled',
};

export const MEETING_STATUS_COLORS: Record<MeetingStatus, string> = {
  scheduled: 'bg-blue-100 text-blue-800',
  ongoing: 'bg-green-100 text-green-800',
  completed: 'bg-gray-100 text-gray-800',
  in_review: 'bg-yellow-100 text-yellow-800',
  confirmed: 'bg-purple-100 text-purple-800',
  cancelled: 'bg-red-100 text-red-800',
};

// 회의 참여자 역할 라벨
export const PARTICIPANT_ROLE_LABELS: Record<ParticipantRole, string> = {
  host: 'Host',
  participant: 'Participant',
};

export const PARTICIPANT_ROLE_COLORS: Record<ParticipantRole, string> = {
  host: 'bg-blue-100 text-blue-800',
  participant: 'bg-gray-100 text-gray-700',
};

// 팀 역할 라벨
export const TEAM_ROLE_LABELS: Record<TeamRole, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
};

export const TEAM_ROLE_COLORS: Record<TeamRole, string> = {
  owner: 'bg-purple-100 text-purple-800',
  admin: 'bg-blue-100 text-blue-800',
  member: 'bg-gray-100 text-gray-700',
};

// 녹음 상태 라벨
export const RECORDING_STATUS_LABELS: Record<RecordingStatus, string> = {
  recording: 'Recording',
  completed: 'Completed',
  failed: 'Failed',
};

export const RECORDING_STATUS_COLORS: Record<RecordingStatus, string> = {
  recording: 'bg-red-100 text-red-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-gray-100 text-gray-600',
};
