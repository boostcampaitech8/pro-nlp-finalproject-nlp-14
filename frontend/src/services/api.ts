import axios from 'axios';

// 환경변수에서 API URL 가져오기 (기본값: 상대 경로)
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 요청 인터셉터: access token 추가
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  console.log('[api] Request:', config.method?.toUpperCase(), config.url, 'token:', token ? 'exists' : 'null');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 응답 인터셉터: 토큰 만료 시 갱신 시도
api.interceptors.response.use(
  (response) => {
    console.log('[api] Response:', response.status, response.config.url);
    return response;
  },
  async (error) => {
    console.log('[api] Error:', error.response?.status, error.config?.url, error.message);
    const originalRequest = error.config;

    // 401 에러이고 재시도하지 않은 경우
    if (error.response?.status === 401 && !originalRequest._retry) {
      console.log('[api] 401 received, attempting token refresh...');
      originalRequest._retry = true;

      const refreshToken = localStorage.getItem('refreshToken');
      console.log('[api] refreshToken exists:', !!refreshToken);
      if (refreshToken) {
        try {
          console.log('[api] Calling /auth/refresh...');
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refreshToken,
          });
          console.log('[api] Refresh response:', response.data);

          // 백엔드에서 camelCase로 반환됨
          const { accessToken, refreshToken: newRefreshToken } = response.data;
          console.log('[api] New accessToken:', accessToken ? 'received' : 'null');
          console.log('[api] New refreshToken:', newRefreshToken ? 'received' : 'null');
          localStorage.setItem('accessToken', accessToken);
          localStorage.setItem('refreshToken', newRefreshToken);

          originalRequest.headers.Authorization = `Bearer ${accessToken}`;
          return api(originalRequest);
        } catch (refreshError) {
          console.error('[api] Refresh failed:', refreshError);
          // 갱신 실패 시 로그아웃
          localStorage.removeItem('accessToken');
          localStorage.removeItem('refreshToken');
          // 커스텀 이벤트를 통해 authStore에 로그아웃 알림
          window.dispatchEvent(new CustomEvent('auth:logout'));
          return Promise.reject(refreshError);
        }
      } else {
        console.log('[api] No refreshToken, dispatching auth:logout');
        // refreshToken이 없으면 토큰 제거
        localStorage.removeItem('accessToken');
        window.dispatchEvent(new CustomEvent('auth:logout'));
      }
    }

    return Promise.reject(error);
  }
);

export default api;
