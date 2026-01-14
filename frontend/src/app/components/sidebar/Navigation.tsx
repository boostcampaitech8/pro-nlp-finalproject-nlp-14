// 네비게이션 컴포넌트
import { Link, useLocation } from 'react-router-dom';
import {
  Home,
  FolderOpen,
  FileText,
  Calendar,
  Settings,
  LayoutDashboard,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface NavItem {
  id: string;
  label: string;
  icon: React.ElementType;
  href: string;
  badge?: string;
}

const mainNavItems: NavItem[] = [
  { id: 'home', label: 'Home', icon: Home, href: '/' },
  { id: 'projects', label: 'Projects', icon: FolderOpen, href: '/projects' },
  { id: 'documents', label: 'Documents', icon: FileText, href: '/documents' },
  { id: 'calendar', label: 'Calendar', icon: Calendar, href: '/calendar' },
];

const bottomNavItems: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, href: '/dashboard' },
  { id: 'settings', label: 'Settings', icon: Settings, href: '/settings' },
];

export function Navigation() {
  const location = useLocation();

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

  return (
    <div className="flex flex-col h-full">
      {/* 메인 네비게이션 */}
      <div className="space-y-1">
        <p className="text-nav-title px-3 mb-2">Main</p>
        {mainNavItems.map(renderNavItem)}
      </div>

      {/* 하단 네비게이션 */}
      <div className="mt-auto space-y-1">
        <p className="text-nav-title px-3 mb-2">System</p>
        {bottomNavItems.map(renderNavItem)}
      </div>
    </div>
  );
}
