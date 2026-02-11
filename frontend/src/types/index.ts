// shared-types에서 타입 re-export
export type {
  // Common
  ErrorResponse,
  PaginationMeta,
  // Auth
  AuthProvider,
  AuthResponse,
  GoogleLoginUrlResponse,
  NaverLoginUrlResponse,
  RefreshTokenRequest,
  TokenResponse,
  User,
  // Team
  CreateTeamRequest,
  InviteTeamMemberRequest,
  Team,
  TeamListResponse,
  TeamMember,
  TeamRole,
  TeamWithMembers,
  UpdateTeamRequest,
  UpdateTeamMemberRequest,
  // Meeting
  AddMeetingParticipantRequest,
  CreateMeetingRequest,
  Meeting,
  MeetingListResponse,
  MeetingParticipant,
  MeetingStatus,
  MeetingWithParticipants,
  ParticipantRole,
  UpdateMeetingParticipantRequest,
  UpdateMeetingRequest,
  // Recording
  Recording,
  RecordingDownloadResponse,
  RecordingListResponse,
  RecordingStatus,
  // Transcript
  GetMeetingTranscriptsResponse,
  CreateTranscriptRequest,
  CreateTranscriptResponse,
  TranscriptDownloadResponse,
  UtteranceItem,
} from '@mit/shared-types';

// Transcript types (local - shared-types에 미정의)
export interface Utterance {
  id: string;
  timestamp: string;
  speakerName: string;
  text: string;
}

export interface MeetingTranscript {
  utterances: Utterance[];
  totalDurationMs?: number | null;
  speakerCount?: number | null;
}

// PR Review types (local)
export type {
  DecisionStatus,
  Decision,
  DecisionListResponse,
  DecisionReviewRequest,
  DecisionReviewResponse,
  PRAgenda,
  PRParticipant,
  PRMinutes,
  PRStatus,
} from './pr-review';

// KG CRUD types (local)
export type {
  UserBrief,
  SpanRef,
  DecisionBrief,
  Comment,
  CreateCommentRequest,
  Suggestion,
  CreateSuggestionRequest,
  ActionItem,
  ActionItemStatus,
  UpdateActionItemRequest,
  Agenda,
  UpdateAgendaRequest,
  DecisionWithReview,
  AgendaWithDecisions,
  MinutesResponse,
} from './kg';

// Context/Topic types (local)
export type { TopicItem, TopicFeedResponse } from './context';

// Invite Link types (local)
export interface InviteLinkResponse {
  code: string;
  inviteUrl: string;
  teamId: string;
  createdBy: string;
  createdAt: string;
  expiresAt: string;
}

export interface InvitePreviewResponse {
  teamName: string;
  teamDescription: string | null;
  memberCount: number;
  maxMembers: number;
}

export interface AcceptInviteResponse {
  teamId: string;
  role: string;
  message: string;
}
