"""Mock 데이터 - Neo4j 그래프 데이터 시뮬레이션"""

from datetime import datetime

# Mock 데이터 저장소 (인메모리)
MOCK_DATA = {
    "teams": {
        "team-1": {
            "id": "team-1",
            "name": "개발팀",
            "description": "백엔드/프론트엔드 개발",
        },
        "team-2": {
            "id": "team-2",
            "name": "기획팀",
            "description": "제품 기획 및 UX 설계",
        },
    },
    "users": {
        "user-1": {
            "id": "user-1",
            "name": "김민준",
            "email": "minjun@example.com",
        },
        "user-2": {
            "id": "user-2",
            "name": "이서연",
            "email": "seoyeon@example.com",
        },
        "user-3": {
            "id": "user-3",
            "name": "박지훈",
            "email": "jihun@example.com",
        },
    },
    "meetings": {
        "meeting-1": {
            "id": "meeting-1",
            "title": "스프린트 계획 회의",
            "status": "completed",
            "team_id": "team-1",
            "participant_ids": ["user-1", "user-2"],
        },
        "meeting-2": {
            "id": "meeting-2",
            "title": "API 설계 리뷰",
            "status": "completed",
            "team_id": "team-1",
            "participant_ids": ["user-1", "user-2", "user-3"],
        },
    },
    "agendas": {
        "agenda-1": {
            "id": "agenda-1",
            "topic": "API 설계 검토",
            "description": "RESTful API 엔드포인트 설계 방향 논의",
            "meeting_id": "meeting-1",
        },
        "agenda-2": {
            "id": "agenda-2",
            "topic": "프로젝트 일정",
            "description": "마일스톤 및 데드라인 확정",
            "meeting_id": "meeting-1",
        },
        "agenda-3": {
            "id": "agenda-3",
            "topic": "인증 방식 결정",
            "description": "JWT vs Session 기반 인증",
            "meeting_id": "meeting-2",
        },
    },
    "decisions": {
        "decision-1": {
            "id": "decision-1",
            "content": "RESTful API 설계 원칙 준수",
            "context": "API 일관성 유지 및 클라이언트 개발 편의성을 위해 REST 원칙을 준수하기로 결정",
            "status": "latest",
            "agenda_id": "agenda-1",
            "created_at": "2026-01-20T10:00:00",
        },
        "decision-2": {
            "id": "decision-2",
            "content": "1차 마일스톤: 2월 15일",
            "context": "MVP 기능 완성 목표",
            "status": "latest",
            "agenda_id": "agenda-2",
            "created_at": "2026-01-20T10:30:00",
        },
        "decision-3": {
            "id": "decision-3",
            "content": "JWT 기반 인증 채택",
            "context": "마이크로서비스 확장성과 stateless 특성 고려",
            "status": "latest",
            "agenda_id": "agenda-3",
            "created_at": "2026-01-22T14:00:00",
        },
    },
    "action_items": {
        "action-1": {
            "id": "action-1",
            "title": "API 문서 작성",
            "description": "OpenAPI 스펙 기반 API 문서화",
            "status": "pending",
            "due_date": "2026-02-01",
            "assignee_id": "user-1",
            "decision_id": "decision-1",
        },
        "action-2": {
            "id": "action-2",
            "title": "JWT 라이브러리 선정",
            "description": "Python JWT 라이브러리 비교 및 선정",
            "status": "in_progress",
            "due_date": "2026-01-28",
            "assignee_id": "user-2",
            "decision_id": "decision-3",
        },
        "action-3": {
            "id": "action-3",
            "title": "마일스톤 일정표 공유",
            "description": "팀 전체에 일정표 공유",
            "status": "completed",
            "due_date": "2026-01-21",
            "assignee_id": "user-3",
            "decision_id": "decision-2",
        },
    },
    # 관계 데이터
    "member_of": [
        {"user_id": "user-1", "team_id": "team-1", "role": "leader"},
        {"user_id": "user-2", "team_id": "team-1", "role": "member"},
        {"user_id": "user-3", "team_id": "team-1", "role": "member"},
        {"user_id": "user-1", "team_id": "team-2", "role": "member"},
    ],
}
