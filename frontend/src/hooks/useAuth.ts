import { useEffect, useRef } from 'react';

import { useAuthStore } from '@/stores/authStore';

export function useAuth() {
  const store = useAuthStore();
  const isCheckingRef = useRef(false);

  console.log('[useAuth] isAuthenticated:', store.isAuthenticated, 'user:', store.user?.email || 'null', 'isLoading:', store.isLoading);

  useEffect(() => {
    // 컴포넌트 마운트 시 인증 상태 확인
    console.log('[useAuth] useEffect - isAuthenticated:', store.isAuthenticated, 'user:', store.user?.email || 'null', 'isChecking:', isCheckingRef.current);

    // 이미 체크 중이면 무시
    if (isCheckingRef.current) {
      console.log('[useAuth] Already checking, skipping...');
      return;
    }

    if (store.isAuthenticated && !store.user) {
      console.log('[useAuth] Calling checkAuth...');
      isCheckingRef.current = true;
      store.checkAuth().finally(() => {
        isCheckingRef.current = false;
        console.log('[useAuth] checkAuth completed');
      });
    }
  }, [store.isAuthenticated, store.user, store.checkAuth]);

  return store;
}
