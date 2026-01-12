# Mit Backend 개발 명세서

## 1. 개요

### 1.1 프로젝트 정보
- **프로젝트명**: Mit (Meeting Intelligence Tool)
- **버전**: v0.1.0 (Prototype)
- **문서 작성일**: 2024.12.31
- **레포지토리 구조**: 모노레포 (`mit/backend/`)

### 1.2 기술 스택
| 구분 | 기술 | 버전 | 비고 |
|------|------|------|------|
| Framework | FastAPI | 0.109.x | 비동기 웹 프레임워크 |
| Python | Python | 3.11+ | 비동기 지원 |
| ORM | SQLAlchemy | 2.0.x | 비동기 ORM |
| Database | PostgreSQL | 15.x | 주 데이터베이스 |
| Cache | Redis | 7.x | 캐싱, 세션, Pub/Sub |
| WebRTC | aiortc | 1.6.x | Python WebRTC (SFU) |
| WebSocket | FastAPI WebSocket | - | 시그널링 |
| 인증 | PyJWT | 2.x | JWT 토큰 |
| 파일 저장 | MinIO / S3 | - | 녹음 파일 저장 |
| Task Queue | Celery | 5.x | 백그라운드 작업 |

### 1.3 관련 문서
- `CLAUDE.md` - AI 컨텍스트 및 진행 상황
- `api-contract/openapi.yaml` - API 명세 (SSOT)
- `docs/Mit_모노레포_가이드.md` - 개발 프로세스
- `docs/Mit_Frontend_개발명세서.md` - FE 상세 스펙

---

## 2. 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client (FE)                             │
└─────────────────────────┬───────────────────────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌─────────────────────┐       ┌─────────────────────┐
│   REST API          │       │   WebSocket         │
│   (FastAPI)         │       │   Signaling Server  │
└─────────┬───────────┘       └─────────┬───────────┘
          │                             │
          ▼                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ Auth        │ │ Meeting     │ │ Review      │ │ Knowledge │  │
│  │ Service     │ │ Service     │ │ Service     │ │ Service   │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────┐
│                      Data Layer                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐  │
│  │ PostgreSQL  │ │ Redis       │ │ MinIO/S3    │ │ Celery    │  │
│  │ (Main DB)   │ │ (Cache)     │ │ (Files)     │ │ (Queue)   │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 WebRTC 서버 아키텍처 (SFU 방식)

**SFU (Selective Forwarding Unit) 선택 이유**:
- 서버에서 모든 미디어 스트림을 수신하여 녹음 가능
- 클라이언트 부하 분산
- 녹음 품질 보장

```
┌─────────────────────────────────────────────────────────────────┐
│                     SFU Server (aiortc)                         │
│                                                                 │
│   ┌─────────┐     ┌─────────────────────┐     ┌─────────┐      │
│   │Client A │────▶│                     │────▶│Client B │      │
│   │ Stream  │     │    Media Router     │     │ Stream  │      │
│   └─────────┘     │                     │     └─────────┘      │
│                   │  ┌───────────────┐  │                      │
│   ┌─────────┐     │  │  MediaRecorder│  │     ┌─────────┐      │
│   │Client B │────▶│  │  (녹음)       │  │────▶│Client A │      │
│   │ Stream  │     │  └───────────────┘  │     │ Stream  │      │
│   └─────────┘     └─────────────────────┘     └─────────┘      │
│                              │                                  │
│                              ▼                                  │
│                     ┌───────────────┐                          │
│                     │ Recording     │                          │
│                     │ Storage       │                          │
│                     └───────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 디렉토리 구조

```
mit/                              # 모노레포 루트
├── CLAUDE.md
├── package.json
├── pnpm-workspace.yaml
│
├── api-contract/                 # API 명세 (SSOT)
│   ├── openapi.yaml
│   ├── schemas/
│   │   ├── user.yaml
│   │   ├── meeting.yaml
│   │   ├── review.yaml
│   │   └── knowledge.yaml
│   └── paths/
│       ├── auth.yaml
│       ├── meetings.yaml
│       ├── notes.yaml
│       └── knowledge.yaml
│
├── packages/
│   └── shared-types/             # 공유 타입 (FE용, 참고용)
│
└── backend/                      # ⭐ BE 앱
    ├── pyproject.toml
    ├── requirements.txt
    ├── alembic.ini
    ├── alembic/                  # DB 마이그레이션
    │   ├── env.py
    │   └── versions/
    │
    ├── app/
    │   ├── __init__.py
    │   ├── main.py               # FastAPI 앱 엔트리
    │   ├── config.py             # 설정
    │   ├── dependencies.py       # 의존성 주입
    │   │
    │   ├── api/                  # API 라우터
    │   │   ├── __init__.py
    │   │   └── v1/
    │   │       ├── __init__.py
    │   │       ├── router.py     # v1 라우터 통합
    │   │       ├── auth.py
    │   │       ├── meetings.py
    │   │       ├── notes.py
    │   │       ├── recordings.py
    │   │       ├── review.py
    │   │       └── knowledge.py
    │   │
    │   ├── websocket/            # WebSocket 핸들러
    │   │   ├── __init__.py
    │   │   ├── signaling.py      # WebRTC 시그널링
    │   │   └── events.py         # 실시간 이벤트
    │   │
    │   ├── core/                 # 핵심 모듈
    │   │   ├── __init__.py
    │   │   ├── security.py       # JWT, 암호화
    │   │   ├── database.py       # DB 연결
    │   │   └── redis.py          # Redis 연결
    │   │
    │   ├── models/               # SQLAlchemy 모델
    │   │   ├── __init__.py
    │   │   ├── base.py           # Base 클래스
    │   │   ├── user.py
    │   │   ├── meeting.py
    │   │   ├── note.py
    │   │   ├── recording.py
    │   │   ├── review.py
    │   │   └── knowledge.py
    │   │
    │   ├── schemas/              # Pydantic 스키마
    │   │   ├── __init__.py
    │   │   ├── user.py
    │   │   ├── meeting.py
    │   │   ├── note.py
    │   │   ├── recording.py
    │   │   ├── review.py
    │   │   └── knowledge.py
    │   │
    │   ├── services/             # 비즈니스 로직
    │   │   ├── __init__.py
    │   │   ├── auth.py
    │   │   ├── meeting.py
    │   │   ├── note.py
    │   │   ├── recording.py
    │   │   ├── review.py
    │   │   └── knowledge.py
    │   │
    │   ├── webrtc/               # WebRTC 관련
    │   │   ├── __init__.py
    │   │   ├── room.py           # 회의실 관리
    │   │   ├── peer.py           # 피어 연결 관리
    │   │   └── recorder.py       # 서버 사이드 녹음
    │   │
    │   └── utils/                # 유틸리티
    │       ├── __init__.py
    │       └── helpers.py
    │
    └── tests/
        ├── __init__.py
        ├── conftest.py           # pytest 설정
        ├── unit/
        └── integration/
```

---

## 4. API Contract First

### 4.1 스키마 관리 원칙

API 명세는 `api-contract/openapi.yaml`이 **유일한 진실의 원천(SSOT)**입니다.

```
api-contract/openapi.yaml 수정
        ↓
pnpm run generate:types (FE 타입 생성)
        ↓
backend/app/schemas/ 구현 (OpenAPI 명세 기반)
        ↓
backend/app/api/v1/ 라우터 구현
```

### 4.2 Pydantic 스키마 작성

OpenAPI 명세를 참고하여 Pydantic 스키마를 작성합니다.

```python
# app/schemas/meeting.py
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

from .user import UserSummary


class MeetingStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Response 스키마
class Meeting(BaseModel):
    id: UUID
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    status: MeetingStatus
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    creator: UserSummary
    participants_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MeetingsListResponse(BaseModel):
    meetings: list[Meeting]
    total: int
    page: int
    limit: int


# Request 스키마
class CreateMeetingRequest(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    participant_ids: Optional[list[UUID]] = None


class UpdateMeetingRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None


# WebRTC 관련
class JoinMeetingResponse(BaseModel):
    room_token: str
    signaling_url: str
    ice_servers: list[dict]
```

### 4.3 OpenAPI 자동 문서

FastAPI가 자동 생성하는 문서가 `api-contract/openapi.yaml`과 일치해야 합니다.

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings

app = FastAPI(
    title="Mit API",
    version="1.0.0",
    description="Mit 협업 기반 조직 지식 시스템 API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터
app.include_router(api_router, prefix="/api/v1")

# WebSocket
from app.websocket.signaling import router as ws_router
app.include_router(ws_router)
```

---

## 5. 데이터 모델

### 5.1 Base 모델

```python
# app/models/base.py
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class UUIDMixin:
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
```

### 5.2 User 모델

```python
# app/models/user.py
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Relationships
    meetings = relationship("Meeting", back_populates="creator")
    participations = relationship("MeetingParticipant", back_populates="user")
```

### 5.3 Meeting 모델

```python
# app/models/meeting.py
from datetime import datetime
from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin


class MeetingStatus(str, PyEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Meeting(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "meetings"
    
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus), default=MeetingStatus.SCHEDULED
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    creator_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    
    # Relationships
    creator = relationship("User", back_populates="meetings")
    participants = relationship("MeetingParticipant", back_populates="meeting")
    notes = relationship("Note", back_populates="meeting")
    recordings = relationship("Recording", back_populates="meeting")
    review = relationship("MeetingReview", back_populates="meeting", uselist=False)


class MeetingParticipant(Base, UUIDMixin):
    __tablename__ = "meeting_participants"
    
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20), default="participant")  # host, participant
    joined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    left_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    meeting = relationship("Meeting", back_populates="participants")
    user = relationship("User", back_populates="participations")
```

### 5.4 Review 모델 (Phase 2)

```python
# app/models/review.py
from datetime import datetime
from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin


class ReviewStatus(str, PyEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    MERGED = "merged"


class SuggestionStatus(str, PyEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class VoteType(str, PyEnum):
    ACCEPT = "accept"
    REJECT = "reject"


class MeetingReview(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "meeting_reviews"
    
    meeting_id: Mapped[UUID] = mapped_column(ForeignKey("meetings.id"), unique=True)
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus), default=ReviewStatus.DRAFT
    )
    content: Mapped[str] = mapped_column(Text)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    meeting = relationship("Meeting", back_populates="review")
    lines = relationship("ReviewLine", back_populates="review", cascade="all, delete-orphan")
    approvals = relationship("ReviewApproval", back_populates="review")


class ReviewLine(Base, UUIDMixin):
    __tablename__ = "review_lines"
    
    review_id: Mapped[UUID] = mapped_column(ForeignKey("meeting_reviews.id"))
    line_number: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    
    # Relationships
    review = relationship("MeetingReview", back_populates="lines")
    comments = relationship("ReviewComment", back_populates="line")
    suggestions = relationship("ReviewSuggestion", back_populates="line")


class ReviewComment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "review_comments"
    
    line_id: Mapped[UUID] = mapped_column(ForeignKey("review_lines.id"))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("review_comments.id"), nullable=True
    )
    
    # Relationships
    line = relationship("ReviewLine", back_populates="comments")
    author = relationship("User")
    replies = relationship("ReviewComment", back_populates="parent")
    parent = relationship("ReviewComment", back_populates="replies", remote_side="ReviewComment.id")


class ReviewSuggestion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "review_suggestions"
    
    line_id: Mapped[UUID] = mapped_column(ForeignKey("review_lines.id"))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    original_text: Mapped[str] = mapped_column(Text)
    suggested_text: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SuggestionStatus] = mapped_column(
        Enum(SuggestionStatus), default=SuggestionStatus.PENDING
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    line = relationship("ReviewLine", back_populates="suggestions")
    author = relationship("User")
    votes = relationship("SuggestionVote", back_populates="suggestion")


class SuggestionVote(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "suggestion_votes"
    __table_args__ = (
        UniqueConstraint('suggestion_id', 'user_id', name='unique_suggestion_vote'),
    )
    
    suggestion_id: Mapped[UUID] = mapped_column(ForeignKey("review_suggestions.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    vote: Mapped[VoteType] = mapped_column(Enum(VoteType))
    
    # Relationships
    suggestion = relationship("ReviewSuggestion", back_populates="votes")
    user = relationship("User")


class ReviewApproval(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "review_approvals"
    __table_args__ = (
        UniqueConstraint('review_id', 'user_id', name='unique_review_approval'),
    )
    
    review_id: Mapped[UUID] = mapped_column(ForeignKey("meeting_reviews.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    approved: Mapped[bool] = mapped_column(default=False)
    
    # Relationships
    review = relationship("MeetingReview", back_populates="approvals")
    user = relationship("User")
```

### 5.5 Knowledge 모델 (Phase 2)

```python
# app/models/knowledge.py
from datetime import datetime
from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UUIDMixin, TimestampMixin


class BranchStatus(str, PyEnum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


class Project(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "projects"
    
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    facts = relationship("Fact", back_populates="project")


class Fact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "facts"
    
    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True
    )
    key: Mapped[str] = mapped_column(String(200))  # e.g., "마케팅 예산"
    value: Mapped[str] = mapped_column(Text)  # e.g., "5,000만원"
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_meeting_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("meetings.id"), nullable=True
    )
    
    # Relationships
    project = relationship("Project", back_populates="facts")
    source_meeting = relationship("Meeting")
    history = relationship("FactHistory", back_populates="fact", order_by="FactHistory.created_at.desc()")
    branches = relationship("FactBranch", back_populates="fact")


class FactHistory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "fact_history"
    
    fact_id: Mapped[UUID] = mapped_column(ForeignKey("facts.id"))
    previous_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    meeting_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("meetings.id"), nullable=True
    )
    
    # Relationships
    fact = relationship("Fact", back_populates="history")
    changed_by = relationship("User")
    meeting = relationship("Meeting")


class FactBranch(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "fact_branches"
    
    fact_id: Mapped[UUID] = mapped_column(ForeignKey("facts.id"))
    title: Mapped[str] = mapped_column(String(200))
    proposed_value: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[BranchStatus] = mapped_column(
        Enum(BranchStatus), default=BranchStatus.OPEN
    )
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    fact = relationship("Fact", back_populates="branches")
    author = relationship("User")
    discussions = relationship("BranchDiscussion", back_populates="branch")
    approvals = relationship("BranchApproval", back_populates="branch")


class BranchDiscussion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "branch_discussions"
    
    branch_id: Mapped[UUID] = mapped_column(ForeignKey("fact_branches.id"))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("branch_discussions.id"), nullable=True
    )
    
    # Relationships
    branch = relationship("FactBranch", back_populates="discussions")
    author = relationship("User")
    replies = relationship("BranchDiscussion", back_populates="parent")
    parent = relationship("BranchDiscussion", back_populates="replies", remote_side="BranchDiscussion.id")


class BranchApproval(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "branch_approvals"
    
    branch_id: Mapped[UUID] = mapped_column(ForeignKey("fact_branches.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    approved: Mapped[bool] = mapped_column(default=False)
    
    # Relationships
    branch = relationship("FactBranch", back_populates="approvals")
    user = relationship("User")
```

---

## 6. API 엔드포인트

### 6.1 라우터 구조

```python
# app/api/v1/router.py
from fastapi import APIRouter

from . import auth, meetings, notes, recordings, review, knowledge

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(meetings.router, prefix="/meetings", tags=["Meeting"])
api_router.include_router(notes.router, prefix="/meetings/{meeting_id}/notes", tags=["Note"])
api_router.include_router(recordings.router, prefix="/meetings/{meeting_id}/recordings", tags=["Recording"])
api_router.include_router(review.router, prefix="/meetings/{meeting_id}/review", tags=["Review"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge"])
```

### 6.2 인증 API

```python
# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, verify_password, get_password_hash
from app.schemas.user import UserCreate, UserResponse, LoginRequest, TokenResponse
from app.services.auth import AuthService

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """회원가입"""
    service = AuthService(db)
    user = await service.create_user(user_data)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """로그인 - JWT 토큰 발급"""
    service = AuthService(db)
    user = await service.authenticate(credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_access_token(data={"sub": str(user.id)}, expires_days=7)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=user
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user = Depends(get_current_user)
):
    """현재 사용자 정보"""
    return current_user
```

### 6.3 회의 API

```python
# app/api/v1/meetings.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.meeting import (
    Meeting, MeetingsListResponse, CreateMeetingRequest,
    UpdateMeetingRequest, JoinMeetingResponse
)
from app.services.meeting import MeetingService

router = APIRouter()


@router.get("/", response_model=MeetingsListResponse)
async def list_meetings(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """회의 목록 조회"""
    service = MeetingService(db)
    meetings, total = await service.list_meetings(
        user_id=current_user.id,
        page=page,
        limit=limit,
        status=status
    )
    return MeetingsListResponse(
        meetings=meetings,
        total=total,
        page=page,
        limit=limit
    )


@router.post("/", response_model=Meeting, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    meeting_data: CreateMeetingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """회의 생성"""
    service = MeetingService(db)
    meeting = await service.create_meeting(meeting_data, current_user.id)
    return meeting


@router.get("/{meeting_id}", response_model=Meeting)
async def get_meeting(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """회의 상세 조회"""
    service = MeetingService(db)
    meeting = await service.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting


@router.post("/{meeting_id}/join", response_model=JoinMeetingResponse)
async def join_meeting(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """회의 참여 - WebRTC 연결 정보 반환"""
    service = MeetingService(db)
    result = await service.join_meeting(meeting_id, current_user.id)
    return result


@router.post("/{meeting_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_meeting(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """회의 퇴장"""
    service = MeetingService(db)
    await service.leave_meeting(meeting_id, current_user.id)


@router.post("/{meeting_id}/end", status_code=status.HTTP_204_NO_CONTENT)
async def end_meeting(
    meeting_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """회의 종료 (호스트 전용)"""
    service = MeetingService(db)
    await service.end_meeting(meeting_id, current_user.id)
```

### 6.4 WebSocket 시그널링

```python
# app/websocket/signaling.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.webrtc.room import RoomManager
from app.core.security import verify_token

router = APIRouter()
room_manager = RoomManager()


@router.websocket("/ws/room/{room_id}")
async def websocket_signaling(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(...)
):
    """WebRTC 시그널링 WebSocket"""
    # 토큰 검증
    payload = verify_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    user_id = payload.get("sub")
    
    # 연결 수락
    await websocket.accept()
    
    # 방 참여
    await room_manager.join_room(room_id, user_id, websocket)
    
    try:
        # 기존 참가자들에게 알림
        await room_manager.broadcast(room_id, {
            "type": "user-joined",
            "user_id": user_id
        }, exclude=user_id)
        
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "offer":
                await room_manager.relay_to_user(
                    room_id, data.get("to"), {
                        "type": "offer",
                        "from": user_id,
                        "sdp": data.get("sdp")
                    }
                )
            
            elif message_type == "answer":
                await room_manager.relay_to_user(
                    room_id, data.get("to"), {
                        "type": "answer",
                        "from": user_id,
                        "sdp": data.get("sdp")
                    }
                )
            
            elif message_type == "ice-candidate":
                await room_manager.relay_to_user(
                    room_id, data.get("to"), {
                        "type": "ice-candidate",
                        "from": user_id,
                        "candidate": data.get("candidate")
                    }
                )
            
            elif message_type == "media-state":
                await room_manager.broadcast(room_id, {
                    "type": "media-state",
                    "user_id": user_id,
                    "audio": data.get("audio"),
                    "video": data.get("video")
                }, exclude=user_id)
    
    except WebSocketDisconnect:
        await room_manager.leave_room(room_id, user_id)
        await room_manager.broadcast(room_id, {
            "type": "user-left",
            "user_id": user_id
        })
```

### 6.5 WebRTC Room Manager

```python
# app/webrtc/room.py
from typing import Dict, Set
from fastapi import WebSocket
import asyncio


class Room:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.participants: Dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()
    
    async def add_participant(self, user_id: str, websocket: WebSocket):
        async with self.lock:
            self.participants[user_id] = websocket
    
    async def remove_participant(self, user_id: str):
        async with self.lock:
            self.participants.pop(user_id, None)
    
    def get_participant_ids(self) -> Set[str]:
        return set(self.participants.keys())


class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}
        self.lock = asyncio.Lock()
    
    async def get_or_create_room(self, room_id: str) -> Room:
        async with self.lock:
            if room_id not in self.rooms:
                self.rooms[room_id] = Room(room_id)
            return self.rooms[room_id]
    
    async def join_room(self, room_id: str, user_id: str, websocket: WebSocket):
        room = await self.get_or_create_room(room_id)
        await room.add_participant(user_id, websocket)
        
        # 기존 참가자 목록 전송
        existing_participants = room.get_participant_ids() - {user_id}
        await websocket.send_json({
            "type": "room-info",
            "participants": list(existing_participants)
        })
    
    async def leave_room(self, room_id: str, user_id: str):
        if room_id in self.rooms:
            room = self.rooms[room_id]
            await room.remove_participant(user_id)
            
            # 빈 방 정리
            if not room.participants:
                async with self.lock:
                    self.rooms.pop(room_id, None)
    
    async def broadcast(self, room_id: str, message: dict, exclude: str | None = None):
        if room_id not in self.rooms:
            return
        
        room = self.rooms[room_id]
        for user_id, ws in room.participants.items():
            if user_id != exclude:
                try:
                    await ws.send_json(message)
                except:
                    pass
    
    async def relay_to_user(self, room_id: str, user_id: str, message: dict):
        if room_id not in self.rooms:
            return
        
        room = self.rooms[room_id]
        ws = room.participants.get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except:
                pass
```

---

## 7. 서버 사이드 녹음 (aiortc)

```python
# app/webrtc/recorder.py
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRecorder
import asyncio
from pathlib import Path
from uuid import UUID

from app.config import settings


class MeetingRecorder:
    def __init__(self, meeting_id: UUID):
        self.meeting_id = meeting_id
        self.output_dir = Path(settings.RECORDING_PATH) / str(meeting_id)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.recorders: dict[str, MediaRecorder] = {}
        self.is_recording = False
    
    async def add_participant_track(self, user_id: str, track):
        """참가자 트랙 추가 및 개별 녹음"""
        output_path = self.output_dir / f"{user_id}.webm"
        recorder = MediaRecorder(str(output_path))
        recorder.addTrack(track)
        
        if self.is_recording:
            await recorder.start()
        
        self.recorders[user_id] = recorder
    
    async def start(self):
        """모든 녹음 시작"""
        self.is_recording = True
        for recorder in self.recorders.values():
            await recorder.start()
    
    async def stop(self) -> list[str]:
        """모든 녹음 종료, 파일 경로 반환"""
        self.is_recording = False
        paths = []
        
        for user_id, recorder in self.recorders.items():
            await recorder.stop()
            paths.append(str(self.output_dir / f"{user_id}.webm"))
        
        return paths
    
    async def remove_participant(self, user_id: str):
        """참가자 녹음 종료"""
        if user_id in self.recorders:
            await self.recorders[user_id].stop()
            del self.recorders[user_id]
```

---

## 8. 환경 설정

### 8.1 환경 변수

```env
# backend/.env
# Database
DATABASE_URL=postgresql+asyncpg://mit:mit@localhost:5432/mit

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# S3/MinIO
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=mit-recordings

# WebRTC
STUN_SERVER=stun:stun.l.google.com:19302
TURN_SERVER=
TURN_USERNAME=
TURN_PASSWORD=

# Recording
RECORDING_PATH=/tmp/mit-recordings

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=true
CORS_ORIGINS=["http://localhost:5173"]
```

### 8.2 Config 클래스

```python
# app/config.py
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str
    
    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # S3/MinIO
    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str
    
    # WebRTC
    STUN_SERVER: str = "stun:stun.l.google.com:19302"
    TURN_SERVER: str | None = None
    TURN_USERNAME: str | None = None
    TURN_PASSWORD: str | None = None
    
    # Recording
    RECORDING_PATH: str = "/tmp/mit-recordings"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]
    
    class Config:
        env_file = ".env"


settings = Settings()
```

---

## 9. 자주 사용하는 명령어

```bash
# 모노레포 루트에서
pnpm run dev:be           # BE 개발 서버 실행

# backend 디렉토리에서
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# DB 마이그레이션
alembic upgrade head                    # 마이그레이션 적용
alembic revision --autogenerate -m "설명"  # 마이그레이션 생성
alembic downgrade -1                    # 롤백

# 테스트
pytest                                  # 전체 테스트
pytest tests/unit                       # 유닛 테스트만
pytest -v --cov=app                     # 커버리지 포함

# 린트
ruff check .                            # 린트
ruff format .                           # 포맷팅
```

---

## 10. 필수 패키지

```txt
# backend/requirements.txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
asyncpg==0.29.0
alembic==1.13.1
pydantic==2.5.3
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.6
aiortc==1.6.0
redis==5.0.1
boto3==1.34.0
celery==5.3.6
httpx==0.26.0

# Dev
pytest==7.4.0
pytest-asyncio==0.23.0
pytest-cov==4.1.0
ruff==0.1.9
```

### 10.1 aiortc 시스템 의존성

```bash
# Ubuntu/Debian
apt-get install libavdevice-dev libavfilter-dev libopus-dev libvpx-dev pkg-config libsrtp2-dev

# macOS
brew install ffmpeg opus libvpx srtp
```
