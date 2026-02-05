// 네비게이션 컴포넌트
import { useEffect } from 'react';
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
  LogOut,
  MessageSquare,
  Trash2,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTeamStore } from '@/stores/teamStore';
import { useMeetingModalStore } from '@/app/stores/meetingModalStore';
import { useAuth } from '@/hooks/useAuth';
import { useCommandStore } from '@/app/stores/commandStore';
import { spotlightApi } from '@/app/services/spotlightApi';
import { ScrollArea } from '@/app/components/ui';
import { formatRelativeTime } from '@/app/utils/dateUtils';

interface NavItem {
  id: string;
  label: string;
  icon: React.ElementType;
  href: string;
  badge?: string;
}

const mainNavItems: NavItem[] = [
  { id: 'home', label: 'Home', icon: Home, href: '/' },
  { id: 'search', label: 'Search', icon: Search, href: '/search' },
  { id: 'calendar', label: 'Calendar', icon: Calendar, href: '/calendar' },
];

const bottomNavItems: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, href: '/dashboard' },
  { id: 'settings', label: 'Settings', icon: Settings, href: '/settings' },
];

// 섹션 타이틀 컴포넌트
function SectionTitle({ children }: { children: React.ReactNode }) {
  return <p className="text-nav-title px-3 mb-2">{children}</p>;
}

export function Navigation() {
  const location = useLocation();
  const navigate = useNavigate();
  const { teams, fetchTeams, teamsLoading } = useTeamStore();
  const { openModal: openMeetingModal } = useMeetingModalStore();
  const { logout, isLoading: authLoading } = useAuth();
  const {
    sessions,
    sessionsLoading,
    currentSessionId,
    removeSession,
    loadSessions,
    createNewSession,
    abortCurrentStream,
  } = useCommandStore();

  useEffect(() => {
    if (teams.length === 0) {
      fetchTeams();
    }
  }, [teams.length, fetchTeams]);

  // Spotlight 세션 목록 로드
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const renderNavItem = (item: NavItem) => {
    const isActive = location.pathname === item.href;
    const Icon = item.icon;

    return (
      <Link
        key={item.id}
        to={item.href}
        className={cn(
          'nav-item',
          isActive && 'nav-item-active'
        )}
      >
        <Icon className="w-[18px] h-[18px]" />
        <span className="text-[14px]">{item.label}</span>
        {item.badge && (
          <span className="badge-warning ml-auto">{item.badge}</span>
        )}
      </Link>
    );
  };

  const handleNewMeeting = () => {
    openMeetingModal();
  };

  const handleNewSpotlightSession = async () => {
    // 기존 스트림 정리
    abortCurrentStream();
    const session = await createNewSession();
    if (session) {
      // URL 기반 라우팅 - MainPage의 useEffect가 세션 로드 처리
      navigate(`/spotlight/${session.id}`);
    }
  };

  const handleSpotlightSessionClick = (sessionId: string) => {
    // 기존 스트림 정리 후 URL 이동
    // URL 변경 시 MainPage의 useEffect가 세션 전환 처리
    abortCurrentStream();
    navigate(`/spotlight/${sessionId}`);
  };

  const handleDeleteSpotlightSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await spotlightApi.deleteSession(sessionId);
      removeSession(sessionId);
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* 메인 네비게이션 */}
      <div className="space-y-1">
        <SectionTitle>Main</SectionTitle>
        {mainNavItems.map(renderNavItem)}
      </div>

      {/* 팀 섹션 */}
      <div className="mt-6 flex-1 min-h-0 flex flex-col">
        <div className="flex items-center justify-between px-3 mb-2">
          <p className="text-nav-title">Teams</p>
          <button
            onClick={handleNewMeeting}
            className="w-5 h-5 rounded flex items-center justify-center text-white/40 hover:text-white/70 hover:bg-white/5 transition-colors"
            title="새 회의 시작"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>

        <ScrollArea className="flex-1">
          <div className="space-y-0.5 pr-2">
            {teamsLoading && teams.length === 0 ? (
              <div className="px-3 py-2 text-white/30 text-sm">
                Loading...
              </div>
            ) : teams.length === 0 ? (
              <Link
                to="/dashboard"
                className="px-3 py-2 text-white/50 text-sm hover:text-white/70 block"
              >
                Create your first team
              </Link>
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
                        : 'text-white/60 hover:text-white/90 hover:bg-white/5'
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
        </ScrollArea>
      </div>

      {/* Spotlight 세션 섹션 */}
      <div className="mt-4 pt-4 border-t border-white/5">
        <div className="flex items-center justify-between px-3 mb-2">
          <div className="flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 text-mit-primary" />
            <p className="text-nav-title">Spotlight</p>
          </div>
          <button
            onClick={handleNewSpotlightSession}
            className="w-5 h-5 rounded flex items-center justify-center text-white/40 hover:text-white/70 hover:bg-white/5 transition-colors"
            title="새 대화 시작"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="space-y-0.5">
          {sessionsLoading ? (
            <div className="px-3 py-2 text-white/30 text-sm">Loading...</div>
          ) : sessions.length === 0 ? (
            <button
              onClick={handleNewSpotlightSession}
              className="w-full px-3 py-2 text-white/50 text-sm hover:text-white/70 text-left"
            >
              새 대화 시작하기
            </button>
          ) : (
            sessions.slice(0, 5).map((session) => (
              <div
                key={session.id}
                onClick={() => handleSpotlightSessionClick(session.id)}
                className={cn(
                  'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors cursor-pointer group',
                  currentSessionId === session.id
                    ? 'bg-white/10 text-white'
                    : 'text-white/60 hover:text-white/90 hover:bg-white/5'
                )}
              >
                <MessageSquare className="w-4 h-4 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="truncate block">{session.title}</span>
                  <span className="text-[10px] text-white/40">
                    {formatRelativeTime(new Date(session.updated_at))}
                  </span>
                </div>
                <button
                  onClick={(e) => handleDeleteSpotlightSession(e, session.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 hover:bg-white/10 rounded transition-all"
                >
                  <Trash2 className="w-3 h-3 text-white/40 hover:text-red-400" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 하단 네비게이션 */}
      <div className="mt-4 space-y-1 pt-4 border-t border-white/5">
        <SectionTitle>System</SectionTitle>
        {bottomNavItems.map(renderNavItem)}
      </div>

      {/* 로그아웃 버튼 */}
      <div className="mt-4 pt-4 border-t border-white/5">
        <button
          onClick={logout}
          disabled={authLoading}
          className={cn(
            'nav-item w-full',
            authLoading && 'opacity-50 cursor-not-allowed'
          )}
        >
          <LogOut className="w-[18px] h-[18px]" />
          <span className="text-[14px]">Logout</span>
        </button>
      </div>
    </div>
  );
}
