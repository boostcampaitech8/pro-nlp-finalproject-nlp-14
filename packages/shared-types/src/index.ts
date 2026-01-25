// OpenAPI에서 자동 생성된 타입
// pnpm run generate:types 명령으로 갱신
export type * from './api';

// 편의를 위한 타입 별칭
import type { components } from './api';

// 스키마 타입 별칭
export type ErrorResponse = components['schemas']['ErrorResponse'];
export type PaginationMeta = components['schemas']['PaginationMeta'];
export type UUID = components['schemas']['UUID'];
export type Timestamp = components['schemas']['Timestamp'];

// 인증 타입 별칭
export type AuthProvider = components['schemas']['AuthProvider'];
export type User = components['schemas']['User'];
export type NaverLoginUrlResponse = components['schemas']['NaverLoginUrlResponse'];
export type GoogleLoginUrlResponse = components['schemas']['GoogleLoginUrlResponse'];
export type TokenResponse = components['schemas']['TokenResponse'];
export type AuthResponse = components['schemas']['AuthResponse'];
export type RefreshTokenRequest = components['schemas']['RefreshTokenRequest'];

// 팀 타입 별칭
export type TeamRole = components['schemas']['TeamRole'];
export type Team = components['schemas']['Team'];
export type TeamMember = components['schemas']['TeamMember'];
export type TeamWithMembers = components['schemas']['TeamWithMembers'];
export type CreateTeamRequest = components['schemas']['CreateTeamRequest'];
export type UpdateTeamRequest = components['schemas']['UpdateTeamRequest'];
export type TeamListResponse = components['schemas']['TeamListResponse'];
export type InviteTeamMemberRequest = components['schemas']['InviteTeamMemberRequest'];
export type UpdateTeamMemberRequest = components['schemas']['UpdateTeamMemberRequest'];

// 회의 타입 별칭
export type MeetingStatus = components['schemas']['MeetingStatus'];
export type ParticipantRole = components['schemas']['ParticipantRole'];
export type Meeting = components['schemas']['Meeting'];
export type MeetingParticipant = components['schemas']['MeetingParticipant'];
export type MeetingWithParticipants = components['schemas']['MeetingWithParticipants'];
export type CreateMeetingRequest = components['schemas']['CreateMeetingRequest'];
export type UpdateMeetingRequest = components['schemas']['UpdateMeetingRequest'];
export type MeetingListResponse = components['schemas']['MeetingListResponse'];
export type AddMeetingParticipantRequest = components['schemas']['AddMeetingParticipantRequest'];
export type UpdateMeetingParticipantRequest = components['schemas']['UpdateMeetingParticipantRequest'];

// 녹음 타입 별칭
export type RecordingStatus = components['schemas']['RecordingStatus'];
export type Recording = components['schemas']['Recording'];
export type RecordingListResponse = components['schemas']['RecordingListResponse'];
export type RecordingDownloadResponse = components['schemas']['RecordingDownloadResponse'];

// 트랜스크립트 타입 별칭
export type TranscriptStatus = components['schemas']['TranscriptStatus'];
export type TranscriptSegment = components['schemas']['TranscriptSegment'];
export type Utterance = components['schemas']['Utterance'];
export type MeetingTranscript = components['schemas']['MeetingTranscript'];
export type TranscribeRequest = components['schemas']['TranscribeRequest'];
export type TranscribeResponse = components['schemas']['TranscribeResponse'];
export type TranscriptStatusResponse = components['schemas']['TranscriptStatusResponse'];

// 수동 추가 (API contract 업데이트 후 삭제 예정)
export interface TranscriptDownloadResponse {
  meetingId: string;
  downloadUrl: string;
  expiresInSeconds: number;
}
