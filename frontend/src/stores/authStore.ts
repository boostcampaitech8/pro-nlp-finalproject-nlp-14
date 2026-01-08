import type { ErrorResponse, LoginRequest, RegisterRequest, User } from '@/types';
import axios from 'axios';
import { create } from 'zustand';

import { authService } from '@/services/authService';
import logger from '@/utils/logger';

// API 에러에서 사용자 친화적 메시지 추출
function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error) && error.response?.data) {
    const data = error.response.data;
    // FastAPI HTTPException 형태: { detail: { error, message } }
    if (data.detail?.message) {
      return data.detail.message;
    }
    // 일반 ErrorResponse 형태: { error, message }
    if ((data as ErrorResponse).message) {
      return (data as ErrorResponse).message;
    }
  }
  return fallback;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // 액션
  register: (data: RegisterRequest) => Promise<void>;
  login: (data: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => {
  logger.log('[authStore] Initializing store...');

  // 토큰 갱신 실패 시 자동 로그아웃 처리
  if (typeof window !== 'undefined') {
    window.addEventListener('auth:logout', () => {
      logger.log('[authStore] auth:logout event received');
      set({ user: null, isAuthenticated: false });
    });
  }

  const hasAccessToken = !!localStorage.getItem('accessToken');
  logger.log('[authStore] Initial isAuthenticated:', hasAccessToken);

  return {
    user: null,
    isAuthenticated: hasAccessToken,
    isLoading: false,
    error: null,

  register: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const response = await authService.register(data);
      localStorage.setItem('accessToken', response.tokens.accessToken);
      localStorage.setItem('refreshToken', response.tokens.refreshToken);
      set({ user: response.user, isAuthenticated: true, isLoading: false });
    } catch (error) {
      const message = getErrorMessage(error, 'Registration failed');
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  login: async (data) => {
    set({ isLoading: true, error: null });
    try {
      const response = await authService.login(data);
      localStorage.setItem('accessToken', response.tokens.accessToken);
      localStorage.setItem('refreshToken', response.tokens.refreshToken);
      set({ user: response.user, isAuthenticated: true, isLoading: false });
    } catch (error) {
      const message = getErrorMessage(error, 'Login failed');
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  logout: async () => {
    try {
      await authService.logout();
    } catch {
      // 서버 에러 무시
    } finally {
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      set({ user: null, isAuthenticated: false });
    }
  },

  checkAuth: async () => {
    logger.log('[authStore] checkAuth called');
    const token = localStorage.getItem('accessToken');
    logger.log('[authStore] accessToken exists:', !!token);
    if (!token) {
      logger.log('[authStore] No token, setting isAuthenticated: false');
      set({ isAuthenticated: false, user: null });
      return;
    }

    set({ isLoading: true });
    try {
      logger.log('[authStore] Fetching current user...');
      const user = await authService.getCurrentUser();
      logger.log('[authStore] User fetched successfully:', user?.email);
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (error) {
      logger.error('[authStore] checkAuth error:', error);
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  clearError: () => set({ error: null }),
}});
