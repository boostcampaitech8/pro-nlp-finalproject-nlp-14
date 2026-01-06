import axios from 'axios';

// 환경변수에서 API URL 가져오기 (기본값: 상대 경로)
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 토큰 갱신 중복 방지를 위한 상태
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

// 갱신 완료 후 대기 중인 요청들에게 새 토큰 전달
function onRefreshed(token: string) {
  refreshSubscribers.forEach((callback) => callback(token));
  refreshSubscribers = [];
}

// 토큰 갱신 대기열에 추가
function addRefreshSubscriber(callback: (token: string) => void) {
  refreshSubscribers.push(callback);
}

/**
 * 토큰 갱신 함수 (외부에서 호출 가능)
 * 회의 중 주기적 갱신에 사용
 */
export async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = localStorage.getItem('refreshToken');
  if (!refreshToken) {
    console.log('[api] No refreshToken available');
    return false;
  }

  // 이미 갱신 중이면 완료될 때까지 대기
  if (isRefreshing) {
    console.log('[api] Token refresh already in progress, waiting...');
    return new Promise((resolve) => {
      addRefreshSubscriber(() => resolve(true));
    });
  }

  isRefreshing = true;
  console.log('[api] Starting token refresh...');

  try {
    const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
      refreshToken,
    });

    const { accessToken, refreshToken: newRefreshToken } = response.data;
    localStorage.setItem('accessToken', accessToken);
    localStorage.setItem('refreshToken', newRefreshToken);

    console.log('[api] Token refreshed successfully');
    onRefreshed(accessToken);
    return true;
  } catch (error) {
    console.error('[api] Token refresh failed:', error);
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    window.dispatchEvent(new CustomEvent('auth:logout'));
    return false;
  } finally {
    isRefreshing = false;
  }
}

/**
 * 토큰 만료 여부 확인 (JWT 디코딩)
 * @param bufferSeconds 만료 전 여유 시간 (초)
 */
export function isTokenExpiringSoon(bufferSeconds: number = 60): boolean {
  const token = localStorage.getItem('accessToken');
  if (!token) return true;

  try {
    // JWT payload 디코딩 (base64)
    const payload = JSON.parse(atob(token.split('.')[1]));
    const exp = payload.exp * 1000; // 밀리초로 변환
    const now = Date.now();
    const buffer = bufferSeconds * 1000;

    return now >= exp - buffer;
  } catch {
    return true;
  }
}

/**
 * 토큰이 곧 만료되면 미리 갱신
 */
export async function ensureValidToken(): Promise<boolean> {
  if (isTokenExpiringSoon(120)) { // 2분 전에 갱신
    console.log('[api] Token expiring soon, refreshing proactively...');
    return await refreshAccessToken();
  }
  return true;
}

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

      // 이미 갱신 중이면 대기
      if (isRefreshing) {
        console.log('[api] Refresh in progress, queueing request...');
        return new Promise((resolve) => {
          addRefreshSubscriber((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(api(originalRequest));
          });
        });
      }

      const refreshToken = localStorage.getItem('refreshToken');
      console.log('[api] refreshToken exists:', !!refreshToken);
      if (refreshToken) {
        isRefreshing = true;
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

          // 대기 중인 요청들에게 새 토큰 전달
          onRefreshed(accessToken);

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
        } finally {
          isRefreshing = false;
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
