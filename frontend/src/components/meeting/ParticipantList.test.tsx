/**
 * ParticipantList 컴포넌트 테스트
 * Force Mute 버튼 기능 테스트
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ParticipantList } from './ParticipantList';
import type { RoomParticipant } from '@/types/webrtc';

// 테스트용 참여자 데이터 생성
const createParticipant = (
  userId: string,
  userName: string,
  role: 'host' | 'participant' = 'participant',
  audioMuted = false
): RoomParticipant => ({
  userId,
  userName,
  role,
  audioMuted,
});

describe('ParticipantList - Force Mute', () => {
  const mockOnVolumeChange = vi.fn();
  const mockOnForceMute = vi.fn();

  const hostParticipant = createParticipant('host-id', 'Host User', 'host');
  const participant1 = createParticipant('user-1', 'User One');
  const participant2 = createParticipant('user-2', 'User Two', 'participant', true);

  const participants = new Map<string, RoomParticipant>([
    ['host-id', hostParticipant],
    ['user-1', participant1],
    ['user-2', participant2],
  ]);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Host가 아니면 Force Mute 버튼이 표시되지 않는다', async () => {
    await act(async () => {
      render(
        <ParticipantList
          participants={participants}
          currentUserId="user-1" // 일반 참여자
          localMuteState={false}
          remoteVolumes={new Map()}
          onVolumeChange={mockOnVolumeChange}
          isHost={false}
          onForceMute={mockOnForceMute}
        />
      );
    });

    // Force Mute 버튼이 없어야 함
    expect(screen.queryByRole('button', { name: /mute/i })).not.toBeInTheDocument();
  });

  it('Host인 경우 다른 참여자에게 Force Mute 버튼이 표시된다', async () => {
    await act(async () => {
      render(
        <ParticipantList
          participants={participants}
          currentUserId="host-id" // Host
          localMuteState={false}
          remoteVolumes={new Map()}
          onVolumeChange={mockOnVolumeChange}
          isHost={true}
          onForceMute={mockOnForceMute}
        />
      );
    });

    // 다른 참여자들에게 Mute 버튼이 있어야 함
    const muteButtons = screen.getAllByRole('button', { name: /mute/i });
    // host 자신 제외, user-1, user-2 두 명에게 버튼 표시
    expect(muteButtons).toHaveLength(2);
  });

  it('Host 자신에게는 Force Mute 버튼이 표시되지 않는다', async () => {
    // Host만 있는 경우
    const onlyHost = new Map<string, RoomParticipant>([['host-id', hostParticipant]]);

    await act(async () => {
      render(
        <ParticipantList
          participants={onlyHost}
          currentUserId="host-id"
          localMuteState={false}
          remoteVolumes={new Map()}
          onVolumeChange={mockOnVolumeChange}
          isHost={true}
          onForceMute={mockOnForceMute}
        />
      );
    });

    // Mute 버튼이 없어야 함 (자기 자신에게는 표시 안 됨)
    expect(screen.queryByRole('button', { name: /mute/i })).not.toBeInTheDocument();
  });

  it('Force Mute 버튼 클릭 시 onForceMute 콜백이 호출된다', async () => {
    const user = userEvent.setup();

    await act(async () => {
      render(
        <ParticipantList
          participants={participants}
          currentUserId="host-id"
          localMuteState={false}
          remoteVolumes={new Map()}
          onVolumeChange={mockOnVolumeChange}
          isHost={true}
          onForceMute={mockOnForceMute}
        />
      );
    });

    // User One의 Mute 버튼 클릭 (음소거되지 않은 상태)
    const muteButtons = screen.getAllByRole('button', { name: /mute/i });
    await user.click(muteButtons[0]);

    expect(mockOnForceMute).toHaveBeenCalledWith('user-1', true);
  });

  it('이미 음소거된 참여자에게는 Unmute 버튼이 표시된다', async () => {
    const user = userEvent.setup();

    await act(async () => {
      render(
        <ParticipantList
          participants={participants}
          currentUserId="host-id"
          localMuteState={false}
          remoteVolumes={new Map()}
          onVolumeChange={mockOnVolumeChange}
          isHost={true}
          onForceMute={mockOnForceMute}
        />
      );
    });

    // User Two는 이미 음소거된 상태
    const unmuteButton = screen.getByRole('button', { name: /unmute/i });
    expect(unmuteButton).toBeInTheDocument();

    // Unmute 버튼 클릭
    await user.click(unmuteButton);
    expect(mockOnForceMute).toHaveBeenCalledWith('user-2', false);
  });
});
