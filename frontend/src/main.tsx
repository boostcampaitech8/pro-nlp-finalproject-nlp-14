import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import App from './App';
import './index.css';

console.log('[main.tsx] App starting...');
console.log('[main.tsx] localStorage accessToken:', localStorage.getItem('accessToken') ? 'exists' : 'null');
console.log('[main.tsx] localStorage refreshToken:', localStorage.getItem('refreshToken') ? 'exists' : 'null');

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);
