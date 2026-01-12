# Mit Frontend 개발 명세서

## 1. 개요

### 1.1 프로젝트 정보
- **프로젝트명**: Mit (Meeting Intelligence Tool)
- **버전**: v0.1.0 (Prototype)
- **문서 작성일**: 2024.12.31
- **레포지토리 구조**: 모노레포 (`mit/frontend/`)

### 1.2 기술 스택
| 구분 | 기술 | 버전 | 비고 |
|------|------|------|------|
| Framework | React | 18.x | TypeScript 기반 |
| Build Tool | Vite | 5.x | 빠른 HMR 지원 |
| 상태관리 | Zustand | 4.x | 경량 상태관리 |
| 스타일링 | Tailwind CSS | 3.x | Utility-first CSS |
| 실시간 통신 | WebRTC | - | 음성/영상 통화 |
| API 통신 | Axios | 1.x | HTTP 클라이언트 |
| WebSocket | Native WebSocket | - | 시그널링용 |
| 폼 관리 | React Hook Form | 7.x | 폼 유효성 검증 |
| 라우팅 | React Router | 6.x | SPA 라우팅 |
| 공유 타입 | @mit/shared-types | - | 모노레포 내부 패키지 |

### 1.3 관련 문서
- `CLAUDE.md` - AI 컨텍스트 및 진행 상황
- `api-contract/openapi.yaml` - API 명세 (SSOT)
- `docs/Mit_모노레포_가이드.md` - 개발 프로세스
- `docs/Mit_Backend_개발명세서.md` - BE 상세 스펙

---

## 2. 디렉토리 구조

```
mit/                              # 모노레포 루트
├── CLAUDE.md
├── package.json                  # 워크스페이스 루트
├── pnpm-workspace.yaml
│
├── api-contract/                 # API 명세 (SSOT)
│   ├── openapi.yaml
│   ├── schemas/
│   └── paths/
│
├── packages/
│   └── shared-types/             # 공유 타입 패키지
│       ├── package.json
│       └── src/
│           ├── index.ts
│           ├── user.ts
│           ├── meeting.ts
│           ├── review.ts
│           ├── knowledge.ts
│           └── api.generated.ts  # OpenAPI에서 자동 생성
│
└── frontend/                     # ⭐ FE 앱
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    ├── public/
    └── src/
        ├── main.tsx              # 엔트리포인트
        ├── App.tsx               # 루트 컴포넌트
        ├── vite-env.d.ts
        │
        ├── components/           # 재사용 컴포넌트
        │   ├── common/           # 공통 UI
        │   │   ├── Button.tsx
        │   │   ├── Input.tsx
        │   │   ├── Modal.tsx
        │   │   ├── Avatar.tsx
        │   │   └── Loading.tsx
        │   ├── auth/             # 인증 관련
        │   │   ├── LoginForm.tsx
        │   │   └── RegisterForm.tsx
        │   ├── meeting/          # 회의 관련
        │   │   ├── MeetingCard.tsx
        │   │   ├── MeetingList.tsx
        │   │   ├── MeetingForm.tsx
        │   │   └── ParticipantList.tsx
        │   ├── room/             # 실시간 회의
        │   │   ├── VideoGrid.tsx
        │   │   ├── VideoTile.tsx
        │   │   ├── ControlBar.tsx
        │   │   ├── ChatPanel.tsx
        │   │   └── ParticipantPanel.tsx
        │   ├── notes/            # 회의록
        │   │   ├── NoteEditor.tsx
        │   │   ├── NoteViewer.tsx
        │   │   └── RecordingUploader.tsx
        │   ├── review/           # PR Review 스타일
        │   │   ├── ReviewContainer.tsx
        │   │   ├── ReviewLine.tsx
        │   │   ├── CommentThread.tsx
        │   │   ├── SuggestionCard.tsx
        │   │   ├── DiffViewer.tsx
        │   │   └── ApprovalPanel.tsx
        │   └── knowledge/        # Ground Truth
        │       ├── FactCard.tsx
        │       ├── FactList.tsx
        │       ├── FactHistory.tsx
        │       ├── BranchCard.tsx
        │       └── DiscussionThread.tsx
        │
        ├── pages/                # 페이지 컴포넌트
        │   ├── LoginPage.tsx
        │   ├── RegisterPage.tsx
        │   ├── DashboardPage.tsx
        │   ├── MeetingDetailPage.tsx
        │   ├── MeetingCreatePage.tsx
        │   ├── RoomPage.tsx
        │   ├── NotesPage.tsx
        │   ├── ReviewPage.tsx
        │   └── KnowledgePage.tsx
        │
        ├── hooks/                # 커스텀 훅
        │   ├── useAuth.ts
        │   ├── useWebRTC.ts
        │   ├── useMediaRecorder.ts
        │   ├── useMeeting.ts
        │   └── useWebSocket.ts
        │
        ├── services/             # API 호출
        │   ├── api.ts            # Axios 인스턴스
        │   ├── auth.service.ts
        │   ├── meeting.service.ts
        │   ├── note.service.ts
        │   ├── review.service.ts
        │   └── knowledge.service.ts
        │
        ├── stores/               # Zustand 스토어
        │   ├── authStore.ts
        │   ├── meetingStore.ts
        │   └── roomStore.ts
        │
        ├── types/                # FE 전용 타입
        │   └── local.ts          # 공유 타입 외 FE 전용
        │
        └── utils/                # 유틸리티
            ├── format.ts
            └── validation.ts
```

---

## 3. 타입 시스템

### 3.1 공유 타입 사용

모든 API 관련 타입은 `@mit/shared-types` 패키지에서 import합니다.

```typescript
// 올바른 방법
import { Meeting, User, CreateMeetingRequest } from '@mit/shared-types';

// 잘못된 방법 - 직접 타입 정의 금지
interface Meeting { ... }  // ❌
```

### 3.2 패키지 설정

```json
// frontend/package.json
{
  "name": "@mit/frontend",
  "dependencies": {
    "@mit/shared-types": "workspace:*"
  }
}
```

```json
// frontend/tsconfig.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"],
      "@mit/shared-types": ["../packages/shared-types/src"]
    }
  },
  "references": [
    { "path": "../packages/shared-types" }
  ]
}
```

### 3.3 타입 생성 워크플로우

API 명세 변경 시:

```bash
# 모노레포 루트에서 실행
pnpm run generate:types

# 생성되는 파일
# packages/shared-types/src/api.generated.ts
```

---

## 4. Phase 1: 미팅 시스템 구축

### 4.1 핵심 목표
- 실시간 음성/영상 회의 기능 구현
- 회의 데이터 수집 및 저장 기반 마련
- 기본적인 회의록 생성 기능

### 4.2 라우팅 구조

| 경로 | 페이지 | 설명 |
|------|--------|------|
| `/login` | LoginPage | 로그인 |
| `/register` | RegisterPage | 회원가입 |
| `/` | DashboardPage | 회의 목록/대시보드 |
| `/meetings/new` | MeetingCreatePage | 새 회의 생성 |
| `/meetings/:id` | MeetingDetailPage | 회의 상세 |
| `/room/:id` | RoomPage | 실시간 회의 |
| `/meetings/:id/notes` | NotesPage | 회의록 편집 |

### 4.3 인증 모듈

```typescript
// src/hooks/useAuth.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User, LoginRequest, TokenResponse } from '@mit/shared-types';
import { authService } from '@/services/auth.service';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      
      login: async (credentials) => {
        const response = await authService.login(credentials);
        set({
          user: response.user,
          token: response.access_token,
          isAuthenticated: true
        });
      },
      
      logout: () => {
        set({ user: null, token: null, isAuthenticated: false });
      },
      
      refreshToken: async () => {
        // refresh token 로직
      }
    }),
    { name: 'auth-storage' }
  )
);
```

### 4.4 WebRTC 모듈

```typescript
// src/hooks/useWebRTC.ts
import { useCallback, useEffect, useRef, useState } from 'react';

interface UseWebRTCOptions {
  roomId: string;
  signalingUrl: string;
  iceServers: RTCIceServer[];
}

interface Participant {
  id: string;
  stream: MediaStream;
  audioEnabled: boolean;
  videoEnabled: boolean;
}

export function useWebRTC({ roomId, signalingUrl, iceServers }: UseWebRTCOptions) {
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [participants, setParticipants] = useState<Map<string, Participant>>(new Map());
  const [connectionState, setConnectionState] = useState<RTCPeerConnectionState>('new');
  
  const wsRef = useRef<WebSocket | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  
  // 로컬 미디어 스트림 시작
  const startLocalStream = useCallback(async (video = true, audio = true) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video, audio });
      setLocalStream(stream);
      return stream;
    } catch (error) {
      console.error('Failed to get local stream:', error);
      throw error;
    }
  }, []);
  
  // WebSocket 시그널링 연결
  const connectSignaling = useCallback(() => {
    const ws = new WebSocket(signalingUrl);
    
    ws.onopen = () => {
      console.log('Signaling connected');
      ws.send(JSON.stringify({ type: 'join', roomId }));
    };
    
    ws.onmessage = async (event) => {
      const message = JSON.parse(event.data);
      await handleSignalingMessage(message);
    };
    
    wsRef.current = ws;
  }, [signalingUrl, roomId]);
  
  // 시그널링 메시지 처리
  const handleSignalingMessage = async (message: any) => {
    switch (message.type) {
      case 'offer':
        await handleOffer(message);
        break;
      case 'answer':
        await handleAnswer(message);
        break;
      case 'ice-candidate':
        await handleIceCandidate(message);
        break;
      case 'user-joined':
        // 새 참가자 처리
        break;
      case 'user-left':
        // 참가자 퇴장 처리
        break;
    }
  };
  
  // Offer 처리
  const handleOffer = async (message: any) => {
    const pc = pcRef.current;
    if (!pc) return;
    
    await pc.setRemoteDescription(new RTCSessionDescription(message.sdp));
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    
    wsRef.current?.send(JSON.stringify({
      type: 'answer',
      sdp: pc.localDescription,
      to: message.from
    }));
  };
  
  // 미디어 컨트롤
  const toggleAudio = useCallback(() => {
    if (localStream) {
      const audioTrack = localStream.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
      }
    }
  }, [localStream]);
  
  const toggleVideo = useCallback(() => {
    if (localStream) {
      const videoTrack = localStream.getVideoTracks()[0];
      if (videoTrack) {
        videoTrack.enabled = !videoTrack.enabled;
      }
    }
  }, [localStream]);
  
  // 정리
  const disconnect = useCallback(() => {
    localStream?.getTracks().forEach(track => track.stop());
    pcRef.current?.close();
    wsRef.current?.close();
    setLocalStream(null);
    setParticipants(new Map());
  }, [localStream]);
  
  return {
    localStream,
    participants,
    connectionState,
    startLocalStream,
    connectSignaling,
    toggleAudio,
    toggleVideo,
    disconnect
  };
}
```

### 4.5 API 서비스

```typescript
// src/services/api.ts
import axios from 'axios';
import { useAuthStore } from '@/stores/authStore';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// 요청 인터셉터 - 토큰 추가
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 응답 인터셉터 - 에러 처리
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // 토큰 만료 처리
      try {
        await useAuthStore.getState().refreshToken();
        return api.request(error.config);
      } catch {
        useAuthStore.getState().logout();
      }
    }
    return Promise.reject(error);
  }
);
```

```typescript
// src/services/meeting.service.ts
import { api } from './api';
import {
  Meeting,
  MeetingsListResponse,
  CreateMeetingRequest,
  JoinMeetingResponse
} from '@mit/shared-types';

export const meetingService = {
  // 회의 목록 조회
  async list(params?: { page?: number; limit?: number; status?: string }) {
    const response = await api.get<MeetingsListResponse>('/meetings', { params });
    return response.data;
  },
  
  // 회의 상세 조회
  async get(id: string) {
    const response = await api.get<Meeting>(`/meetings/${id}`);
    return response.data;
  },
  
  // 회의 생성
  async create(data: CreateMeetingRequest) {
    const response = await api.post<Meeting>('/meetings', data);
    return response.data;
  },
  
  // 회의 참여
  async join(id: string) {
    const response = await api.post<JoinMeetingResponse>(`/meetings/${id}/join`);
    return response.data;
  },
  
  // 회의 퇴장
  async leave(id: string) {
    await api.post(`/meetings/${id}/leave`);
  },
  
  // 회의 종료
  async end(id: string) {
    await api.post(`/meetings/${id}/end`);
  }
};
```

---

## 5. Phase 2: PR Review 스타일 협업 시스템

### 5.1 핵심 목표
- Git PR Review 스타일의 회의록 검토 시스템
- Ground Truth (GT) 관리 시스템
- 협업 기반 합의 프로세스

### 5.2 추가 라우팅

| 경로 | 페이지 | 설명 |
|------|--------|------|
| `/meetings/:id/review` | ReviewPage | 회의록 Review |
| `/meetings/:id/history` | HistoryPage | 변경 이력 |
| `/knowledge` | KnowledgePage | GT 대시보드 |
| `/knowledge/:projectId` | ProjectKnowledgePage | 프로젝트별 GT |
| `/knowledge/facts/:id` | FactDetailPage | GT 상세 |
| `/knowledge/facts/:id/branch/:branchId` | BranchPage | Branch 상세 |

### 5.3 Review 컴포넌트

```typescript
// src/components/review/ReviewLine.tsx
import { useState } from 'react';
import { ReviewLine as ReviewLineType, Comment } from '@mit/shared-types';
import { CommentThread } from './CommentThread';
import { SuggestionForm } from './SuggestionForm';

interface ReviewLineProps {
  line: ReviewLineType;
  comments: Comment[];
  onAddComment: (content: string) => void;
  onAddSuggestion: (original: string, suggested: string, reason?: string) => void;
}

export function ReviewLine({ line, comments, onAddComment, onAddSuggestion }: ReviewLineProps) {
  const [showCommentForm, setShowCommentForm] = useState(false);
  const [showSuggestionForm, setShowSuggestionForm] = useState(false);
  
  return (
    <div className="group relative border-b border-gray-100 hover:bg-gray-50">
      {/* 라인 번호 */}
      <span className="absolute left-0 w-12 text-right text-gray-400 text-sm pr-4">
        {line.line_number}
      </span>
      
      {/* 내용 */}
      <div className="pl-16 pr-4 py-2">
        <p className="text-gray-800">{line.content}</p>
        
        {/* 코멘트 스레드 */}
        {comments.length > 0 && (
          <CommentThread comments={comments} />
        )}
        
        {/* 액션 버튼 (hover 시 표시) */}
        <div className="hidden group-hover:flex gap-2 mt-2">
          <button
            onClick={() => setShowCommentForm(true)}
            className="text-sm text-blue-600 hover:underline"
          >
            Comment
          </button>
          <button
            onClick={() => setShowSuggestionForm(true)}
            className="text-sm text-green-600 hover:underline"
          >
            Suggest Change
          </button>
        </div>
        
        {/* 코멘트 폼 */}
        {showCommentForm && (
          <CommentForm
            onSubmit={(content) => {
              onAddComment(content);
              setShowCommentForm(false);
            }}
            onCancel={() => setShowCommentForm(false)}
          />
        )}
        
        {/* 제안 폼 */}
        {showSuggestionForm && (
          <SuggestionForm
            originalText={line.content}
            onSubmit={(suggested, reason) => {
              onAddSuggestion(line.content, suggested, reason);
              setShowSuggestionForm(false);
            }}
            onCancel={() => setShowSuggestionForm(false)}
          />
        )}
      </div>
    </div>
  );
}
```

```typescript
// src/components/review/SuggestionCard.tsx
import { Suggestion, SuggestionVote } from '@mit/shared-types';
import { DiffViewer } from './DiffViewer';

interface SuggestionCardProps {
  suggestion: Suggestion;
  votes: SuggestionVote[];
  currentUserId: string;
  onVote: (vote: 'accept' | 'reject') => void;
}

export function SuggestionCard({ 
  suggestion, 
  votes, 
  currentUserId, 
  onVote 
}: SuggestionCardProps) {
  const acceptCount = votes.filter(v => v.vote === 'accept').length;
  const rejectCount = votes.filter(v => v.vote === 'reject').length;
  const userVote = votes.find(v => v.user_id === currentUserId);
  
  return (
    <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-4 my-2">
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-yellow-800">
          {suggestion.author.name}의 제안
        </span>
        <span className={`text-xs px-2 py-1 rounded ${
          suggestion.status === 'pending' ? 'bg-yellow-200 text-yellow-800' :
          suggestion.status === 'accepted' ? 'bg-green-200 text-green-800' :
          'bg-red-200 text-red-800'
        }`}>
          {suggestion.status}
        </span>
      </div>
      
      {/* Diff 뷰어 */}
      <DiffViewer
        original={suggestion.original_text}
        modified={suggestion.suggested_text}
      />
      
      {/* 사유 */}
      {suggestion.reason && (
        <p className="text-sm text-gray-600 mt-2 italic">
          "{suggestion.reason}"
        </p>
      )}
      
      {/* 투표 */}
      {suggestion.status === 'pending' && (
        <div className="flex items-center gap-4 mt-3 pt-3 border-t border-yellow-200">
          <button
            onClick={() => onVote('accept')}
            disabled={userVote?.vote === 'accept'}
            className={`flex items-center gap-1 px-3 py-1 rounded text-sm ${
              userVote?.vote === 'accept' 
                ? 'bg-green-600 text-white' 
                : 'bg-green-100 text-green-700 hover:bg-green-200'
            }`}
          >
            Accept ({acceptCount})
          </button>
          <button
            onClick={() => onVote('reject')}
            disabled={userVote?.vote === 'reject'}
            className={`flex items-center gap-1 px-3 py-1 rounded text-sm ${
              userVote?.vote === 'reject'
                ? 'bg-red-600 text-white'
                : 'bg-red-100 text-red-700 hover:bg-red-200'
            }`}
          >
            Reject ({rejectCount})
          </button>
        </div>
      )}
    </div>
  );
}
```

### 5.4 Review 서비스

```typescript
// src/services/review.service.ts
import { api } from './api';
import {
  ReviewDetail,
  CreateCommentRequest,
  CreateSuggestionRequest,
  VoteSuggestionRequest
} from '@mit/shared-types';

export const reviewService = {
  // Review 상세 조회
  async get(meetingId: string) {
    const response = await api.get<ReviewDetail>(`/meetings/${meetingId}/review`);
    return response.data;
  },
  
  // 코멘트 추가
  async addComment(meetingId: string, data: CreateCommentRequest) {
    const response = await api.post(`/meetings/${meetingId}/review/comment`, data);
    return response.data;
  },
  
  // 제안 추가
  async addSuggestion(meetingId: string, data: CreateSuggestionRequest) {
    const response = await api.post(`/meetings/${meetingId}/review/suggestion`, data);
    return response.data;
  },
  
  // 제안 투표
  async voteSuggestion(meetingId: string, suggestionId: string, data: VoteSuggestionRequest) {
    await api.post(`/meetings/${meetingId}/review/suggestion/${suggestionId}/vote`, data);
  },
  
  // Merge (확정)
  async merge(meetingId: string, acceptedSuggestionIds: string[]) {
    const response = await api.post(`/meetings/${meetingId}/review/merge`, {
      accepted_suggestions: acceptedSuggestionIds
    });
    return response.data;
  }
};
```

---

## 6. 환경 설정

### 6.1 환경 변수

```env
# frontend/.env.local
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000
VITE_STUN_SERVER=stun:stun.l.google.com:19302
```

### 6.2 Vite 설정

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@mit/shared-types': path.resolve(__dirname, '../packages/shared-types/src')
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  }
});
```

### 6.3 package.json

```json
{
  "name": "@mit/frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit",
    "lint": "eslint src --ext ts,tsx",
    "test": "vitest"
  },
  "dependencies": {
    "@mit/shared-types": "workspace:*",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "zustand": "^4.4.0",
    "axios": "^1.6.0",
    "react-hook-form": "^7.48.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.3.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vitest": "^1.0.0"
  }
}
```

---

## 7. 자주 사용하는 명령어

```bash
# 모노레포 루트에서
pnpm run dev:fe           # FE 개발 서버 실행
pnpm run generate:types   # API 명세에서 타입 생성

# frontend 디렉토리에서
pnpm dev                  # 개발 서버 (http://localhost:5173)
pnpm build                # 프로덕션 빌드
pnpm typecheck            # 타입 체크
pnpm lint                 # 린트
pnpm test                 # 테스트
```

---

## 8. 코드 컨벤션

### 8.1 파일 명명
- 컴포넌트: `PascalCase.tsx` (예: `MeetingCard.tsx`)
- 훅: `camelCase.ts` (예: `useAuth.ts`)
- 서비스: `kebab-case.service.ts` (예: `meeting.service.ts`)
- 타입: `kebab-case.ts` (예: `meeting.ts`) - 공유 타입은 shared-types에

### 8.2 컴포넌트 구조
```typescript
// 권장 구조
import { useState, useEffect } from 'react';
import { SomeType } from '@mit/shared-types';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/common/Button';

interface Props {
  // props 정의
}

export function ComponentName({ prop1, prop2 }: Props) {
  // 1. 훅
  // 2. 상태
  // 3. 파생 값
  // 4. 이펙트
  // 5. 핸들러
  // 6. 렌더
  return (
    // JSX
  );
}
```

### 8.3 API 호출
- 항상 서비스 레이어 통해 호출 (직접 axios 호출 금지)
- 타입은 `@mit/shared-types`에서 import
- 에러 처리는 컴포넌트 레벨에서
