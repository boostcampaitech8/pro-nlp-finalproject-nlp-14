/**
 * 회의실 페이지
 */

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { MeetingRoom } from '@/components/meeting/MeetingRoom';
import { useAuth } from '@/hooks/useAuth';
import { meetingService } from '@/services/meetingService';
import logger from '@/utils/logger';
import type { MeetingWithParticipants } from '@mit/shared-types';

export default function MeetingRoomPage() {
  logger.log('[MeetingRoomPage] Rendering...');
  const { meetingId } = useParams<{ meetingId: string }>();
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();

  logger.log('[MeetingRoomPage] meetingId:', meetingId, 'isAuthenticated:', isAuthenticated, 'user:', user?.id);

  const [meeting, setMeeting] = useState<MeetingWithParticipants | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 인증 확인
  useEffect(() => {
    logger.log('[MeetingRoomPage] Auth check - isAuthenticated:', isAuthenticated);
    if (!isAuthenticated) {
      logger.log('[MeetingRoomPage] Not authenticated, navigating to /login');
      navigate('/login');
    }
  }, [isAuthenticated, navigate]);

  // 회의 정보 조회
  useEffect(() => {
    if (!meetingId) return;

    const fetchMeeting = async () => {
      try {
        logger.log('[MeetingRoomPage] Fetching meeting:', meetingId);
        setLoading(true);
        const data = await meetingService.getMeeting(meetingId);
        logger.log('[MeetingRoomPage] Meeting data:', data.title, 'status:', data.status);
        setMeeting(data);

        // 회의 상태 확인
        if (data.status !== 'ongoing') {
          const errorMsg = data.status === 'scheduled'
            ? '아직 시작되지 않은 회의입니다.'
            : '이미 종료된 회의입니다.';
          logger.log('[MeetingRoomPage] Meeting not ongoing:', errorMsg);
          setError(errorMsg);
        }
      } catch (err) {
        logger.error('[MeetingRoomPage] Failed to fetch meeting:', err);
        setError('회의 정보를 불러올 수 없습니다.');
      } finally {
        setLoading(false);
      }
    };

    fetchMeeting();
  }, [meetingId]);

  logger.log('[MeetingRoomPage] State - loading:', loading, 'error:', error, 'meeting:', meeting?.title);

  // 로딩 중
  if (loading) {
    logger.log('[MeetingRoomPage] Showing loading UI');
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
          <p className="text-white text-lg">회의 정보를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  // 에러
  if (error || !meeting) {
    logger.log('[MeetingRoomPage] Showing error UI - error:', error);
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 text-6xl mb-4">!</div>
          <p className="text-white text-lg mb-2">오류</p>
          <p className="text-gray-400 mb-4">{error || '회의를 찾을 수 없습니다.'}</p>
          <button
            onClick={() => navigate(`/dashboard/meetings/${meetingId}`)}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            회의 상세로 돌아가기
          </button>
        </div>
      </div>
    );
  }

  // 유저 정보 확인
  if (!user) {
    logger.log('[MeetingRoomPage] No user, returning null');
    return null;
  }

  logger.log('[MeetingRoomPage] Rendering MeetingRoom component');

  return (
    <MeetingRoom
      meetingId={meetingId!}
      userId={user.id}
      meetingTitle={meeting.title}
      onLeave={() => navigate(`/dashboard/meetings/${meetingId}`)}
    />
  );
}
