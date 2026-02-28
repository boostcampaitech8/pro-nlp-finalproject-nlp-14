import { useEffect, useRef } from 'react';

import { useAuthStore } from '@/stores/authStore';
import logger from '@/utils/logger';

export function useAuth() {
  const store = useAuthStore();
  const isCheckingRef = useRef(false);

  logger.log('[useAuth] isAuthenticated:', store.isAuthenticated, 'user:', store.user?.email || 'null', 'isLoading:', store.isLoading);

  useEffect(() => {
    // 컴포넌트 마운트 시 인증 상태 확인
    logger.log('[useAuth] useEffect - isAuthenticated:', store.isAuthenticated, 'user:', store.user?.email || 'null', 'isChecking:', isCheckingRef.current);

    // 이미 체크 중이면 무시
    if (isCheckingRef.current) {
      logger.log('[useAuth] Already checking, skipping...');
      return;
    }

    if (store.isAuthenticated && !store.user) {
      logger.log('[useAuth] Calling checkAuth...');
      isCheckingRef.current = true;
      store.checkAuth().finally(() => {
        isCheckingRef.current = false;
        logger.log('[useAuth] checkAuth completed');
      });
    }
  }, [store.isAuthenticated, store.user, store.checkAuth]);

  return store;
}
