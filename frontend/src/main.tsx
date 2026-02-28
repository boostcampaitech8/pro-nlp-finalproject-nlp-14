import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import App from './App';
import './index.css';
import logger from '@/utils/logger';
import { analyticsService } from '@/services/analyticsService';

logger.log('[main.tsx] App starting...');

// 사용자 활동 로그 수집 시작
analyticsService.init();
logger.log('[main.tsx] localStorage accessToken:', localStorage.getItem('accessToken') ? 'exists' : 'null');
logger.log('[main.tsx] localStorage refreshToken:', localStorage.getItem('refreshToken') ? 'exists' : 'null');

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);

