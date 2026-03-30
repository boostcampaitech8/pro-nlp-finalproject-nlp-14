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
  scheduled: 'bg-blue-500/20 text-blue-300',
  ongoing: 'bg-green-500/20 text-green-300',
  completed: 'bg-white/10 text-white/70',
  in_review: 'bg-yellow-500/20 text-yellow-300',
  confirmed: 'bg-purple-500/20 text-purple-300',
  cancelled: 'bg-red-500/20 text-red-300',
};

// 회의 참여자 역할 라벨
export const PARTICIPANT_ROLE_LABELS: Record<ParticipantRole, string> = {
  host: 'Host',
  participant: 'Participant',
};

export const PARTICIPANT_ROLE_COLORS: Record<ParticipantRole, string> = {
  host: 'bg-blue-500/20 text-blue-300',
  participant: 'bg-white/10 text-white/70',
};

// 팀 역할 라벨
export const TEAM_ROLE_LABELS: Record<TeamRole, string> = {
  owner: 'Owner',
  admin: 'Admin',
  member: 'Member',
};

export const TEAM_ROLE_COLORS: Record<TeamRole, string> = {
  owner: 'bg-purple-500/20 text-purple-300',
  admin: 'bg-blue-500/20 text-blue-300',
  member: 'bg-white/10 text-white/70',
};

// 녹음 상태 라벨
export const RECORDING_STATUS_LABELS: Record<RecordingStatus, string> = {
  pending: 'Pending',
  recording: 'Recording',
  completed: 'Completed',
  failed: 'Failed',
  transcribing: 'Transcribing',
  transcribed: 'Transcribed',
  transcription_failed: 'Transcription Failed',
};

export const RECORDING_STATUS_COLORS: Record<RecordingStatus, string> = {
  pending: 'bg-yellow-500/20 text-yellow-300',
  recording: 'bg-red-500/20 text-red-300',
  completed: 'bg-green-500/20 text-green-300',
  failed: 'bg-white/10 text-white/50',
  transcribing: 'bg-blue-500/20 text-blue-300',
  transcribed: 'bg-purple-500/20 text-purple-300',
  transcription_failed: 'bg-orange-500/20 text-orange-300',
};
