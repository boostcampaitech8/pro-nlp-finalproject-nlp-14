/**
 * PR 리뷰 페이지
 *
 * 회의록 검토 및 결정사항 승인/거절
 */

import { useEffect, useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Home } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
import { usePRReviewStore } from '@/stores/prReviewStore';
import type { PRParticipant } from '@/types';
import {
  DecisionList,
  MinutesHeader,
  PRStatusBadge,
} from '@/dashboard/components/review';

export function PRReviewPage() {
  const { meetingId } = useParams<{ meetingId: string }>();
  const { user, logout, isLoading: authLoading } = useAuth();
  const { meeting, agendas, prStatus, loading, error, fetchMeetingReview, reset } =
    usePRReviewStore();

  useEffect(() => {
    if (meetingId) {
      fetchMeetingReview(meetingId);
    }
    // 컴포넌트 언마운트 시 상태 초기화
    return () => reset();
  }, [meetingId, fetchMeetingReview, reset]);

  // 참여자 목록 변환
  const participants: PRParticipant[] = useMemo(() => {
    if (!meeting?.participants) return [];
    return meeting.participants.map((p) => ({
      id: p.userId,
      name: p.user?.name || 'Unknown',
    }));
  }, [meeting?.participants]);

  if (loading && !meeting) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">Loading meeting review...</p>
      </div>
    );
  }

  if (error && !meeting) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{error}</p>
          <Link to="/dashboard" className="text-blue-600 hover:underline">
            Back to Home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              to="/"
              className="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              title="Home"
            >
              <Home className="w-4 h-4" />
            </Link>
            {meetingId && (
              <Link
                to={`/dashboard/meetings/${meetingId}`}
                className="flex items-center gap-1 text-gray-500 hover:text-gray-700 transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="text-sm">Meeting</span>
              </Link>
            )}
            <span className="text-gray-300">|</span>
            <h1 className="text-xl font-bold text-gray-900">
              PR Review: {meeting?.title || 'Meeting'}
            </h1>
            {prStatus && <PRStatusBadge status={prStatus} />}
          </div>

          <div className="flex items-center gap-4">
            {user && (
              <span className="text-gray-600">
                Hello, <strong>{user.name}</strong>
              </span>
            )}
            <Button variant="outline" onClick={logout} isLoading={authLoading}>
              Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* 에러 메시지 */}
        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-6">
            {error}
          </div>
        )}

        {/* 회의록 헤더 */}
        {meeting && (
          <MinutesHeader
            title={meeting.title}
            description={meeting.description}
            createdAt={meeting.createdAt}
            participants={participants}
          />
        )}

        {/* 결정사항 목록 */}
        {meeting && (
          <div className="mt-8">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              Decisions to Review
            </h3>
            <DecisionList
              agendas={agendas}
              currentUserId={user?.id}
              participants={participants}
            />
          </div>
        )}

        {/* 빈 상태 */}
        {meeting && agendas.length === 0 && (
          <div className="mt-8 bg-gray-50 rounded-xl p-8 text-center">
            <p className="text-gray-500">
              No decisions found for this meeting.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
