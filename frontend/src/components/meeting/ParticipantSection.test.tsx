/**
 * ParticipantSection 컴포넌트 테스트
 * 다중 선택 기능 테스트
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ParticipantSection } from './ParticipantSection';
import type { MeetingParticipant, TeamMember } from '@/types';

// 테스트용 유저 데이터 생성 헬퍼
const createMockUser = (id: string, name: string, email: string) => ({
  id,
  name,
  email,
  authProvider: 'local' as const,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
});

// 테스트용 팀 멤버 데이터
const mockAvailableMembers: TeamMember[] = [
  {
    id: 'tm-1',
    userId: 'user-1',
    teamId: 'team-1',
    role: 'member',
    joinedAt: new Date().toISOString(),
    user: createMockUser('user-1', 'User One', 'user1@test.com'),
  },
  {
    id: 'tm-2',
    userId: 'user-2',
    teamId: 'team-1',
    role: 'member',
    joinedAt: new Date().toISOString(),
    user: createMockUser('user-2', 'User Two', 'user2@test.com'),
  },
  {
    id: 'tm-3',
    userId: 'user-3',
    teamId: 'team-1',
    role: 'member',
    joinedAt: new Date().toISOString(),
    user: createMockUser('user-3', 'User Three', 'user3@test.com'),
  },
];

// 테스트용 참여자 데이터
const mockParticipants: MeetingParticipant[] = [
  {
    id: 'p1',
    meetingId: 'meeting-1',
    userId: 'host-user',
    role: 'host',
    joinedAt: new Date().toISOString(),
    user: createMockUser('host-user', 'Host User', 'host@test.com'),
  },
];

describe('ParticipantSection - 다중 선택', () => {
  const mockOnAddParticipant = vi.fn().mockResolvedValue(undefined);
  const mockOnUpdateRole = vi.fn().mockResolvedValue(undefined);
  const mockOnRemoveParticipant = vi.fn();

  const defaultProps = {
    participants: mockParticipants,
    availableMembers: mockAvailableMembers,
    currentUserId: 'host-user',
    isHost: true,
    onAddParticipant: mockOnAddParticipant,
    onUpdateRole: mockOnUpdateRole,
    onRemoveParticipant: mockOnRemoveParticipant,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Add Participant 버튼 클릭 시 폼이 표시된다', async () => {
    const user = userEvent.setup();
    render(<ParticipantSection {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /add participant/i }));

    expect(screen.getByText(/team member/i)).toBeInTheDocument();
  });

  it('여러 멤버를 체크박스로 선택할 수 있다', async () => {
    const user = userEvent.setup();
    render(<ParticipantSection {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /add participant/i }));

    // 멤버 체크박스들이 표시되어야 함
    const checkbox1 = screen.getByRole('checkbox', { name: /user one/i });
    const checkbox2 = screen.getByRole('checkbox', { name: /user two/i });

    expect(checkbox1).toBeInTheDocument();
    expect(checkbox2).toBeInTheDocument();

    // 체크박스 선택
    await user.click(checkbox1);
    await user.click(checkbox2);

    expect(checkbox1).toBeChecked();
    expect(checkbox2).toBeChecked();
  });

  it('여러 멤버를 선택하고 한 번에 추가할 수 있다', async () => {
    const user = userEvent.setup();
    render(<ParticipantSection {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /add participant/i }));

    // 두 명 선택
    await user.click(screen.getByRole('checkbox', { name: /user one/i }));
    await user.click(screen.getByRole('checkbox', { name: /user two/i }));

    // 추가 버튼 클릭
    await user.click(screen.getByRole('button', { name: /^add$/i }));

    // onAddParticipant가 두 번 호출되어야 함
    await waitFor(() => {
      expect(mockOnAddParticipant).toHaveBeenCalledTimes(2);
    });

    expect(mockOnAddParticipant).toHaveBeenCalledWith(
      'user-1',
      expect.any(String)
    );
    expect(mockOnAddParticipant).toHaveBeenCalledWith(
      'user-2',
      expect.any(String)
    );
  });

  it('선택된 멤버 수를 표시한다', async () => {
    const user = userEvent.setup();
    render(<ParticipantSection {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /add participant/i }));

    await user.click(screen.getByRole('checkbox', { name: /user one/i }));
    await user.click(screen.getByRole('checkbox', { name: /user two/i }));

    expect(screen.getByText(/2.*selected/i)).toBeInTheDocument();
  });

  it('선택 없이 추가 버튼이 비활성화된다', async () => {
    const user = userEvent.setup();
    render(<ParticipantSection {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /add participant/i }));

    // 아무것도 선택 안 하면 버튼 비활성화
    const addButton = screen.getByRole('button', { name: /^add$/i });
    expect(addButton).toBeDisabled();
  });

  it('전체 선택 체크박스가 동작한다', async () => {
    const user = userEvent.setup();
    render(<ParticipantSection {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /add participant/i }));

    // 전체 선택 클릭
    const selectAll = screen.getByRole('checkbox', { name: /select all/i });
    await user.click(selectAll);

    // 모든 체크박스가 선택됨
    expect(screen.getByRole('checkbox', { name: /user one/i })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: /user two/i })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: /user three/i })).toBeChecked();
  });

  it('전체 선택 후 다시 클릭하면 전체 해제된다', async () => {
    const user = userEvent.setup();
    render(<ParticipantSection {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /add participant/i }));

    const selectAll = screen.getByRole('checkbox', { name: /select all/i });

    // 전체 선택
    await user.click(selectAll);
    expect(screen.getByRole('checkbox', { name: /user one/i })).toBeChecked();

    // 전체 해제
    await user.click(selectAll);
    expect(
      screen.getByRole('checkbox', { name: /user one/i })
    ).not.toBeChecked();
  });

  it('Host가 아니면 Add Participant 버튼이 표시되지 않는다', () => {
    render(<ParticipantSection {...defaultProps} isHost={false} />);

    expect(
      screen.queryByRole('button', { name: /add participant/i })
    ).not.toBeInTheDocument();
  });

  it('availableMembers가 비어있으면 Add Participant 버튼이 표시되지 않는다', () => {
    render(<ParticipantSection {...defaultProps} availableMembers={[]} />);

    expect(
      screen.queryByRole('button', { name: /add participant/i })
    ).not.toBeInTheDocument();
  });

  it('Cancel 버튼 클릭 시 폼이 닫힌다', async () => {
    const user = userEvent.setup();
    render(<ParticipantSection {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /add participant/i }));
    expect(screen.getByText(/team member/i)).toBeInTheDocument();

    // 폼 내부의 Cancel 버튼 (type="button") 클릭
    const cancelButtons = screen.getAllByRole('button', { name: /cancel/i });
    const formCancelButton = cancelButtons.find(btn => btn.getAttribute('type') === 'button');
    await user.click(formCancelButton!);
    expect(screen.queryByText(/team member/i)).not.toBeInTheDocument();
  });

  it('추가 완료 후 폼이 닫히고 선택이 초기화된다', async () => {
    const user = userEvent.setup();
    render(<ParticipantSection {...defaultProps} />);

    await user.click(screen.getByRole('button', { name: /add participant/i }));
    await user.click(screen.getByRole('checkbox', { name: /user one/i }));
    await user.click(screen.getByRole('button', { name: /^add$/i }));

    // 폼이 닫힘
    await waitFor(() => {
      expect(screen.queryByRole('checkbox', { name: /user one/i })).not.toBeInTheDocument();
    });
  });
});
