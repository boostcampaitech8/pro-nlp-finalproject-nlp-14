/**
 * Minutes View 페이지
 *
 * 마크다운 스타일 회의록 뷰
 * Agenda/Decision 인라인 수정, Comments, Suggestions, ActionItems 통합
 */

import { useEffect, useState, useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Home,
  FileText,
  MessageSquare,
  Lightbulb,
  ListTodo,
  ChevronDown,
  ChevronRight,
  Trash2,
  Loader2,
  CheckCircle2,
  Users,
  Check,
  X,
  Lock,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
import { useKGStore } from '@/stores/kgStore';
import type { DecisionWithReview, AgendaWithDecisions } from '@/types';

import { UnifiedInput, CommentItem } from '../components/review/comments';
import { SuggestionItem } from '../components/review/suggestions';
import { ActionItemList } from '../components/review/actionitems';
import { EditableText } from '../components/review/EditableText';
import { PRStatusBadge } from '../components/review/PRStatusBadge';

// Decision 상태 배지
const DecisionStatusBadge = ({ status }: { status: string }) => {
  const styles: Record<string, string> = {
    draft: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    latest: 'bg-blue-100 text-blue-700 border-blue-200',
    approved: 'bg-green-100 text-green-700 border-green-200',
    rejected: 'bg-red-100 text-red-700 border-red-200',
    outdated: 'bg-gray-100 text-gray-500 border-gray-200',
    superseded: 'bg-purple-100 text-purple-700 border-purple-200',
  };

  const labels: Record<string, string> = {
    draft: 'Draft',
    latest: 'Latest',
    approved: 'Approved',
    rejected: 'Rejected',
    outdated: 'Outdated',
    superseded: 'Superseded',
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full border ${styles[status] || styles.draft}`}
    >
      {labels[status] || status}
    </span>
  );
};

// Decision 카드 컴포넌트
function DecisionCard({
  decision,
  meetingId,
  currentUserId,
  isReviewClosed,
}: {
  decision: DecisionWithReview;
  meetingId: string;
  currentUserId?: string;
  isReviewClosed: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const {
    addComment,
    addReply,
    removeComment,
    addSuggestion,
    updateDecision,
    approveDecision,
    rejectDecision,
    actionLoading,
    fetchMinutes,
  } = useKGStore();

  const isLoading =
    actionLoading[`comment-${decision.id}`] || actionLoading[`suggestion-${decision.id}`];
  const isApproving = actionLoading[`approve-${decision.id}`];
  const isRejecting = actionLoading[`reject-${decision.id}`];

  // 이미 승인/거절했는지 확인 (currentUserId가 approvers/rejectors에 있는지)
  const hasApproved = currentUserId && decision.approvers.includes(currentUserId);
  const hasRejected = currentUserId && decision.rejectors.includes(currentUserId);
  const canReview = decision.status === 'draft' && !hasApproved && !hasRejected;

  const handleSubmitComment = async (content: string) => {
    await addComment(decision.id, content);
  };

  const handleSubmitSuggestion = async (content: string) => {
    await addSuggestion(decision.id, content, meetingId);
  };

  const handleReply = async (commentId: string, content: string) => {
    await addReply(commentId, decision.id, content);
  };

  const handleDeleteComment = async (commentId: string) => {
    await removeComment(commentId, decision.id);
  };

  const handleApprove = async () => {
    await approveDecision(decision.id);
  };

  const handleReject = async () => {
    await rejectDecision(decision.id);
  };

  const handleRefresh = () => {
    fetchMinutes(meetingId);
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Decision 헤더 */}
      <div className="p-4 border-b border-gray-100">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <DecisionStatusBadge status={decision.status} />
              <div className="flex items-center gap-1 text-xs text-gray-400">
                <Users className="w-3 h-3" />
                <span>
                  {decision.approvers.length} approved / {decision.rejectors.length} rejected
                </span>
              </div>
            </div>

            {/* 수정 가능한 내용 */}
            <EditableText
              value={decision.content}
              onSave={async (content) => updateDecision(decision.id, { content })}
              className="text-gray-900 font-medium"
              multiline
            />

            {decision.context && (
              <p className="mt-2 text-sm text-gray-600 italic">{decision.context}</p>
            )}

            {/* 이전 버전 (GT) 정보 */}
            {decision.supersedes && (
              <div className="mt-3 p-3 bg-gray-50 rounded-lg border-l-4 border-gray-300">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-medium text-gray-500">이전 버전 (GT)</span>
                  {decision.supersedes.meetingId && (
                    <Link
                      to={`/dashboard/meetings/${decision.supersedes.meetingId}/minutes`}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      해당 회의록으로 이동 →
                    </Link>
                  )}
                </div>
                <p className="text-sm text-gray-600 line-through">{decision.supersedes.content}</p>
              </div>
            )}

            {/* 히스토리 타임라인 (같은 Meeting 스코프 내 superseded된 이전 버전들) */}
            {decision.history && decision.history.length > 0 && (
              <div className="mt-4 border-t pt-4">
                <button
                  type="button"
                  onClick={() => setShowHistory(!showHistory)}
                  className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 transition-colors"
                >
                  <ChevronDown className={`w-4 h-4 transition-transform ${showHistory ? 'rotate-180' : ''}`} />
                  히스토리 ({decision.history.length}개 이전 버전)
                </button>

                {showHistory && (
                  <div className="mt-3 space-y-2 pl-4 border-l-2 border-gray-200">
                    {decision.history.map((item) => (
                      <div key={item.id} className="relative">
                        <div className="absolute -left-[9px] top-1.5 w-2 h-2 rounded-full bg-gray-300" />
                        <div className="text-sm text-gray-500 pl-2">
                          <p className="line-through">{item.content}</p>
                          <span className="text-xs text-gray-400">
                            {new Date(item.createdAt).toLocaleDateString('ko-KR', {
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 승인/거절 버튼 */}
          {canReview && (
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={handleApprove}
                disabled={isApproving || isRejecting}
                className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isApproving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Check className="w-4 h-4" />
                )}
                Approve
              </button>
              <button
                type="button"
                onClick={handleReject}
                disabled={isApproving || isRejecting}
                className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isRejecting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <X className="w-4 h-4" />
                )}
                Reject
              </button>
            </div>
          )}
          {hasApproved && (
            <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">
              You approved
            </span>
          )}
          {hasRejected && (
            <span className="text-xs text-red-600 bg-red-50 px-2 py-1 rounded-full">
              You rejected
            </span>
          )}
        </div>
      </div>

      {/* 펼치기/접기 버튼 */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-2 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-4 text-sm text-gray-600">
          <span className="flex items-center gap-1">
            <MessageSquare className="w-4 h-4" />
            {decision.comments.length} comments
          </span>
          <span className="flex items-center gap-1">
            <Lightbulb className="w-4 h-4" />
            {decision.suggestions.length} suggestions
          </span>
        </div>
        {isExpanded ? (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-400" />
        )}
      </button>

      {/* 확장 영역 */}
      {isExpanded && (
        <div className="p-4 space-y-6">
          {/* 통합 입력창 */}
          {isReviewClosed ? (
            <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg text-gray-500 text-sm">
              <Lock className="w-4 h-4" />
              <span>모든 결정사항이 확정되어 더 이상 댓글/제안을 추가할 수 없습니다.</span>
            </div>
          ) : (
            <UnifiedInput
              onSubmitComment={handleSubmitComment}
              onSubmitSuggestion={handleSubmitSuggestion}
              isLoading={isLoading}
            />
          )}

          {/* 댓글 목록 */}
          {decision.comments.length > 0 && (
            <div>
              <h5 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                <MessageSquare className="w-4 h-4" />
                Comments
              </h5>
              <div className="space-y-3">
                {decision.comments.map((comment) => (
                  <CommentItem
                    key={comment.id}
                    comment={comment}
                    decisionId={decision.id}
                    currentUserId={currentUserId}
                    onReply={handleReply}
                    onDelete={handleDeleteComment}
                    onRefresh={handleRefresh}
                  />
                ))}
              </div>
            </div>
          )}

          {/* 제안 목록 */}
          {decision.suggestions.length > 0 && (
            <div>
              <h5 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
                <Lightbulb className="w-4 h-4" />
                Suggestions
              </h5>
              <div className="space-y-3">
                {decision.suggestions.map((suggestion) => (
                  <SuggestionItem key={suggestion.id} suggestion={suggestion} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Agenda 섹션 컴포넌트
function AgendaSection({
  agenda,
  index,
  meetingId,
  currentUserId,
  isReviewClosed,
}: {
  agenda: AgendaWithDecisions;
  index: number;
  meetingId: string;
  currentUserId?: string;
  isReviewClosed: boolean;
}) {
  const { updateAgenda, removeAgenda } = useKGStore();
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    if (!confirm('이 안건을 삭제하시겠습니까? 하위 결정사항도 모두 삭제됩니다.')) return;
    setIsDeleting(true);
    try {
      await removeAgenda(agenda.id);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <section className="mb-8">
      {/* Agenda 헤더 - 마크다운 스타일 */}
      <div className="group flex items-start gap-3 mb-4">
        <span className="text-2xl font-bold text-gray-300">#{index + 1}</span>
        <div className="flex-1">
          <EditableText
            value={agenda.topic}
            onSave={async (topic) => updateAgenda(agenda.id, { topic })}
            className="text-xl font-bold text-gray-900"
          />
          {agenda.description && (
            <p className="mt-1 text-gray-600">{agenda.description}</p>
          )}
        </div>
        <button
          type="button"
          onClick={handleDelete}
          disabled={isDeleting}
          className="p-2 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
          title="안건 삭제"
        >
          {isDeleting ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Trash2 className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Decisions */}
      <div className="space-y-4 ml-8">
        {agenda.decisions.map((decision) => (
          <DecisionCard
            key={decision.id}
            decision={decision}
            meetingId={meetingId}
            currentUserId={currentUserId}
            isReviewClosed={isReviewClosed}
          />
        ))}

        {agenda.decisions.length === 0 && (
          <p className="text-gray-400 text-sm italic">이 안건에 대한 결정사항이 없습니다.</p>
        )}
      </div>
    </section>
  );
}

// 메인 페이지
export function MinutesViewPage() {
  const { meetingId } = useParams<{ meetingId: string }>();
  const { user, logout, isLoading: authLoading } = useAuth();
  const {
    minutes,
    minutesLoading,
    minutesError,
    prStatus,
    fetchMinutes,
    updateActionItem,
    removeActionItem,
    isAllDecisionsLatest,
    reset,
  } = useKGStore();

  useEffect(() => {
    if (meetingId) {
      fetchMinutes(meetingId);
    }
    return () => reset();
  }, [meetingId, fetchMinutes, reset]);

  // Minutes SSE 구독 - 실시간 업데이트
  useEffect(() => {
    if (!meetingId) return;

    const eventSource = new EventSource(`/api/v1/meetings/${meetingId}/minutes/events`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // keepalive는 무시
        if (data.event === 'keepalive') return;

        console.log('[MinutesSSE] Event received:', data.event);

        // 모든 이벤트에서 Minutes 재조회 (간단한 구현)
        // 추후 부분 업데이트로 최적화 가능
        fetchMinutes(meetingId);
      } catch (e) {
        console.error('[MinutesSSE] Parse error:', e);
      }
    };

    eventSource.onerror = (error) => {
      console.error('[MinutesSSE] Connection error:', error);
      // 연결 끊김 시 자동 재연결 (EventSource 기본 동작)
    };

    return () => {
      eventSource.close();
      console.log('[MinutesSSE] Disconnected');
    };
  }, [meetingId, fetchMinutes]);

  // 모든 Decision이 latest 상태인지 확인 (리뷰 비활성화용)
  const isReviewClosed = useMemo(() => isAllDecisionsLatest(), [minutes]);

  // 로딩 상태
  if (minutesLoading && !minutes) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto mb-3" />
          <p className="text-gray-500">회의록을 불러오는 중...</p>
        </div>
      </div>
    );
  }

  // 에러 상태
  if (minutesError && !minutes) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 mb-4">{minutesError}</p>
          <Link to="/dashboard" className="text-blue-600 hover:underline">
            홈으로 돌아가기
          </Link>
        </div>
      </div>
    );
  }

  const totalDecisions = minutes?.agendas.reduce((sum, a) => sum + a.decisions.length, 0) || 0;
  const totalComments =
    minutes?.agendas.reduce(
      (sum, a) => sum + a.decisions.reduce((dSum, d) => dSum + d.comments.length, 0),
      0
    ) || 0;

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* 헤더 */}
      <header className="sticky top-0 z-10 bg-white/80 backdrop-blur-sm border-b border-gray-100">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              to="/"
              className="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
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
            {prStatus && <PRStatusBadge status={prStatus} />}
          </div>

          <div className="flex items-center gap-4">
            {user && (
              <span className="text-sm text-gray-600">
                <strong>{user.name}</strong>
              </span>
            )}
            <Button variant="outline" onClick={logout} isLoading={authLoading}>
              Logout
            </Button>
          </div>
        </div>
      </header>

      {/* 메인 컨텐츠 */}
      <main className="max-w-4xl mx-auto px-4 py-8">
        {minutes && (
          <>
            {/* 제목 영역 - 마크다운 스타일 */}
            <div className="mb-8 pb-6 border-b border-gray-200">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
                <FileText className="w-4 h-4" />
                <span>Meeting Minutes</span>
              </div>
              <h1 className="text-3xl font-bold text-gray-900 mb-4">
                {minutes.agendas[0]?.decisions[0]?.meetingTitle || 'Meeting Minutes'}
              </h1>

              {/* 통계 */}
              <div className="flex items-center gap-6 text-sm text-gray-600">
                <span className="flex items-center gap-1">
                  <ListTodo className="w-4 h-4" />
                  {minutes.agendas.length} agendas
                </span>
                <span className="flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" />
                  {totalDecisions} decisions
                </span>
                <span className="flex items-center gap-1">
                  <MessageSquare className="w-4 h-4" />
                  {totalComments} comments
                </span>
              </div>

              {/* 요약 */}
              {minutes.summary && (
                <div className="mt-6 p-4 bg-blue-50 rounded-xl border border-blue-100">
                  <h3 className="text-sm font-medium text-blue-800 mb-2">Summary</h3>
                  <div className="prose prose-sm prose-blue max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {minutes.summary}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>

            {/* Agendas */}
            <div className="mb-12">
              {minutes.agendas.map((agenda, index) => (
                <AgendaSection
                  key={agenda.id}
                  agenda={agenda}
                  index={index}
                  meetingId={minutes.meetingId}
                  currentUserId={user?.id}
                  isReviewClosed={isReviewClosed}
                />
              ))}

              {minutes.agendas.length === 0 && (
                <div className="text-center py-12 text-gray-500">
                  <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                  <p>등록된 안건이 없습니다</p>
                </div>
              )}
            </div>

            {/* Action Items 섹션 */}
            {minutes.actionItems.length > 0 && (
              <section className="pt-8 border-t border-gray-200">
                <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                  <ListTodo className="w-5 h-5" />
                  Action Items
                </h2>
                <ActionItemList
                  items={minutes.actionItems}
                  onUpdate={updateActionItem}
                  onDelete={removeActionItem}
                />
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
