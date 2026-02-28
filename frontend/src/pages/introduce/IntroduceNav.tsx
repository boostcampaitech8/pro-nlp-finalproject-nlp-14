import { Layers } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/app/components/ui/button';
import { useAuth } from '@/hooks/useAuth';

export function IntroduceNav() {
  const { isAuthenticated } = useAuth();

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl bg-[#0f172a]/70 border-b border-white/5">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="icon-container w-8 h-8 rounded-lg">
            <Layers className="w-4 h-4 text-white" />
          </div>
          <div>
            <span className="text-base font-bold text-white tracking-tight">
              Mit
            </span>
            <span className="hidden sm:inline text-[11px] text-white/40 ml-2">
              Meeting Intelligence
            </span>
          </div>
        </div>

        {/* Auth-dependent buttons */}
        <div className="flex items-center gap-2">
          {isAuthenticated ? (
            <Link to="/">
              <Button variant="glass" size="sm">
                Spotlight으로 돌아가기
              </Button>
            </Link>
          ) : (
            <>
              <Link to="/login">
                <Button variant="glass" size="sm">
                  로그인
                </Button>
              </Link>
              <Link to="/login">
                <Button size="sm" className="bg-gradient-to-r from-mit-primary to-mit-purple hover:from-mit-primary/90 hover:to-mit-purple/90 text-white font-semibold shadow-[0_2px_12px_rgba(99,102,241,0.3)]">
                  무료로 시작하기
                </Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
