/**
 * WebRTC 시그널링 관련 타입 정의
 */

// 시그널링 메시지 타입
export type SignalingMessageType =
  | 'join'
  | 'offer'
  | 'answer'
  | 'ice-candidate'
  | 'leave'
  | 'mute'
  | 'joined'
  | 'participant-joined'
  | 'participant-left'
  | 'participant-muted'
  | 'meeting-ended'
  | 'error';

// 회의실 참여자 정보
export interface RoomParticipant {
  userId: string;
  userName: string;
  role: 'host' | 'participant';
  audioMuted: boolean;
}

// ICE 서버 설정
export interface IceServer {
  urls: string;
  username?: string;
  credential?: string;
}

// 회의실 정보 응답
export interface MeetingRoomResponse {
  meetingId: string;
  status: string;
  participants: RoomParticipant[];
  iceServers: IceServer[];
  maxParticipants: number;
}

// 회의 시작 응답
export interface StartMeetingResponse {
  meetingId: string;
  status: string;
  startedAt: string;
}

// 회의 종료 응답
export interface EndMeetingResponse {
  meetingId: string;
  status: string;
  endedAt: string;
}

// ===== Client -> Server 메시지 =====

export interface JoinMessage {
  type: 'join';
}

export interface OfferMessage {
  type: 'offer';
  sdp: RTCSessionDescriptionInit;
  targetUserId: string;
}

export interface AnswerMessage {
  type: 'answer';
  sdp: RTCSessionDescriptionInit;
  targetUserId: string;
}

export interface IceCandidateMessage {
  type: 'ice-candidate';
  candidate: RTCIceCandidateInit;
  targetUserId?: string;
}

export interface LeaveMessage {
  type: 'leave';
}

export interface MuteMessage {
  type: 'mute';
  muted: boolean;
}

export type ClientMessage =
  | JoinMessage
  | OfferMessage
  | AnswerMessage
  | IceCandidateMessage
  | LeaveMessage
  | MuteMessage;

// ===== Server -> Client 메시지 =====

export interface JoinedMessage {
  type: 'joined';
  participants: RoomParticipant[];
}

export interface ParticipantJoinedMessage {
  type: 'participant-joined';
  participant: RoomParticipant;
}

export interface ParticipantLeftMessage {
  type: 'participant-left';
  userId: string;
}

export interface ServerOfferMessage {
  type: 'offer';
  sdp: RTCSessionDescriptionInit;
  fromUserId: string;
}

export interface ServerAnswerMessage {
  type: 'answer';
  sdp: RTCSessionDescriptionInit;
  fromUserId: string;
}

export interface ServerIceCandidateMessage {
  type: 'ice-candidate';
  candidate: RTCIceCandidateInit;
  fromUserId: string;
}

export interface ParticipantMutedMessage {
  type: 'participant-muted';
  userId: string;
  muted: boolean;
}

export interface MeetingEndedMessage {
  type: 'meeting-ended';
  reason: string;
}

export interface ErrorMessage {
  type: 'error';
  code: string;
  message: string;
}

export type ServerMessage =
  | JoinedMessage
  | ParticipantJoinedMessage
  | ParticipantLeftMessage
  | ServerOfferMessage
  | ServerAnswerMessage
  | ServerIceCandidateMessage
  | ParticipantMutedMessage
  | MeetingEndedMessage
  | ErrorMessage;

// 연결 상태
export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'failed';

// 피어 연결 정보
export interface PeerConnection {
  peerId: string;
  connection: RTCPeerConnection;
  stream?: MediaStream;
}
