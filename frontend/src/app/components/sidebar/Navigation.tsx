// 네비게이션 컴포넌트
import { useEffect, useState, useCallback } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Home,
  Search,
  Calendar,
  Settings,
  LayoutDashboard,
  Users,
  Plus,
  ChevronRight,
  ChevronDown,
  LogOut,
  MessageSquare,
  Video,
  X,
  Info,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTeamStore } from '@/stores/teamStore';
import { useCommandStore } from '@/app/stores/commandStore';
import { spotlightApi } from '@/app/services/spotlightApi';
import { useCreateTeamModalStore } from '@/app/stores/createTeamModalStore';
import { useAuth } from '@/hooks/useAuth';
import { useSidebarMeetings } from '@/app/hooks/useSidebarMeetings';

// ─── 공통: 폴드 섹션 ────────────────────────────────────────

const STORAGE_PREFIX = 'mit-sidebar-';

interface CollapsibleSectionProps {
  id: string;
  title: string;
  count?: number;
  /** 펼쳤을 때 콘텐츠가 flex 공간을 나눠 쓰며 내부 스크롤 */
  scrollable?: boolean;
  /** 헤더 우측 액션 (+ 버튼 등) */
  action?: React.ReactNode;
  children: React.ReactNode;
}

function CollapsibleSection({
  id,
  title,
  count,
  scrollable = false,
  action,
  children,
}: CollapsibleSectionProps) {
  const foldKey = `${STORAGE_PREFIX}${id}-folded`;
  const [folded, setFolded] = useState(() => localStorage.getItem(foldKey) === 'true');

  const toggleFold = useCallback(() => {
    setFolded((prev) => {
      localStorage.setItem(foldKey, String(!prev));
      return !prev;
    });
  }, [foldKey]);

  return (
    <div
      className={cn(
        'flex flex-col',
        !folded && scrollable ? 'flex-1 min-h-0' : 'flex-shrink-0',
      )}
    >
      {/* 섹션 헤더 — 항상 보임 */}
      <div className="flex-shrink-0 flex items-center border-b border-white/[0.06] bg-white/[0.03] mt-1">
        <button
          onClick={toggleFold}
          className="flex items-center gap-1.5 flex-1 min-w-0 px-3 py-1.5 group"
        >
          <ChevronDown
            className={cn(
              'w-3 h-3 text-white/25 group-hover:text-white/50 transition-all duration-200',
              folded && '-rotate-90',
            )}
          />
          <span className="text-[11px] font-medium uppercase tracking-wider text-white/40 group-hover:text-white/60 transition-colors">
            {title}
          </span>
          {count !== undefined && count > 0 && (
            <span className="text-[10px] text-white/25 tabular-nums ml-auto">{count}</span>
          )}
        </button>
        {action && (
          <div className="pr-3 flex-shrink-0">{action}</div>
        )}
      </div>

      {/* 콘텐츠 */}
      {!folded && (
        scrollable ? (
          <div className="flex-1 min-h-0 overflow-y-auto sidebar-scrollbar mt-1 px-2">
            {children}
          </div>
        ) : (
          <div className="mt-1 px-2">{children}</div>
        )
      )}
    </div>
  );
}

// ─── 네비 아이템 ────────────────────────────────────────────

interface NavItem {
  id: string;
  label: string;
  icon: React.ElementType;
  href: string;
  badge?: string;
}

const mainNavItems: NavItem[] = [
  { id: 'introduce', label: '서비스 소개', icon: Info, href: '/introduce' },
  { id: 'home', label: '홈', icon: Home, href: '/' },
  { id: 'search', label: '검색', icon: Search, href: '/search' },
  { id: 'calendar', label: '캘린더', icon: Calendar, href: '/calendar' },
];

const bottomNavItems: NavItem[] = [
  { id: 'dashboard', label: '대시보드', icon: LayoutDashboard, href: '/dashboard' },
  { id: 'settings', label: '설정', icon: Settings, href: '/settings' },
];

// ─── Navigation 본체 ────────────────────────────────────────

export function Navigation() {
  const location = useLocation();
  const navigate = useNavigate();
  const { teams, fetchTeams, teamsLoading } = useTeamStore();
  const { openModal: openCreateTeamModal } = useCreateTeamModalStore();
  const { logout, isLoading: authLoading, isAuthenticated } = useAuth();
  const {
    sessions,
    sessionsLoading,
    currentSessionId,
    sessionsWithNewResponse,
    loadSessions,
    createNewSession,
    removeSession,
  } = useCommandStore();
  const { meetings: sidebarMeetings, isLoading: meetingsLoading } = useSidebarMeetings(teams);

  useEffect(() => {
    if (teams.length === 0) {
      fetchTeams();
    }
  }, [teams.length, fetchTeams]);

  useEffect(() => {
    if (isAuthenticated) {
      loadSessions();
    }
  }, [isAuthenticated, loadSessions]);

  const handleNewSession = async () => {
    const session = await createNewSession();
    if (session) {
      navigate(`/spotlight/${session.id}`);
    }
  };

  const handleSessionClick = (sessionId: string) => {
    if (currentSessionId !== sessionId) {
      navigate(`/spotlight/${sessionId}`);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await spotlightApi.deleteSession(sessionId);
      removeSession(sessionId);
      // 삭제된 세션을 보고 있었다면 홈으로 이동
      if (currentSessionId === sessionId) {
        navigate('/');
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  const renderNavItem = (item: NavItem) => {
    const isActive = location.pathname === item.href;
    const Icon = item.icon;

    return (
      <Link
        key={item.id}
        to={item.href}
        className={cn('nav-item', isActive && 'nav-item-active')}
      >
        <Icon className="w-[18px] h-[18px]" />
        <span className="text-[14px]">{item.label}</span>
        {item.badge && <span className="badge-warning ml-auto">{item.badge}</span>}
      </Link>
    );
  };

  // 액션 버튼 헬퍼
  const plusButton = (onClick: () => void, disabled = false, titleText?: string) => (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      disabled={disabled}
      className={cn(
        'w-5 h-5 rounded flex items-center justify-center transition-all',
        disabled
          ? 'text-white/15 cursor-not-allowed'
          : 'text-white/40 hover:text-mit-primary hover:bg-mit-primary/10',
      )}
      title={titleText}
    >
      <Plus className="w-3 h-3" />
    </button>
  );

  return (
    <div className="flex flex-col h-full overflow-hidden" role="navigation" aria-label="메인 네비게이션">
      {/* ── Main (상단 고정, 폴드 없음) ── */}
      <div className="flex-shrink-0">
        <div className="space-y-0.5 py-1 px-2">{mainNavItems.map(renderNavItem)}</div>
      </div>

      {/* ── 중간 섹션 (각 섹션이 자체 스크롤 처리) ── */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
      {/* ── Teams ── */}
      <CollapsibleSection
        id="teams"
        title="팀"
        count={teams.length}
        scrollable
        action={teams.length > 0 ? plusButton(openCreateTeamModal, false, '새 팀 만들기') : undefined}
      >
        <div className="space-y-0.5">
          {teamsLoading && teams.length === 0 ? (
            <div className="px-3 py-2 text-white/30 text-sm">불러오는 중...</div>
          ) : teams.length === 0 ? (
            <button
              onClick={openCreateTeamModal}
              className="mx-2 w-[calc(100%-16px)] flex items-center gap-2.5 px-3 py-2.5 rounded-lg bg-gradient-to-r from-mit-primary/15 to-mit-purple/15 hover:from-mit-primary/25 hover:to-mit-purple/25 border border-mit-primary/20 hover:border-mit-primary/35 text-white/80 hover:text-white transition-all group"
            >
              <Plus className="w-4 h-4 text-mit-primary/60 group-hover:text-mit-primary transition-colors" />
              <p className="text-sm">첫 팀을 만들어보세요</p>
            </button>
          ) : (
            teams.map((team) => {
              const isActive = location.pathname === `/dashboard/teams/${team.id}`;
              return (
                <Link
                  key={team.id}
                  to={`/dashboard/teams/${team.id}`}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors group',
                    isActive
                      ? 'bg-white/10 text-white'
                      : 'text-white/60 hover:text-white/90 hover:bg-white/5',
                  )}
                >
                  <Users className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate flex-1">{team.name}</span>
                  <ChevronRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-50 transition-opacity" />
                </Link>
              );
            })
          )}
        </div>
      </CollapsibleSection>

      {/* ── Meetings ── */}
      <CollapsibleSection
        id="meetings"
        title="회의"
        count={sidebarMeetings.length}
        scrollable
      >
        <div className="space-y-0.5">
          {meetingsLoading ? (
            <div className="space-y-1 px-3">
              {[1, 2].map((i) => (
                <div key={i} className="h-12 bg-white/5 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : sidebarMeetings.length === 0 ? (
            <p className="px-3 py-2 text-white/30 text-xs">
              예정된 회의가 없어요
            </p>
          ) : (
            sidebarMeetings.map((meeting) => {
                const isOngoing = meeting.status === 'ongoing';
                const meetingPath = isOngoing
                  ? `/dashboard/meetings/${meeting.id}/room`
                  : `/dashboard/meetings/${meeting.id}`;
                const isActive =
                  location.pathname === `/dashboard/meetings/${meeting.id}` ||
                  location.pathname === `/dashboard/meetings/${meeting.id}/room`;

                return (
                  <Link
                    key={meeting.id}
                    to={meetingPath}
                    className={cn(
                      'flex items-start gap-2 px-3 py-2 rounded-lg text-sm transition-colors group',
                      isActive
                        ? 'bg-white/10 text-white'
                        : 'text-white/60 hover:text-white/90 hover:bg-white/5',
                    )}
                  >
                    <div className="mt-0.5 flex-shrink-0">
                      {isOngoing ? (
                        <span className="relative w-4 h-4 flex items-center justify-center">
                          <span className="absolute w-2.5 h-2.5 rounded-full bg-green-500/30 animate-ping" />
                          <span className="relative w-2 h-2 rounded-full bg-green-500" />
                        </span>
                      ) : (
                        <Video className="w-4 h-4 text-blue-400/70" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className="block truncate">
                        <span className="text-white/40">{meeting.teamName}</span>
                        <span className="text-white/20 mx-1">·</span>
                        {meeting.title}
                      </span>
                      {meeting.description ? (
                        <span className="block text-[11px] text-white/25 truncate">
                          {meeting.description}
                        </span>
                      ) : (
                        <span className="block text-[11px] text-white/20 truncate">
                          {isOngoing ? '진행 중' : '예정됨'}
                        </span>
                      )}
                    </div>
                    <ChevronRight className="w-3.5 h-3.5 mt-1 opacity-0 group-hover:opacity-50 transition-opacity flex-shrink-0" />
                  </Link>
                );
              })
            )}
          </div>
        </CollapsibleSection>

      {/* ── Spotlight ── */}
      <CollapsibleSection
        id="spotlight"
        title="스포트라이트"
        count={sessions.length}
        scrollable
        action={plusButton(handleNewSession, false, '새 대화')}
      >
        <div className="space-y-0.5">
          {sessionsLoading ? (
            <div className="space-y-1 px-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-9 bg-white/5 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : sessions.length === 0 ? (
            <button
              onClick={handleNewSession}
              className="px-3 py-2 text-white/50 text-sm hover:text-white/70 block w-full text-left"
            >
              Mit에게 질문해보세요
            </button>
          ) : (
            sessions.map((session) => {
              const isActive =
                currentSessionId === session.id ||
                location.pathname === `/spotlight/${session.id}`;
              const hasNewResponse = sessionsWithNewResponse.has(session.id);

              return (
                <div
                  key={session.id}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors group/session',
                    isActive
                      ? 'bg-mit-primary/20 border border-mit-primary/30 text-white'
                      : 'text-white/60 hover:text-white/90 hover:bg-white/5',
                  )}
                >
                  <button
                    onClick={() => handleSessionClick(session.id)}
                    className="flex items-center gap-2 flex-1 min-w-0 text-left"
                  >
                    <MessageSquare className="w-4 h-4 flex-shrink-0" />
                    <span className="truncate flex-1">{session.title}</span>
                  </button>
                  {hasNewResponse && (
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse flex-shrink-0" />
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteSession(session.id);
                    }}
                    className="w-4 h-4 flex items-center justify-center flex-shrink-0 opacity-0 group-hover/session:opacity-100 text-white/30 hover:text-red-400 transition-all"
                    title="대화 삭제"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </CollapsibleSection>

      {/* ── System ── */}
      <CollapsibleSection id="system" title="시스템">
        <div className="space-y-0.5">{bottomNavItems.map(renderNavItem)}</div>
      </CollapsibleSection>
      </div>{/* end 중간 섹션 */}

      {/* 로그아웃 — 하단 고정 */}
      <div className="flex-shrink-0 mt-auto pt-2 pb-1 px-2 border-t border-white/5">
        <button
          onClick={logout}
          disabled={authLoading}
          className={cn('nav-item w-full', authLoading && 'opacity-50 cursor-not-allowed')}
        >
          <LogOut className="w-[18px] h-[18px]" />
          <span className="text-[14px]">로그아웃</span>
        </button>
      </div>
    </div>
  );
}
