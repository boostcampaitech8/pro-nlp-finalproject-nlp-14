import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '@/hooks/useAuth';
import { useAuthStore } from '@/stores/authStore';
import logger from '@/utils/logger';

export function LoginPage() {
  logger.log('[LoginPage] Rendering...');
  const { isAuthenticated } = useAuth();
  const { loginWithNaver, loginWithGoogle, isLoading, error, clearError } = useAuthStore();
  const navigate = useNavigate();
  logger.log('[LoginPage] isAuthenticated:', isAuthenticated);

  useEffect(() => {
    logger.log('[LoginPage] useEffect - isAuthenticated:', isAuthenticated);
    if (isAuthenticated) {
      logger.log('[LoginPage] Already authenticated, navigating to /');
      navigate('/');
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    // 에러 메시지 초기화
    return () => clearError();
  }, [clearError]);

  const handleNaverLogin = async () => {
    try {
      await loginWithNaver();
    } catch {
      // 에러는 store에서 처리됨
    }
  };

  const handleGoogleLogin = async () => {
    try {
      await loginWithGoogle();
    } catch {
      // 에러는 store에서 처리됨
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Mit</h1>
          <p className="mt-2 text-gray-600">
            조직 회의의 진실을 관리하는 협업 시스템
          </p>
        </div>

        <div className="bg-white p-8 rounded-xl shadow-md">
          <h2 className="text-xl font-semibold text-center mb-6">로그인</h2>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          <div className="space-y-3">
            <button
              onClick={handleGoogleLogin}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white hover:bg-gray-50 text-gray-700 font-medium rounded-lg border border-gray-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <span>로그인 중...</span>
              ) : (
                <>
                  <GoogleIcon />
                  <span>Google로 로그인</span>
                </>
              )}
            </button>

            <button
              onClick={handleNaverLogin}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-[#03C75A] hover:bg-[#02b350] text-white font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <span>로그인 중...</span>
              ) : (
                <>
                  <NaverIcon />
                  <span>네이버로 로그인</span>
                </>
              )}
            </button>
          </div>

          <p className="mt-6 text-center text-sm text-gray-500">
            소셜 계정으로 간편하게 로그인하세요
          </p>
        </div>
      </div>
    </div>
  );
}

// 네이버 로고 아이콘
function NaverIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M13.5 10.5L6.5 2H2V18H6.5V9.5L13.5 18H18V2H13.5V10.5Z"
        fill="white"
      />
    </svg>
  );
}

// Google 로고 아이콘
function GoogleIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}
