/**
 * WebRTC 서비스
 * PeerConnection 관리 및 미디어 스트림 처리
 */

import type { IceServer } from '@/types/webrtc';

/**
 * PeerConnection 생성
 */
export function createPeerConnection(
  iceServers: IceServer[],
  onIceCandidate: (candidate: RTCIceCandidate) => void,
  onTrack: (event: RTCTrackEvent) => void,
  onConnectionStateChange: (state: RTCPeerConnectionState) => void
): RTCPeerConnection {
  const config: RTCConfiguration = {
    iceServers: iceServers.map((server) => ({
      urls: server.urls,
      username: server.username,
      credential: server.credential,
    })),
  };

  const pc = new RTCPeerConnection(config);

  pc.onicecandidate = (event) => {
    if (event.candidate) {
      onIceCandidate(event.candidate);
    }
  };

  pc.ontrack = (event) => {
    onTrack(event);
  };

  pc.onconnectionstatechange = () => {
    onConnectionStateChange(pc.connectionState);
  };

  return pc;
}

/**
 * 로컬 오디오 스트림 획득
 */
export async function getLocalAudioStream(): Promise<MediaStream> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: true,
      video: false, // 오디오만
    });
    return stream;
  } catch (error) {
    console.error('[WebRTC] Failed to get local audio stream:', error);
    throw error;
  }
}

/**
 * SDP Offer 생성
 */
export async function createOffer(pc: RTCPeerConnection): Promise<RTCSessionDescriptionInit> {
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  return offer;
}

/**
 * SDP Answer 생성
 */
export async function createAnswer(
  pc: RTCPeerConnection,
  offer: RTCSessionDescriptionInit
): Promise<RTCSessionDescriptionInit> {
  await pc.setRemoteDescription(new RTCSessionDescription(offer));
  const answer = await pc.createAnswer();
  await pc.setLocalDescription(answer);
  return answer;
}

/**
 * Remote Description 설정
 */
export async function setRemoteDescription(
  pc: RTCPeerConnection,
  sdp: RTCSessionDescriptionInit
): Promise<void> {
  await pc.setRemoteDescription(new RTCSessionDescription(sdp));
}

/**
 * ICE Candidate 추가
 */
export async function addIceCandidate(
  pc: RTCPeerConnection,
  candidate: RTCIceCandidateInit
): Promise<void> {
  try {
    await pc.addIceCandidate(new RTCIceCandidate(candidate));
  } catch (error) {
    console.error('[WebRTC] Failed to add ICE candidate:', error);
  }
}

/**
 * 트랙 추가
 */
export function addTrack(
  pc: RTCPeerConnection,
  track: MediaStreamTrack,
  stream: MediaStream
): RTCRtpSender {
  return pc.addTrack(track, stream);
}

/**
 * 오디오 트랙 음소거 토글
 */
export function toggleAudioMute(stream: MediaStream, muted: boolean): void {
  stream.getAudioTracks().forEach((track) => {
    track.enabled = !muted;
  });
}

/**
 * PeerConnection 종료
 */
export function closeConnection(pc: RTCPeerConnection): void {
  pc.close();
}

/**
 * MediaStream 정리
 */
export function stopStream(stream: MediaStream): void {
  stream.getTracks().forEach((track) => {
    track.stop();
  });
}

// 서비스 객체로 export
export const webrtcService = {
  createPeerConnection,
  getLocalAudioStream,
  createOffer,
  createAnswer,
  setRemoteDescription,
  addIceCandidate,
  addTrack,
  toggleAudioMute,
  closeConnection,
  stopStream,
};
