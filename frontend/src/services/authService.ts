import type { AuthResponse, User } from '@/types';
import api from './api';

interface NaverLoginUrlResponse {
  url: string;
}

interface GoogleLoginUrlResponse {
  url: string;
}

export const authService = {
  // 네이버 OAuth 로그인 URL 가져오기
  async getNaverLoginUrl(): Promise<string> {
    const response = await api.get<NaverLoginUrlResponse>('/auth/naver/login');
    return response.data.url;
  },

  // 네이버 OAuth 콜백 처리
  async naverCallback(code: string, state: string): Promise<AuthResponse> {
    const response = await api.get<AuthResponse>('/auth/naver/callback', {
      params: { code, state },
    });
    return response.data;
  },

  // Google OAuth 로그인 URL 가져오기
  async getGoogleLoginUrl(): Promise<string> {
    const response = await api.get<GoogleLoginUrlResponse>('/auth/google/login');
    return response.data.url;
  },

  // Google OAuth 콜백 처리
  async googleCallback(code: string, state: string): Promise<AuthResponse> {
    const response = await api.get<AuthResponse>('/auth/google/callback', {
      params: { code, state },
    });
    return response.data;
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout');
  },

  async getCurrentUser(): Promise<User> {
    const response = await api.get<User>('/auth/me');
    return response.data;
  },
};
