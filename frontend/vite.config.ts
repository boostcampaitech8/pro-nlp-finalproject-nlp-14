import react from '@vitejs/plugin-react';
import path from 'path';
import { readFileSync } from 'fs';
import { defineConfig, Plugin } from 'vite';

/**
 * VAD 정적 파일 서빙 플러그인
 * Vite 개발 서버가 .mjs 파일을 ESM 변환하지 않고 그대로 서빙하도록 함
 */
function vadStaticPlugin(): Plugin {
  return {
    name: 'vad-static',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url || '';
        // /vad/*.mjs 요청을 정적 파일로 서빙 (Vite 모듈 변환 우회)
        if (url.startsWith('/vad/') && url.includes('.mjs')) {
          const cleanPath = url.split('?')[0];
          const filePath = path.join(__dirname, 'public', cleanPath);
          try {
            const content = readFileSync(filePath, 'utf-8');
            res.setHeader('Content-Type', 'application/javascript');
            res.setHeader('Cache-Control', 'public, max-age=31536000');
            res.end(content);
            return;
          } catch {
            // 파일이 없으면 다음 미들웨어로
          }
        }
        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), vadStaticPlugin()],
  envDir: '..',  // 루트의 .env 사용
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    // @ricky0123/vad-web 내부의 CJS require(onnxruntime-web/wasm)를 사전 번들링
    include: ['onnxruntime-web/wasm'],
  },
  assetsInclude: ['**/*.onnx', '**/*.wasm'],
});
