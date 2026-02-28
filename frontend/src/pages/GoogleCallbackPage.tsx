import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { useAuthStore } from '@/stores/authStore';
import logger from '@/utils/logger';

export function GoogleCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { handleGoogleCallback, error } = useAuthStore();
  const [isProcessing, setIsProcessing] = useState(true);

  useEffect(() => {
    const processCallback = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const errorParam = searchParams.get('error');
      const errorDescription = searchParams.get('error_description');

      logger.log('[GoogleCallback] Processing callback...', { code: !!code, state: !!state, error: errorParam });

      // 에러 응답 처리
      if (errorParam) {
        logger.error('[GoogleCallback] OAuth error:', errorParam, errorDescription);
        setIsProcessing(false);
        navigate('/login', {
          state: { error: errorDescription || 'Login was cancelled or failed' },
        });
        return;
      }

      // 필수 파라미터 확인
      if (!code || !state) {
        logger.error('[GoogleCallback] Missing code or state');
        setIsProcessing(false);
        navigate('/login', {
          state: { error: 'Invalid callback parameters' },
        });
        return;
      }

      try {
        await handleGoogleCallback(code, state);
        logger.log('[GoogleCallback] Login successful');
        const pendingInviteCode = sessionStorage.getItem('pendingInviteCode');
        if (pendingInviteCode) {
          sessionStorage.removeItem('pendingInviteCode');
          logger.log('[GoogleCallback] Redirecting to invite page:', pendingInviteCode);
          navigate(`/invite/${pendingInviteCode}`, { replace: true });
        } else {
          navigate('/', { replace: true });
        }
      } catch (err) {
        logger.error('[GoogleCallback] Login failed:', err);
        setIsProcessing(false);
        navigate('/login', { replace: true });
      }
    };

    processCallback();
  }, [searchParams, handleGoogleCallback, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        {isProcessing ? (
          <>
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#4285F4] mx-auto mb-4" />
            <p className="text-gray-600">Google 로그인 처리 중...</p>
          </>
        ) : error ? (
          <>
            <div className="text-red-500 text-5xl mb-4">!</div>
            <p className="text-gray-900 font-medium mb-2">로그인 실패</p>
            <p className="text-gray-600 text-sm">{error}</p>
          </>
        ) : null}
      </div>
    </div>
  );
}
