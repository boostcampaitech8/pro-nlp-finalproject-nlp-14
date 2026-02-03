/**
 * Minutes View 페이지
 *
 * 마크다운 스타일 회의록 뷰
 * Agenda/Decision 인라인 수정, Comments, Suggestions, ActionItems 통합
 */

import { useEffect, useState, useMemo, memo } from 'react';
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
  Sparkles,
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
    rejected: '부결',
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

/**
 * AI가 Decision 내용을 생성 중인지 판단
 * - suggestions 중 createdDecision이 현재 decision과 같고
 * - suggestion content와 decision content가 동일하면 → AI가 아직 처리 중
 */
function isAIGeneratingDecision(decision: DecisionWithReview): boolean {
  if (decision.status !== 'draft') return false;
  return decision.suggestions.some(
    (s) => s.createdDecision?.id === decision.id && s.content === decision.content
  );
}

/**
 * AI 생성 중인 suggestion을 찾아서 반환
 * - 사용자 요청 내용을 표시하기 위해 사용
 */
function getPendingSuggestion(decision: DecisionWithReview) {
  if (decision.status !== 'draft') return null;
  return decision.suggestions.find(
    (s) => s.createdDecision?.id === decision.id && s.content === decision.content
  ) || null;
}

// M1: Decision 카드 컴포넌트 - React.memo로 불필요한 리렌더링 방지
const DecisionCard = memo(function DecisionCard({
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

  // M2: AI가 Decision 내용을 생성 중인지 확인 - useMemo로 최적화
  const { isGenerating, pendingSuggestion } = useMemo(() => ({
    isGenerating: isAIGeneratingDecision(decision),
    pendingSuggestion: getPendingSuggestion(decision),
  }), [decision]);

  // 최종 상태 여부 (rejected 또는 latest면 suggestion 불가)
  const isFinalState = decision.status === 'latest' || decision.status === 'rejected';

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
    <div
      className={`rounded-xl border shadow-sm overflow-hidden transition-all duration-300 ${
        isGenerating
          ? 'bg-gradient-to-br from-amber-900/30 to-yellow-900/30 border-amber-500/30 animate-float'
          : 'glass-card'
      }`}
    >
      {/* AI 생성 중 배너 */}
      {isGenerating && pendingSuggestion && (
        <div className="px-4 py-3 bg-gradient-to-r from-amber-900/40 to-yellow-900/40 border-b border-amber-500/30">
          <div className="flex items-center gap-2 mb-2">
            <div className="relative">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-amber-400 rounded-full animate-ping" />
            </div>
            <span className="text-sm text-amber-300 font-medium">AI가 새로운 Decision 내용을 작성하고 있습니다...</span>
          </div>
          <div className="ml-6 p-2 bg-white/5 rounded-lg border border-amber-500/20">
            <span className="text-xs text-amber-400 font-medium">사용자 요청:</span>
            <p className="text-sm text-white/70 mt-1">{pendingSuggestion.content}</p>
          </div>
        </div>
      )}
      {/* Decision 헤더 - 클릭으로 펼치기/접기 */}
      {/* M4: 접근성 속성 추가 */}
      <div
        role="button"
        tabIndex={0}
        aria-expanded={isExpanded}
        className="p-4 border-b border-white/10 cursor-pointer hover:bg-white/5 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setIsExpanded(!isExpanded);
          }
        }}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <DecisionStatusBadge status={decision.status} />
              <div className="flex items-center gap-1 text-xs text-white/40">
                <Users className="w-3 h-3" />
                <span>
                  {decision.approvers.length} approved / {decision.rejectors.length} rejected
                </span>
              </div>
            </div>

            {/* 수정 가능한 내용 */}
            {isGenerating ? (
              <div className="flex items-center gap-2 text-white/40 italic py-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>AI가 새로운 내용을 생성하고 있습니다...</span>
              </div>
            ) : (
              <EditableText
                value={decision.content}
                onSave={async (content) => updateDecision(decision.id, { content })}
                className="text-white font-medium"
                multiline
                disabled={isFinalState}
              />
            )}

            {decision.context && (
              <p className="mt-2 text-sm text-white/60 italic">{decision.context}</p>
            )}

            {/* 이전 버전 (GT) 정보 */}
            {decision.supersedes && (
              <div className="mt-3 p-3 bg-white/5 rounded-lg border-l-4 border-white/20">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-medium text-white/50">이전 버전 (GT)</span>
                  {decision.supersedes.meetingId && (
                    <Link
                      to={`/dashboard/meetings/${decision.supersedes.meetingId}/minutes`}
                      className="text-xs text-mit-primary hover:underline"
                    >
                      해당 회의록으로 이동 →
                    </Link>
                  )}
                </div>
                <p className="text-sm text-white/50 line-through">{decision.supersedes.content}</p>
              </div>
            )}

            {/* 히스토리 타임라인 (같은 Meeting 스코프 내 superseded된 이전 버전들) */}
            {decision.history && decision.history.length > 0 && (
              <div className="mt-4 border-t border-white/10 pt-4">
                <button
                  type="button"
                  onClick={() => setShowHistory(!showHistory)}
                  className="flex items-center gap-2 text-sm text-white/50 hover:text-white/70 transition-colors"
                >
                  <ChevronDown className={`w-4 h-4 transition-transform ${showHistory ? 'rotate-180' : ''}`} />
                  히스토리 ({decision.history.length}개 이전 버전)
                </button>

                {showHistory && (
                  <div className="mt-3 space-y-2 pl-4 border-l-2 border-white/20">
                    {decision.history.map((item) => (
                      <div key={item.id} className="relative">
                        <div className="absolute -left-[9px] top-1.5 w-2 h-2 rounded-full bg-white/30" />
                        <div className="text-sm text-white/50 pl-2">
                          <p className="line-through">{item.content}</p>
                          <span className="text-xs text-white/40">
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
            <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.stopPropagation()}>
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
        className="w-full px-4 py-2 flex items-center justify-between bg-white/5 hover:bg-white/10 transition-colors"
      >
        <div className="flex items-center gap-4 text-sm text-white/60">
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
          <ChevronDown className="w-4 h-4 text-white/40" />
        ) : (
          <ChevronRight className="w-4 h-4 text-white/40" />
        )}
      </button>

      {/* 확장 영역 */}
      {isExpanded && (
        <div className="p-4 space-y-6">
          {/* 통합 입력창 */}
          {isReviewClosed ? (
            <div className="flex items-center gap-2 p-3 bg-white/5 rounded-lg text-white/50 text-sm">
              <Lock className="w-4 h-4" />
              <span>모든 결정사항이 확정되어 더 이상 댓글/제안을 추가할 수 없습니다.</span>
            </div>
          ) : (
            <div className="space-y-2">
              {isFinalState && (
                <div className="flex items-start gap-2 p-3 bg-white/5 rounded-lg text-white/60 text-sm border border-white/10">
                  <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0 text-white/40" />
                  <p>
                    {decision.status === 'latest' ? '확정된' : '부결된'} 결정사항입니다.
                    새로운 제안은 새 회의를 통해 안건으로 등록해주세요.
                  </p>
                </div>
              )}
              <UnifiedInput
                onSubmitComment={handleSubmitComment}
                onSubmitSuggestion={handleSubmitSuggestion}
                isLoading={isLoading}
                enabledModes={
                  isFinalState
                    ? ['comment', 'ask']
                    : ['comment', 'suggestion', 'ask']
                }
              />
            </div>
          )}

          {/* 댓글 목록 */}
          {decision.comments.length > 0 && (
            <div>
              <h5 className="text-sm font-medium text-white/70 mb-3 flex items-center gap-2">
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
              <h5 className="text-sm font-medium text-white/70 mb-3 flex items-center gap-2">
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
});

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
        <span className="text-3xl font-bold text-white/30">#{index + 1}</span>
        <div className="flex-1">
          <EditableText
            value={agenda.topic}
            onSave={async (topic) => updateAgenda(agenda.id, { topic })}
            className="text-2xl font-bold text-white"
          />
          {agenda.description && (
            <p className="mt-1 text-white/60">{agenda.description}</p>
          )}
        </div>
        <button
          type="button"
          onClick={handleDelete}
          disabled={isDeleting}
          className="p-2 text-white/30 hover:text-red-400 hover:bg-red-500/20 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
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
          <p className="text-white/40 text-sm italic">이 안건에 대한 결정사항이 없습니다.</p>
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
      <div className="min-h-screen gradient-bg flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-mit-primary mx-auto mb-3" />
          <p className="text-white/50">회의록을 불러오는 중...</p>
        </div>
      </div>
    );
  }

  // 에러 상태
  if (minutesError && !minutes) {
    return (
      <div className="min-h-screen gradient-bg flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">{minutesError}</p>
          <Link to="/dashboard" className="text-mit-primary hover:underline">
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
    <div className="min-h-screen gradient-bg">
      {/* 헤더 */}
      <header className="sticky top-0 z-10 glass-sidebar border-b border-white/10">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              to="/"
              className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
            >
              <Home className="w-4 h-4" />
            </Link>
            {meetingId && (
              <Link
                to={`/dashboard/meetings/${meetingId}`}
                className="flex items-center gap-1 text-white/60 hover:text-white transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="text-sm">Meeting</span>
              </Link>
            )}
            {prStatus && <PRStatusBadge status={prStatus} />}
          </div>

          <div className="flex items-center gap-4">
            {user && (
              <span className="text-sm text-white/70">
                <strong className="text-white">{user.name}</strong>
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
            <div className="mb-8 pb-6 border-b border-white/10">
              <div className="flex items-center gap-2 text-sm text-white/50 mb-2">
                <FileText className="w-4 h-4" />
                <span>Meeting Minutes</span>
              </div>
              <h1 className="text-3xl font-bold text-white mb-4">
                {minutes.agendas[0]?.decisions[0]?.meetingTitle || 'Meeting Minutes'}
              </h1>

              {/* 통계 */}
              <div className="flex items-center gap-6 text-sm text-white/60">
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
                <div className="mt-6 p-4 bg-mit-primary/10 rounded-xl border border-mit-primary/20">
                  <h3 className="text-sm font-medium text-mit-primary mb-2">Summary</h3>
                  <div className="prose prose-sm prose-invert max-w-none text-white/80">
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
                <div className="text-center py-12 text-white/50">
                  <FileText className="w-12 h-12 mx-auto mb-3 text-white/30" />
                  <p>등록된 안건이 없습니다</p>
                </div>
              )}
            </div>

            {/* Action Items 섹션 */}
            {minutes.actionItems.length > 0 && (
              <section className="pt-8 border-t border-white/10">
                <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
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
