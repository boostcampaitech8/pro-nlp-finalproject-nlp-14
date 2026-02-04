// 세션 목록 컴포넌트
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Trash2, MessageSquare } from 'lucide-react';
import { useCommandStore } from '@/app/stores/commandStore';
import { spotlightApi } from '@/app/services/spotlightApi';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/app/utils/dateUtils';

export function SessionList() {
  const navigate = useNavigate();
  const {
    sessions,
    sessionsLoading,
    currentSessionId,
    removeSession,
    loadSessions,
    createNewSession,
    abortCurrentStream,
    sessionsWithNewResponse,
  } = useCommandStore();

  // 컴포넌트 마운트 시 세션 목록 로드
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const handleSessionClick = (sessionId: string) => {
    // URL 이동만 수행 (abort는 setCurrentSession에서 처리됨)
    if (currentSessionId !== sessionId) {
      navigate(`/spotlight/${sessionId}`);
    }
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await spotlightApi.deleteSession(sessionId);
      removeSession(sessionId);
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  const handleNewSession = async () => {
    abortCurrentStream();
    const session = await createNewSession();
    if (session) {
      navigate(`/spotlight/${session.id}`);
    }
  };

  if (sessionsLoading) {
    return (
      <div className="p-4 text-center text-white/60">
        세션 로딩 중...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {/* 새 세션 버튼 */}
      <button
        onClick={handleNewSession}
        className="glass-card-hover flex items-center gap-3 p-3 rounded-lg transition-all"
      >
        <div className="icon-container-sm bg-mit-primary/20">
          <Plus className="w-4 h-4 text-mit-primary" />
        </div>
        <span className="text-sm text-white">새 대화 시작</span>
      </button>

      {/* 세션 목록 */}
      {sessions.length === 0 ? (
        <div className="p-4 text-center text-white/40 text-sm">
          대화 기록이 없습니다
        </div>
      ) : (
        <div className="space-y-1">
          {sessions.map((session) => (
            <div
              key={session.id}
              onClick={() => handleSessionClick(session.id)}
              className={cn(
                'group flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all',
                currentSessionId === session.id
                  ? 'bg-white/10 border border-white/20'
                  : 'glass-card-hover'
              )}
            >
              <div className="icon-container-sm">
                <MessageSquare className="w-4 h-4 text-white/60" />
              </div>

              {/* 새 응답 표시 (초록색 점) */}
              {sessionsWithNewResponse.has(session.id) && (
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              )}

              <div className="flex-1 min-w-0">
                <p className="text-sm text-white truncate">{session.title}</p>
                <p className="text-xs text-white/40">
                  {formatRelativeTime(new Date(session.updated_at))}
                  {session.message_count > 0 && ` · ${session.message_count}개 메시지`}
                </p>
              </div>

              <button
                onClick={(e) => handleDeleteSession(e, session.id)}
                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-white/10 rounded transition-all"
              >
                <Trash2 className="w-4 h-4 text-white/40 hover:text-mit-warning" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
