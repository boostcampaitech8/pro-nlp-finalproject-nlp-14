import type { ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { useAuth } from '@/hooks/useAuth';
import { MainLayout } from '@/app/layouts/MainLayout';
import { MainPage } from '@/app/pages/MainPage';
import { HomePage } from '@/dashboard/pages/HomePage';
import { GoogleCallbackPage } from '@/pages/GoogleCallbackPage';
import { LoginPage } from '@/pages/LoginPage';
import { NaverCallbackPage } from '@/pages/NaverCallbackPage';
import { MeetingDetailPage } from '@/dashboard/pages/MeetingDetailPage';
import MeetingRoomPage from '@/dashboard/pages/MeetingRoomPage';
import { PRReviewPage } from '@/dashboard/pages/PRReviewPage';
import { TeamDetailPage } from '@/dashboard/pages/TeamDetailPage';
import logger from '@/utils/logger';

// 인증된 사용자만 접근 가능
function PrivateRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  logger.log('[PrivateRoute] path:', location.pathname, 'isAuthenticated:', isAuthenticated);

  if (!isAuthenticated) {
    logger.log('[PrivateRoute] Redirecting to /login');
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <Routes>
      {/* 인증 페이지 */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/naver/callback" element={<NaverCallbackPage />} />
      <Route path="/auth/google/callback" element={<GoogleCallbackPage />} />

      {/* 새 서비스 페이지 (Spotlight UI) - MainLayout 사용 */}
      <Route
        path="/"
        element={
          <PrivateRoute>
            <MainLayout />
          </PrivateRoute>
        }
      >
        <Route index element={<MainPage />} />
      </Route>

      {/* 기존 Dashboard 페이지 */}
      <Route
        path="/dashboard"
        element={
          <PrivateRoute>
            <HomePage />
          </PrivateRoute>
        }
      />
      <Route
        path="/dashboard/teams/:teamId"
        element={
          <PrivateRoute>
            <TeamDetailPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/dashboard/meetings/:meetingId"
        element={
          <PrivateRoute>
            <MeetingDetailPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/dashboard/meetings/:meetingId/room"
        element={
          <PrivateRoute>
            <MeetingRoomPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/dashboard/meetings/:meetingId/review"
        element={
          <PrivateRoute>
            <PRReviewPage />
          </PrivateRoute>
        }
      />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
