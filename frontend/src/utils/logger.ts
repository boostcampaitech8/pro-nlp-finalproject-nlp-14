/**
 * 개발 모드에서만 동작하는 로거
 * VITE_DEV_MODE=true 일 때만 콘솔 출력
 */

const isDevMode = import.meta.env.VITE_DEV_MODE === 'true';

export const logger = {
  log: (...args: unknown[]) => {
    if (isDevMode) {
      console.log(...args);
    }
  },
  warn: (...args: unknown[]) => {
    if (isDevMode) {
      console.warn(...args);
    }
  },
  error: (...args: unknown[]) => {
    // 에러는 항상 출력
    console.error(...args);
  },
  info: (...args: unknown[]) => {
    if (isDevMode) {
      console.info(...args);
    }
  },
  debug: (...args: unknown[]) => {
    if (isDevMode) {
      console.debug(...args);
    }
  },
};

export default logger;
