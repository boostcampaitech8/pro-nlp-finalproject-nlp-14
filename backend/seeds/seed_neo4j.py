#!/usr/bin/env python3
"""
MIT Neo4j 데이터 Augmentation 스크립트
- 500개 단위로 CSV 저장 + Neo4j 직접 Import
- data/augment/000.csv, 001.csv, ... 형태로 저장
- Neo4j driver로 직접 데이터 삽입

실행:
  make seed-neo4j                    # 기본 실행
  make seed-neo4j -- --clean         # augment 폴더 정리
  make seed-neo4j -- --records=1000  # 1000개 레코드 생성
  make seed-neo4j -- --csv           # CSV 파일도 저장
  make seed-neo4j -- --no-import     # Neo4j import 건너뛰기
"""
import os
import sys
import csv
import random
import shutil
import uuid
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from dotenv import load_dotenv


load_dotenv()

# ============================================
# CLI 파서
# ============================================
def parse_args() -> argparse.Namespace:
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="Neo4j 시드 데이터 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python seeds/seed_neo4j.py                  # 기본 실행 (10000 레코드)
  python seeds/seed_neo4j.py --clean          # augment 폴더 정리
  python seeds/seed_neo4j.py --records 1000   # 1000개만 생성
  python seeds/seed_neo4j.py --csv            # CSV 파일도 저장
  python seeds/seed_neo4j.py --no-import      # Neo4j import 건너뛰기
        """
    )
    parser.add_argument("--clean", action="store_true",
                        help="augment 폴더 정리 후 종료")
    parser.add_argument("--records", type=int, default=10000,
                        help="생성할 레코드 수 (기본: 10000)")
    parser.add_argument("--batch", type=int, default=500,
                        help="배치 크기 (기본: 500)")
    parser.add_argument("--csv", action="store_true",
                        help="CSV 파일 저장")
    parser.add_argument("--no-import", action="store_true", dest="no_import",
                        help="Neo4j import 건너뛰기")
    parser.add_argument("--no-clear", action="store_true", dest="no_clear",
                        help="DB 초기화 건너뛰기")
    parser.add_argument("--seed", type=int, default=42,
                        help="랜덤 시드 (기본: 42, 0이면 랜덤)")
    return parser.parse_args()

# ============================================
# 설정
# ============================================

# Neo4j 연결 설정 (환경변수)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# 출력 경로 (프로젝트 루트의 data/augment)
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "augment"

# ============================================
# 프로그레스 바 유틸리티
# ============================================
def print_progress(current: int, total: int, batch_num: int, bar_length: int = 30) -> None:
    """같은 줄에서 업데이트되는 프로그레스 바 출력"""
    percent = current / total
    filled = int(bar_length * percent)
    bar = "█" * filled + "░" * (bar_length - filled)
    sys.stdout.write(f"\r[{bar}] {percent*100:5.1f}% ({current:,}/{total:,}) - 배치 {batch_num:03d}")
    sys.stdout.flush()

def print_progress_done() -> None:
    """프로그레스 완료 후 줄바꿈"""
    print()  # 줄바꿈

# ============================================
# 한국어 데이터 풀
# ============================================
TEAM_NAMES = [
    "개발팀", "프론트엔드팀", "백엔드팀", "인프라팀", "데이터팀",
    "마케팅팀", "브랜드팀", "퍼포먼스마케팅팀", "콘텐츠팀", "PR팀",
    "기획팀", "서비스기획팀", "전략기획팀", "UX팀", "UI팀",
    "디자인팀", "프로덕트팀", "QA팀", "보안팀", "HR팀",
    "영업팀", "CS팀", "운영팀", "재무팀", "법무팀",
    "AI팀", "ML팀", "플랫폼팀", "모바일팀", "웹팀",
]

TEAM_DESCRIPTIONS = [
    "핵심 서비스 개발 담당", "사용자 경험 최적화", "서버 및 API 개발",
    "클라우드 인프라 관리", "데이터 파이프라인 구축", "브랜드 인지도 향상",
    "디지털 광고 운영", "콘텐츠 제작 및 배포", "서비스 기획 및 로드맵",
    "사용자 리서치 및 UX 설계", "비주얼 디자인", "제품 전략 수립",
    "품질 보증 및 테스트", "보안 정책 수립", "인재 채용 및 관리",
]

FIRST_NAMES = [
    "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임",
    "한", "오", "서", "신", "권", "황", "안", "송", "류", "홍",
]

LAST_NAMES = [
    "윤성", "동현", "도훈", "수효", "미란", "예찬", "성욱", "하윤",
    "주원", "지민", "지호", "수아", "지훈", "다은", "준서", "채원",
    "현우", "지원", "건우", "소율", "우진", "예은", "승현", "수빈",
]

ROLES = ["개발", "기획", "디자인", "마케팅", "데이터", "인프라", "QA", "PM"]

MEETING_TITLES = [
    "{quarter} 스프린트 킥오프",
    "{quarter} OKR 수립 회의",
    "{feature} 기능 리뷰",
    "{feature} 설계 검토",
    "주간 스탠드업",
    "월간 회고",
    "{topic} 논의",
    "{topic} 결정 회의",
    "인터뷰 디브리핑",
    "장애 포스트모템",
    "기술 부채 검토",
    "로드맵 수립",
    "예산 검토 회의",
    "파트너십 논의",
    "신규 프로젝트 착수",
]

FEATURES = [
    "인증", "결제", "알림", "검색", "대시보드", "리포트",
    "사용자 관리", "권한 설정", "API", "모바일 앱",
    "데이터 파이프라인", "실시간 처리", "캐싱", "로깅",
]

TOPICS = [
    "마이그레이션", "성능 최적화", "보안 강화", "UX 개선",
    "비용 절감", "프로세스 개선", "도구 도입", "팀 구조",
    "채용 계획", "교육 프로그램", "기술 스택", "아키텍처",
]

QUARTERS = ["Q1", "Q2", "Q3", "Q4", "상반기", "하반기", "1월", "2월", "3월"]

MEETING_STATUSES = ["scheduled", "ongoing", "completed", "in_review", "confirmed", "cancelled"]

AGENDA_TOPICS = [
    "{feature} 스펙 확정",
    "{feature} 일정 논의",
    "{topic} 방안 검토",
    "{topic} 우선순위 결정",
    "리소스 배분",
    "마일스톤 설정",
    "기술적 의사결정",
    "디자인 리뷰",
    "테스트 전략",
    "배포 계획",
    "모니터링 방안",
    "문서화 계획",
]

DECISION_TEMPLATES = [
    "{feature}은(는) {tech}로 구현",
    "{topic} {duration} 내 완료 목표",
    "{resource} {amount} 배정",
    "{approach} 방식으로 진행",
    "{tool} 도입 확정",
    "매주 {day}에 {activity} 진행",
    "{metric} {target} 목표 설정",
    "{phase} 단계로 나눠서 진행",
]

TECHS = ["React", "Vue", "Next.js", "FastAPI", "Django", "Spring", "Go", "Rust", "Kafka", "Redis", "PostgreSQL", "MongoDB"]
DURATIONS = ["1주", "2주", "1개월", "2개월", "분기 내", "상반기 내"]
RESOURCES = ["개발 인력", "예산", "서버 리소스", "디자인 리소스"]
AMOUNTS = ["2명", "3명", "5명", "1000만원", "3000만원", "5000만원", "10대", "20대"]
APPROACHES = ["애자일", "워터폴", "하이브리드", "린", "스크럼"]
TOOLS = ["Jira", "Notion", "Slack", "Figma", "GitHub", "GitLab", "Datadog", "Sentry"]
DAYS = ["월요일", "화요일", "수요일", "목요일", "금요일"]
ACTIVITIES = ["스탠드업", "코드 리뷰", "디자인 크리틱", "회고", "데모"]
METRICS = ["테스트 커버리지", "응답 시간", "에러율", "DAU", "전환율"]
TARGETS = ["80% 이상", "90% 이상", "100ms 이하", "1% 이하", "10% 증가", "20% 개선"]
PHASES = ["3", "4", "5", "알파/베타/정식", "POC/MVP/정식"]

DECISION_STATUSES = ["draft", "latest", "outdated", "rejected"]
DECISION_STATUS_WEIGHTS = [0.2, 0.5, 0.2, 0.1]

ACTION_ITEM_TITLES = [
    "{feature} 개발",
    "{feature} 문서 작성",
    "{feature} 테스트 코드 작성",
    "{topic} 조사",
    "{topic} 보고서 작성",
    "{tool} 설정",
    "{tool} 연동",
    "디자인 시안 제작",
    "프로토타입 제작",
    "성능 테스트",
    "보안 점검",
    "코드 리뷰",
    "배포 스크립트 작성",
    "모니터링 대시보드 구성",
]

ACTION_ITEM_STATUSES = ["pending", "in_progress", "completed", "cancelled"]
ACTION_ITEM_STATUS_WEIGHTS = [0.3, 0.3, 0.3, 0.1]

MEMBER_ROLES = ["owner", "admin", "member"]
MEMBER_ROLE_WEIGHTS = [0.1, 0.2, 0.7]

PARTICIPANT_ROLES = ["host", "participant"]
PARTICIPANT_ROLE_WEIGHTS = [0.2, 0.8]

APPROVAL_STATUSES = ["pending", "approved", "rejected"]
APPROVAL_STATUS_WEIGHTS = [0.2, 0.7, 0.1]


# ============================================
# 유틸리티 함수
# ============================================
def generate_uuid() -> str:
    return str(uuid.uuid4())[:8]


def random_datetime(start_year: int = 2023, end_year: int = 2025) -> datetime:
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    random_seconds = random.randint(0, 86400)
    return start + timedelta(days=random_days, seconds=random_seconds)


def format_datetime(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def weighted_choice(choices: list, weights: list) -> Any:
    return random.choices(choices, weights=weights, k=1)[0]


def fill_template(template: str) -> str:
    return template.format(
        feature=random.choice(FEATURES),
        topic=random.choice(TOPICS),
        quarter=random.choice(QUARTERS),
        tech=random.choice(TECHS),
        duration=random.choice(DURATIONS),
        resource=random.choice(RESOURCES),
        amount=random.choice(AMOUNTS),
        approach=random.choice(APPROACHES),
        tool=random.choice(TOOLS),
        day=random.choice(DAYS),
        activity=random.choice(ACTIVITIES),
        metric=random.choice(METRICS),
        target=random.choice(TARGETS),
        phase=random.choice(PHASES),
    )


# ============================================
# 데이터 생성 클래스
# ============================================
class DataGenerator:
    def __init__(self):
        self.teams: list[dict] = []
        self.users: list[dict] = []
        self.meetings: list[dict] = []
        self.agendas: list[dict] = []
        self.decisions: list[dict] = []
        self.action_items: list[dict] = []

        self.member_of: list[dict] = []
        self.hosts: list[dict] = []
        self.participated_in: list[dict] = []
        self.contains: list[dict] = []
        self.has_decision: list[dict] = []
        self.reviewed: list[dict] = []
        self.supersedes: list[dict] = []
        self.triggers: list[dict] = []
        self.assigned_to: list[dict] = []

        self.record_count = 0

    def generate_team(self) -> dict:
        team_id = f"team-{generate_uuid()}"
        team = {
            "id": team_id,
            "name": f"{random.choice(TEAM_NAMES)}-{generate_uuid()[:4]}",
            "description": random.choice(TEAM_DESCRIPTIONS),
        }
        self.teams.append(team)
        self.record_count += 1
        return team

    def generate_user(self) -> dict:
        user_id = f"user-{generate_uuid()}"
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        role = random.choice(ROLES)
        user = {
            "id": user_id,
            "email": f"{first.lower()}.{last.lower()}.{generate_uuid()[:4]}@mit.com",
            "name": f"{first}{last}",
        }
        self.users.append(user)
        self.record_count += 1
        return user

    def generate_meeting(self, team_id: str) -> dict:
        meeting_id = f"meeting-{generate_uuid()}"
        scheduled = random_datetime()
        status = random.choice(MEETING_STATUSES)

        started = None
        ended = None
        transcript = None
        summary = None

        if status in ["ongoing", "completed", "in_review", "confirmed"]:
            started = scheduled + timedelta(minutes=random.randint(0, 10))
            transcript = f"회의 내용 기록... {fill_template(random.choice(MEETING_TITLES))}"

        if status in ["completed", "in_review", "confirmed"]:
            ended = started + timedelta(minutes=random.randint(30, 120))
            summary = f"주요 결정사항: {fill_template(random.choice(DECISION_TEMPLATES))}"

        meeting = {
            "id": meeting_id,
            "title": fill_template(random.choice(MEETING_TITLES)),
            "status": status,
            "description": f"{random.choice(TOPICS)} 관련 회의",
            "transcript": transcript,
            "summary": summary,
            "scheduled_at": format_datetime(scheduled),
            "started_at": format_datetime(started) if started else None,
            "ended_at": format_datetime(ended) if ended else None,
            "created_at": format_datetime(scheduled - timedelta(days=random.randint(1, 7))),
        }
        self.meetings.append(meeting)
        self.record_count += 1

        # HOSTS 관계
        self.hosts.append({"from": team_id, "to": meeting_id})
        self.record_count += 1

        return meeting

    def generate_agenda(self, meeting_id: str) -> dict:
        agenda_id = f"agenda-{generate_uuid()}"
        agenda = {
            "id": agenda_id,
            "topic": fill_template(random.choice(AGENDA_TOPICS)),
            "description": f"{random.choice(TOPICS)} 관련 안건",
            "created_at": format_datetime(random_datetime()),
        }
        self.agendas.append(agenda)
        self.record_count += 1

        # CONTAINS 관계
        self.contains.append({"from": meeting_id, "to": agenda_id})
        self.record_count += 1

        return agenda

    def generate_decision(self, agenda_id: str) -> dict:
        decision_id = f"decision-{generate_uuid()}"
        decision = {
            "id": decision_id,
            "content": fill_template(random.choice(DECISION_TEMPLATES)),
            "status": weighted_choice(DECISION_STATUSES, DECISION_STATUS_WEIGHTS),
            "context": f"{random.choice(TOPICS)} 기반 결정",
            "created_at": format_datetime(random_datetime()),
        }
        self.decisions.append(decision)
        self.record_count += 1

        # HAS_DECISION 관계
        self.has_decision.append({"from": agenda_id, "to": decision_id})
        self.record_count += 1

        return decision

    def generate_action_item(self, decision_id: str) -> dict:
        action_id = f"action-{generate_uuid()}"
        created = random_datetime()
        action_item = {
            "id": action_id,
            "title": fill_template(random.choice(ACTION_ITEM_TITLES)),
            "description": f"{random.choice(FEATURES)} 관련 작업",
            "due_date": format_datetime(created + timedelta(days=random.randint(7, 30))),
            "status": weighted_choice(ACTION_ITEM_STATUSES, ACTION_ITEM_STATUS_WEIGHTS),
            "created_at": format_datetime(created),
        }
        self.action_items.append(action_item)
        self.record_count += 1

        # TRIGGERS 관계
        self.triggers.append({"from": decision_id, "to": action_id})
        self.record_count += 1

        return action_item

    def add_member_of(self, user_id: str, team_id: str):
        self.member_of.append({
            "from": user_id,
            "to": team_id,
            "role": weighted_choice(MEMBER_ROLES, MEMBER_ROLE_WEIGHTS),
        })
        self.record_count += 1

    def add_participated_in(self, user_id: str, meeting_id: str):
        self.participated_in.append({
            "from": user_id,
            "to": meeting_id,
            "role": weighted_choice(PARTICIPANT_ROLES, PARTICIPANT_ROLE_WEIGHTS),
        })
        self.record_count += 1

    def add_reviewed(self, user_id: str, decision_id: str):
        status = weighted_choice(APPROVAL_STATUSES, APPROVAL_STATUS_WEIGHTS)
        self.reviewed.append({
            "from": user_id,
            "to": decision_id,
            "status": status,
            "responded_at": format_datetime(random_datetime()) if status != "pending" else None,
        })
        self.record_count += 1

    def add_supersedes(self, new_decision_id: str, old_decision_id: str):
        self.supersedes.append({
            "from": new_decision_id,
            "to": old_decision_id,
        })
        self.record_count += 1

    def add_assigned_to(self, user_id: str, action_id: str):
        self.assigned_to.append({
            "from": user_id,
            "to": action_id,
            "assigned_at": format_datetime(random_datetime()),
        })
        self.record_count += 1

    def generate_batch(self, target_count: int = 500):
        """하나의 배치 데이터 생성"""
        initial_count = self.record_count

        while self.record_count - initial_count < target_count:
            # 팀 생성
            team = self.generate_team()

            # 팀에 사용자 3-8명 배정
            team_users = []
            for _ in range(random.randint(3, 8)):
                user = self.generate_user()
                team_users.append(user)
                self.add_member_of(user["id"], team["id"])

            # 회의 1-3개 생성
            for _ in range(random.randint(1, 3)):
                meeting = self.generate_meeting(team["id"])

                # 회의 참여자 배정
                participants = random.sample(team_users, min(len(team_users), random.randint(2, 5)))
                for user in participants:
                    self.add_participated_in(user["id"], meeting["id"])

                # 안건 1-4개 생성
                meeting_decisions = []
                for _ in range(random.randint(1, 4)):
                    agenda = self.generate_agenda(meeting["id"])

                    # 결정사항 1-2개 생성
                    for _ in range(random.randint(1, 2)):
                        decision = self.generate_decision(agenda["id"])
                        meeting_decisions.append(decision)

                        # 승인 관계 추가
                        approvers = random.sample(participants, min(len(participants), random.randint(1, 3)))
                        for user in approvers:
                            self.add_reviewed(user["id"], decision["id"])

                        # 액션아이템 생성 (50% 확률)
                        if random.random() > 0.5:
                            action_item = self.generate_action_item(decision["id"])

                            # 담당자 배정
                            assignee = random.choice(team_users)
                            self.add_assigned_to(assignee["id"], action_item["id"])

                # SUPERSEDES 관계 (같은 안건의 결정사항 간)
                if len(meeting_decisions) >= 2 and random.random() > 0.7:
                    # outdated 결정을 latest로 대체
                    outdated = [d for d in meeting_decisions if d["status"] == "outdated"]
                    latest = [d for d in meeting_decisions if d["status"] == "latest"]
                    if outdated and latest:
                        self.add_supersedes(random.choice(latest)["id"], random.choice(outdated)["id"])

    def to_flat_data(self) -> dict:
        """노드/관계별 평면화된 데이터 반환

        Returns:
            {
                "nodes": {"teams": [...], "users": [...], ...},
                "relationships": {"member_of": [...], ...}
            }
        """
        return {
            "nodes": {
                "teams": self.teams,
                "users": self.users,
                "meetings": self.meetings,
                "agendas": self.agendas,
                "decisions": self.decisions,
                "action_items": self.action_items,
            },
            "relationships": {
                "member_of": self.member_of,
                "hosts": self.hosts,
                "participated_in": self.participated_in,
                "contains": self.contains,
                "has_decision": self.has_decision,
                "reviewed": self.reviewed,
                "supersedes": self.supersedes,
                "triggers": self.triggers,
                "assigned_to": self.assigned_to,
            },
        }

    def clear(self):
        """데이터 초기화"""
        self.teams.clear()
        self.users.clear()
        self.meetings.clear()
        self.agendas.clear()
        self.decisions.clear()
        self.action_items.clear()
        self.member_of.clear()
        self.hosts.clear()
        self.participated_in.clear()
        self.contains.clear()
        self.has_decision.clear()
        self.reviewed.clear()
        self.supersedes.clear()
        self.triggers.clear()
        self.assigned_to.clear()
        self.record_count = 0


def save_flat_batch(data: dict, first_batch: bool = False):
    """평면화된 CSV로 저장 (append 모드)

    Args:
        data: to_flat_data() 결과
        first_batch: True면 파일 새로 생성 (헤더 포함)
    """
    nodes_dir = OUTPUT_DIR / "nodes"
    rels_dir = OUTPUT_DIR / "relationships"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    rels_dir.mkdir(parents=True, exist_ok=True)

    total_rows = 0

    # 노드 저장
    for name, items in data["nodes"].items():
        if items:
            output = nodes_dir / f"{name}.csv"
            mode = "w" if first_batch else "a"
            write_header = first_batch or not output.exists()

            with open(output, mode, newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=items[0].keys())
                if write_header:
                    writer.writeheader()
                writer.writerows(items)
            total_rows += len(items)

    # 관계 저장
    for name, items in data["relationships"].items():
        if items:
            output = rels_dir / f"{name}.csv"
            mode = "w" if first_batch else "a"
            write_header = first_batch or not output.exists()

            with open(output, mode, newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=items[0].keys())
                if write_header:
                    writer.writeheader()
                writer.writerows(items)
            total_rows += len(items)

    print(f"[저장완료] nodes/*, relationships/* ({total_rows} rows)")


# ============================================
# Neo4j Import 클래스
# ============================================
class Neo4jImporter:
    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        try:
            from neo4j import GraphDatabase

            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.database = database
        except ImportError:
            print("[오류] neo4j 패키지가 설치되지 않았습니다.")
            print("       실행: pip install neo4j")
            raise
        except Exception as e:
            print(f"[오류] Neo4j 연결 실패: {e}")
            raise

    def close(self):
        self.driver.close()
        print("[Neo4j] 연결 종료")

    def clear_database(self):
        """DB 전체 초기화 (주의!)"""
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("[Neo4j] 데이터베이스 초기화 완료")

    def create_constraints(self):
        """제약조건 및 인덱스 생성"""
        constraints = [
            "CREATE CONSTRAINT team_id_unique IF NOT EXISTS FOR (t:Team) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT user_email_unique IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE",
            "CREATE CONSTRAINT meeting_id_unique IF NOT EXISTS FOR (m:Meeting) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT agenda_id_unique IF NOT EXISTS FOR (a:Agenda) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT decision_id_unique IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT actionitem_id_unique IF NOT EXISTS FOR (ai:ActionItem) REQUIRE ai.id IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX team_name_idx IF NOT EXISTS FOR (t:Team) ON (t.name)",
            "CREATE INDEX user_name_idx IF NOT EXISTS FOR (u:User) ON (u.name)",
            "CREATE INDEX meeting_status_idx IF NOT EXISTS FOR (m:Meeting) ON (m.status)",
            "CREATE INDEX decision_status_idx IF NOT EXISTS FOR (d:Decision) ON (d.status)",
            "CREATE INDEX actionitem_status_idx IF NOT EXISTS FOR (ai:ActionItem) ON (ai.status)",
        ]

        with self.driver.session(database=self.database) as session:
            for c in constraints:
                try:
                    session.run(c)
                except Exception as e:
                    print(f"[경고] 제약조건 생성 실패: {e}")

            for i in indexes:
                try:
                    session.run(i)
                except Exception as e:
                    print(f"[경고] 인덱스 생성 실패: {e}")

        print("[Neo4j] 제약조건/인덱스 생성 완료")

    def import_batch(self, generator: "DataGenerator"):
        """배치 데이터를 Neo4j에 import"""
        with self.driver.session(database=self.database) as session:
            # 노드 생성
            for team in generator.teams:
                session.run(
                    "CREATE (t:Team {id: $id, name: $name, description: $description})",
                    **team
                )

            for user in generator.users:
                session.run(
                    "CREATE (u:User {id: $id, email: $email, name: $name})",
                    **user
                )

            for meeting in generator.meetings:
                session.run("""
                    CREATE (m:Meeting {
                        id: $id, title: $title, status: $status, description: $description,
                        transcript: $transcript, summary: $summary,
                        scheduled_at: CASE WHEN $scheduled_at IS NOT NULL THEN datetime($scheduled_at) ELSE null END,
                        started_at: CASE WHEN $started_at IS NOT NULL THEN datetime($started_at) ELSE null END,
                        ended_at: CASE WHEN $ended_at IS NOT NULL THEN datetime($ended_at) ELSE null END,
                        created_at: datetime($created_at)
                    })
                """, **meeting)

            for agenda in generator.agendas:
                session.run(
                    "CREATE (a:Agenda {id: $id, topic: $topic, description: $description, created_at: datetime($created_at)})",
                    **agenda
                )

            for decision in generator.decisions:
                session.run(
                    "CREATE (d:Decision {id: $id, content: $content, status: $status, context: $context, created_at: datetime($created_at)})",
                    **decision
                )

            for action_item in generator.action_items:
                session.run("""
                    CREATE (ai:ActionItem {
                        id: $id, title: $title, description: $description,
                        due_date: CASE WHEN $due_date IS NOT NULL THEN datetime($due_date) ELSE null END,
                        status: $status, created_at: datetime($created_at)
                    })
                """, **action_item)

            # 관계 생성
            for rel in generator.member_of:
                session.run(
                    "MATCH (u:User {id: $from}), (t:Team {id: $to}) CREATE (u)-[:MEMBER_OF {role: $role}]->(t)",
                    **rel
                )

            for rel in generator.hosts:
                session.run(
                    "MATCH (t:Team {id: $from}), (m:Meeting {id: $to}) CREATE (t)-[:HOSTS]->(m)",
                    **rel
                )

            for rel in generator.participated_in:
                session.run(
                    "MATCH (u:User {id: $from}), (m:Meeting {id: $to}) CREATE (u)-[:PARTICIPATED_IN {role: $role}]->(m)",
                    **rel
                )

            for rel in generator.contains:
                session.run(
                    "MATCH (m:Meeting {id: $from}), (a:Agenda {id: $to}) CREATE (m)-[:CONTAINS]->(a)",
                    **rel
                )

            for rel in generator.has_decision:
                session.run(
                    "MATCH (a:Agenda {id: $from}), (d:Decision {id: $to}) CREATE (a)-[:HAS_DECISION]->(d)",
                    **rel
                )

            for rel in generator.reviewed:
                session.run("""
                    MATCH (u:User {id: $from}), (d:Decision {id: $to})
                    CREATE (u)-[:REVIEWED {
                        status: $status,
                        responded_at: CASE WHEN $responded_at IS NOT NULL THEN datetime($responded_at) ELSE null END
                    }]->(d)
                """, **rel)

            for rel in generator.supersedes:
                session.run(
                    "MATCH (new_d:Decision {id: $from}), (old_d:Decision {id: $to}) CREATE (new_d)-[:SUPERSEDES]->(old_d)",
                    **rel
                )

            for rel in generator.triggers:
                session.run(
                    "MATCH (d:Decision {id: $from}), (ai:ActionItem {id: $to}) CREATE (d)-[:TRIGGERS]->(ai)",
                    **rel
                )

            for rel in generator.assigned_to:
                session.run(
                    "MATCH (u:User {id: $from}), (ai:ActionItem {id: $to}) CREATE (u)-[:ASSIGNED_TO {assigned_at: datetime($assigned_at)}]->(ai)",
                    **rel
                )

    def get_stats(self) -> dict:
        """DB 통계 조회"""
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (n)
                WITH labels(n) AS labels, count(*) AS cnt
                UNWIND labels AS label
                RETURN label, sum(cnt) AS count
                ORDER BY label
            """)
            nodes = {record["label"]: record["count"] for record in result}

            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) AS type, count(*) AS count
                ORDER BY type
            """)
            rels = {record["type"]: record["count"] for record in result}

        return {"nodes": nodes, "relationships": rels}


def main():
    args = parse_args()

    # --clean 옵션: augment 폴더 정리 후 종료
    if args.clean:
        if OUTPUT_DIR.exists():
            shutil.rmtree(OUTPUT_DIR)
            print(f"[정리 완료] {OUTPUT_DIR} 삭제됨")
        else:
            print(f"[정리] {OUTPUT_DIR} 폴더가 없습니다")
        return

    # 설정값 (CLI 인자 우선)
    batch_size = args.batch
    max_records = args.records
    save_csv = args.csv
    import_to_neo4j = not args.no_import
    clear_db = not args.no_clear

    # 랜덤 시드 설정
    if args.seed != 0:
        random.seed(args.seed)

    print("=" * 60)
    print("MIT Neo4j 데이터 Augmentation")
    print("=" * 60)
    print(f"  배치 크기:     {batch_size}")
    print(f"  최대 레코드:   {max_records}")
    print(f"  CSV 저장:      {save_csv}")
    print(f"  Neo4j Import:  {import_to_neo4j}")
    if import_to_neo4j:
        print(f"  Neo4j URI:     {NEO4J_URI}")
        print(f"  Neo4j User:    {NEO4J_USER}")
        print(f"  Neo4j DB:      {NEO4J_DATABASE}")
        print(f"  DB 초기화:     {clear_db}")
    print("=" * 60)

    # 폴더 생성
    if save_csv:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Neo4j 연결
    importer = None
    if import_to_neo4j:
        try:
            importer = Neo4jImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)

            if clear_db:
                confirm = input("\n[경고] DB를 초기화하시겠습니까? (yes/no): ")
                if confirm.lower() == "yes":
                    importer.clear_database()
                else:
                    print("DB 초기화를 건너뜁니다.")

            importer.create_constraints()
        except Exception as e:
            print(f"\n[오류] Neo4j 연결 실패: {e}")
            print("--no-import 모드로 전환합니다.\n")
            importer = None

    generator = DataGenerator()
    total_records = 0
    batch_num = 0

    print("\n데이터 생성 시작...")
    try:
        while total_records < max_records:
            generator.generate_batch(batch_size)

            # CSV 저장 (평면화된 형식)
            if save_csv:
                data = generator.to_flat_data()
                save_flat_batch(data, first_batch=(batch_num == 0))

            # Neo4j Import
            if importer:
                importer.import_batch(generator)

            total_records += generator.record_count
            batch_num += 1

            generator.clear()

            # 프로그레스 바 업데이트
            print_progress(total_records, max_records, batch_num)

        # 완료 후 줄바꿈
        print_progress_done()

    except KeyboardInterrupt:
        print_progress_done()
        print("\n[중단] 사용자에 의해 중단되었습니다.")

    finally:
        # Neo4j 통계 출력
        if importer:
            print("\n[Neo4j 통계]")
            stats = importer.get_stats()
            print("  노드:")
            for label, count in stats["nodes"].items():
                print(f"    {label}: {count}")
            print("  관계:")
            for rel_type, count in stats["relationships"].items():
                print(f"    {rel_type}: {count}")
            importer.close()

    print("\n" + "=" * 60)
    print(f"완료! 총 {batch_num}개 배치, {total_records}개 레코드")
    if save_csv:
        print(f"CSV 저장 위치: {OUTPUT_DIR.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
