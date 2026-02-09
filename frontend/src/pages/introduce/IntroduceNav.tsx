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

        {/* Auth-dependent button */}
        <Link to={isAuthenticated ? '/' : '/login'}>
          <Button variant="glass" size="sm">
            {isAuthenticated ? 'Spotlight으로 돌아가기' : '로그인'}
          </Button>
        </Link>
      </div>
    </nav>
  );
}
