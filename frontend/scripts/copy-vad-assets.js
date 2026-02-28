/**
 * VAD 에셋 복사 스크립트
 * @ricky0123/vad-web과 onnxruntime-web의 필수 파일을 public/vad로 복사
 */

import { copyFileSync, mkdirSync, existsSync, readdirSync } from 'fs';
import { dirname, join, resolve } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const frontendDir = resolve(__dirname, '..');
const publicVadDir = join(frontendDir, 'public', 'vad');

// public/vad 디렉토리 생성
if (!existsSync(publicVadDir)) {
  mkdirSync(publicVadDir, { recursive: true });
}

// @ricky0123/vad-web 에셋 복사
const vadWebDist = join(frontendDir, 'node_modules', '@ricky0123', 'vad-web', 'dist');
const vadAssets = [
  'silero_vad_legacy.onnx',
  'silero_vad_v5.onnx',
  'vad.worklet.bundle.min.js',
];

vadAssets.forEach((file) => {
  const src = join(vadWebDist, file);
  const dest = join(publicVadDir, file);
  if (existsSync(src)) {
    copyFileSync(src, dest);
    console.log(`Copied: ${file}`);
  } else {
    console.warn(`Warning: ${file} not found at ${src}`);
  }
});

// onnxruntime-web WASM 파일 복사 (pnpm 구조 지원)
const onnxFiles = ['ort-wasm-simd-threaded.mjs', 'ort-wasm-simd-threaded.wasm'];

// pnpm에서는 .pnpm 폴더가 루트 또는 각 패키지에 있을 수 있음
function findOnnxDir() {
  // 직접 node_modules 경로 시도
  const directPath = join(frontendDir, 'node_modules', 'onnxruntime-web', 'dist');
  if (existsSync(directPath)) return directPath;

  // pnpm workspace: 루트의 .pnpm 폴더에서 찾기
  const rootDir = resolve(frontendDir, '..');
  const searchPaths = [
    join(frontendDir, 'node_modules', '.pnpm'),
    join(rootDir, 'node_modules', '.pnpm'),
  ];

  for (const pnpmPath of searchPaths) {
    if (existsSync(pnpmPath)) {
      const dirs = readdirSync(pnpmPath).filter((d) => d.startsWith('onnxruntime-web@'));
      if (dirs.length > 0) {
        const onnxPath = join(pnpmPath, dirs[0], 'node_modules', 'onnxruntime-web', 'dist');
        if (existsSync(onnxPath)) return onnxPath;
      }
    }
  }

  return null;
}

const onnxDir = findOnnxDir();
if (onnxDir) {
  onnxFiles.forEach((file) => {
    const src = join(onnxDir, file);
    const dest = join(publicVadDir, file);
    if (existsSync(src)) {
      copyFileSync(src, dest);
      console.log(`Copied: ${file}`);
    } else {
      console.warn(`Warning: ${file} not found at ${src}`);
    }
  });
} else {
  console.warn('Warning: onnxruntime-web dist directory not found');
}

console.log('VAD assets copied to public/vad/');
