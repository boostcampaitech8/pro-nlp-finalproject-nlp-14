# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# pnpm 설치
RUN corepack enable && corepack prepare pnpm@latest --activate

# 의존성 파일 복사 (모노레포 구조)
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY frontend/package.json ./frontend/
COPY frontend/scripts ./frontend/scripts
COPY packages ./packages

# 의존성 설치 (postinstall에서 VAD 에셋 복사)
RUN pnpm install --frozen-lockfile

# shared-types 빌드 (frontend에서 참조)
RUN pnpm --filter @mit/shared-types build

# 프론트엔드 소스 복사
COPY frontend ./frontend

# 빌드 인자로 환경변수 전달
ARG VITE_API_URL=/api/v1
ARG VITE_DEV_MODE=false
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_DEV_MODE=$VITE_DEV_MODE

# 빌드 (워크스페이스 필터 사용)
WORKDIR /app/frontend
RUN pnpm build

# Production stage
FROM nginx:alpine

# nginx 설정 복사
COPY frontend/nginx.conf /etc/nginx/nginx.conf

# 빌드 결과물 복사
COPY --from=builder /app/frontend/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
