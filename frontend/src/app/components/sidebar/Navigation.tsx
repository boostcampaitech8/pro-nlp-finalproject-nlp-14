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
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTeamStore } from '@/stores/teamStore';
import { useCommandStore } from '@/app/stores/commandStore';
import { useMeetingModalStore } from '@/app/stores/meetingModalStore';
import { useCreateTeamModalStore } from '@/app/stores/createTeamModalStore';
import { useAuth } from '@/hooks/useAuth';
import { ScrollArea } from '@/app/components/ui';
import { MAX_SPOTLIGHT_SESSIONS } from '@/app/constants';

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
  const { openModal: openCreateTeamModal } = useCreateTeamModalStore();
  const { logout, isLoading: authLoading, isAuthenticated } = useAuth();
  const {
    sessions,
    sessionsLoading,
    currentSessionId,
    sessionsWithNewResponse,
    loadSessions,
    createNewSession,
  } = useCommandStore();

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
    if (sessions.length >= MAX_SPOTLIGHT_SESSIONS) return;
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
    if (teams.length > 0) {
      openMeetingModal();
    } else {
      openCreateTeamModal();
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
            title={teams.length > 0 ? "새 회의 시작" : "새 팀 만들기"}
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
          <p className="text-nav-title">Spotlight</p>
          <button
            onClick={handleNewSession}
            disabled={sessions.length >= MAX_SPOTLIGHT_SESSIONS}
            className={cn(
              'w-5 h-5 rounded flex items-center justify-center transition-colors',
              sessions.length >= MAX_SPOTLIGHT_SESSIONS
                ? 'text-white/20 cursor-not-allowed'
                : 'text-white/40 hover:text-white/70 hover:bg-white/5'
            )}
            title={sessions.length >= MAX_SPOTLIGHT_SESSIONS ? `최대 ${MAX_SPOTLIGHT_SESSIONS}개 세션` : '새 대화'}
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>

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
              새 대화를 시작하세요
            </button>
          ) : (
            sessions.map((session) => {
              const isActive = currentSessionId === session.id ||
                location.pathname === `/spotlight/${session.id}`;
              const hasNewResponse = sessionsWithNewResponse.has(session.id);

              return (
                <button
                  key={session.id}
                  onClick={() => handleSessionClick(session.id)}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors w-full text-left',
                    isActive
                      ? 'bg-mit-primary/20 border border-mit-primary/30 text-white'
                      : 'text-white/60 hover:text-white/90 hover:bg-white/5'
                  )}
                >
                  <MessageSquare className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate flex-1">{session.title}</span>
                  {hasNewResponse && (
                    <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse flex-shrink-0" />
                  )}
                </button>
              );
            })
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
