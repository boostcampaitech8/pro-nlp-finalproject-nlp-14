import type { ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';

import { useAuth } from '@/hooks/useAuth';
import { HomePage } from '@/pages/HomePage';
import { LoginPage } from '@/pages/LoginPage';
import { MeetingDetailPage } from '@/pages/MeetingDetailPage';
import MeetingRoomPage from '@/pages/MeetingRoomPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { TeamDetailPage } from '@/pages/TeamDetailPage';

// 인증된 사용자만 접근 가능
function PrivateRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  console.log('[PrivateRoute] path:', location.pathname, 'isAuthenticated:', isAuthenticated);

  if (!isAuthenticated) {
    console.log('[PrivateRoute] Redirecting to /login');
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <HomePage />
          </PrivateRoute>
        }
      />
      <Route
        path="/teams/:teamId"
        element={
          <PrivateRoute>
            <TeamDetailPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/meetings/:meetingId"
        element={
          <PrivateRoute>
            <MeetingDetailPage />
          </PrivateRoute>
        }
      />
      <Route
        path="/meetings/:meetingId/room"
        element={
          <PrivateRoute>
            <MeetingRoomPage />
          </PrivateRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
