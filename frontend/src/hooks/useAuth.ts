import { useEffect } from 'react';

import { useAuthStore } from '@/stores/authStore';

export function useAuth() {
  const store = useAuthStore();

  useEffect(() => {
    // 컴포넌트 마운트 시 인증 상태 확인
    if (store.isAuthenticated && !store.user) {
      store.checkAuth();
    }
  }, [store.isAuthenticated, store.user, store]);

  return store;
}
