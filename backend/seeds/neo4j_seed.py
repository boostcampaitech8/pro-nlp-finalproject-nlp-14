#!/usr/bin/env python3
"""
MIT Neo4j 데이터 Augmentation 스크립트
- 500개 단위로 CSV 저장 + Neo4j 직접 Import
- data/augment/000.csv, 001.csv, ... 형태로 저장
- Neo4j driver로 직접 데이터 삽입

실행:
  make neo4j-seed                    # 기본 실행
  make neo4j-seed -- --clean         # augment 폴더 정리
  make neo4j-seed -- --records=1000  # 1000개 레코드 생성
  make neo4j-seed -- --csv           # CSV 파일도 저장
  make neo4j-seed -- --no-import     # Neo4j import 건너뛰기
"""
import os
import sys
import csv
import random
import shutil
import uuid
import argparse
import asyncio
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
  python seeds/neo4j_seed.py                  # 기본 실행 (10000 레코드)
  python seeds/neo4j_seed.py --clean          # augment 폴더 정리
  python seeds/neo4j_seed.py --records 1000   # 1000개만 생성
  python seeds/neo4j_seed.py --csv            # CSV 파일도 저장
  python seeds/neo4j_seed.py --no-import      # Neo4j import 건너뛰기
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
    # 남성 이름 (200개)
    "민준", "서준", "도윤", "예준", "시우", "하준", "주원", "지호",
    "지후", "준서", "준우", "현우", "도현", "지훈", "건우", "우진",
    "선우", "서진", "민재", "현준", "연우", "유준", "정우", "승우",
    "승현", "시윤", "준혁", "은우", "지환", "승민", "지우", "유찬",
    "윤우", "민성", "준영", "시후", "진우", "지원", "수호", "재윤",
    "시현", "동현", "수현", "태윤", "민우", "재원", "한결", "지안",
    "윤호", "민규", "태민", "규민", "성민", "성준", "성현", "민호",
    "재민", "재현", "준호", "지성", "태현", "정민", "현성", "승준",
    "동윤", "상현", "재호", "민혁", "진호", "태양", "성훈", "지완",
    "동혁", "상윤", "재혁", "민석", "진영", "태호", "성진", "지수",
    "동건", "상준", "재영", "민수", "진혁", "태준", "성호", "지혁",
    "동민", "상훈", "재준", "민찬", "진수", "태영", "성원", "지현",
    "윤성", "도훈", "예찬", "성욱", "건호", "영준", "영민", "영호",
    "영진", "영훈", "영석", "영수", "세준", "세현", "세민", "세훈",
    "기현", "기훈", "기민", "기석", "인호", "인성", "인우", "인혁",
    "용준", "용현", "용민", "용호", "경민", "경훈", "경호", "경석",
    "종현", "종민", "종훈", "종호", "원준", "원호", "원석", "원영",
    "창민", "창훈", "창호", "창현", "익준", "익현", "익호", "익수",
    "찬영", "찬호", "찬우", "찬혁", "대현", "대호", "대민", "대영",
    "형준", "형민", "형호", "형석", "광민", "광호", "광현", "광석",
    "정훈", "정호", "정현", "정석", "상민", "상호", "상석", "상진",
    "철민", "철호", "철현", "철수", "호준", "호민", "호영", "호진",
    "태성", "태훈", "태석", "태수", "진성", "진민", "진석", "진환",
    "병준", "병민", "병호", "병현", "한솔", "한빈", "한울", "한별",
    "강민", "강호", "강현", "강준", "혁준", "혁민", "혁진", "혁수",
    # 여성 이름 (200개)
    "서연", "서윤", "지유", "서현", "민서", "하은", "하윤", "윤서",
    "채원", "수아", "지아", "지윤", "은서", "다은", "예은", "예서",
    "수빈", "소율", "소윤", "지은", "채은", "유진", "윤아", "유나",
    "지현", "수연", "예진", "민지", "하린", "시은", "서은", "은지",
    "연우", "소연", "민아", "지연", "하영", "유빈", "연서", "은채",
    "소민", "민영", "지수", "하나", "유리", "연주", "유림", "은빈",
    "소영", "민정", "지민", "하늘", "유라", "연지", "유미", "은하",
    "소정", "민주", "지영", "하율", "유정", "미란", "예린", "다인",
    "서영", "연희", "은비", "소희", "미연", "하진", "예빈", "다연",
    "서정", "연아", "은정", "소현", "미정", "하선", "예나", "다현",
    "서희", "연수", "은영", "소은", "미영", "하경", "예원", "다영",
    "서인", "연정", "은주", "소진", "가은", "가영", "가연", "가인",
    "나연", "나영", "나은", "나인", "다솔", "다희", "다정", "다솜",
    "라희", "라연", "라은", "라인", "마리", "마음", "마야", "마린",
    "바다", "바람", "바른", "바롬", "사랑", "사빈", "사현", "사윤",
    "아름", "아인", "아린", "아영", "자은", "자영", "자연", "자인",
    "차은", "차영", "차연", "차인", "세아", "세연", "세은", "세인",
    "혜원", "혜진", "혜린", "혜은", "보라", "보미", "보연", "보은",
    "주아", "주연", "주은", "주인", "초아", "초연", "초은", "초롱",
    "효진", "효연", "효은", "효린", "별이", "별님", "봄이", "봄솔",
    "빛나", "빛솔", "슬아", "슬기", "슬비", "슬희", "아라", "아리",
    "아미", "아현", "이슬", "이솔", "이랑", "이안", "해나", "해린",
    "해원", "해은", "새봄", "새별", "새롬", "새미", "푸름", "푸른",
    "하람", "하랑", "하솔", "하음", "해솔", "해오름", "햇살", "희망",
    "달빛", "단비", "담비", "도담", "라온", "루다", "루리", "루비",
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
    # 기능/개발 관련 (25개)
    "{feature} 스펙 확정", "{feature} 일정 논의", "{feature} 요구사항 분석",
    "{feature} 기술 검토", "{feature} 구현 방안", "{feature} API 설계",
    "{feature} DB 스키마 설계", "{feature} UI/UX 설계", "{feature} 보안 검토",
    "{feature} 성능 요구사항", "{feature} 테스트 케이스 정의", "{feature} 릴리즈 계획",
    "{feature} 롤백 전략", "{feature} A/B 테스트 설계", "{feature} 피처 플래그 전략",
    "{feature} 의존성 분석", "{feature} 마이그레이션 계획", "{feature} 호환성 검토",
    "{feature} 문서화 범위", "{feature} 데모 준비", "{feature} 코드 리뷰 기준",
    "{feature} 모니터링 지표", "{feature} 알림 설정", "{feature} SLA 정의",
    "{feature} 운영 가이드 작성",
    # 주제/이슈 관련 (25개)
    "{topic} 방안 검토", "{topic} 우선순위 결정", "{topic} 현황 분석",
    "{topic} 개선 방향", "{topic} 리스크 평가", "{topic} 대응 전략",
    "{topic} 비용 분석", "{topic} ROI 검토", "{topic} 벤치마킹",
    "{topic} 경쟁사 분석", "{topic} 사용자 피드백 검토", "{topic} 데이터 분석",
    "{topic} 트렌드 분석", "{topic} 기술 조사", "{topic} 도구 비교",
    "{topic} 프로세스 개선", "{topic} 자동화 방안", "{topic} 효율화 전략",
    "{topic} 품질 개선", "{topic} 장애 대응", "{topic} 보안 강화",
    "{topic} 확장성 검토", "{topic} 유지보수 전략", "{topic} 기술 부채 해소",
    "{topic} 레거시 전환",
    # 프로젝트 관리 (20개)
    "리소스 배분", "마일스톤 설정", "일정 조율", "진행 상황 점검",
    "블로커 해결", "리스크 관리", "이해관계자 커뮤니케이션", "스코프 조정",
    "우선순위 재검토", "팀 역량 평가", "외부 협력 논의", "예산 검토",
    "KPI 설정", "성과 측정 방안", "회고 및 개선점", "다음 스프린트 계획",
    "릴리즈 일정 확정", "핫픽스 대응", "긴급 이슈 논의", "크로스팀 협업",
    # 기술적 의사결정 (15개)
    "기술적 의사결정", "아키텍처 리뷰", "기술 스택 선정", "인프라 구성",
    "CI/CD 파이프라인", "테스트 자동화", "코드 품질 기준", "보안 정책",
    "데이터 거버넌스", "API 버저닝 전략", "캐싱 전략", "로깅 표준",
    "에러 핸들링", "성능 최적화", "스케일링 전략",
    # 디자인/UX (10개)
    "디자인 리뷰", "UI 컴포넌트 정의", "디자인 시스템 업데이트", "접근성 검토",
    "사용성 테스트 결과", "프로토타입 피드백", "브랜드 가이드라인", "반응형 설계",
    "다크모드 지원", "국제화/지역화",
    # 운영/배포 (5개)
    "테스트 전략", "배포 계획", "모니터링 방안", "문서화 계획", "운영 이관",
]

DECISION_TEMPLATES = [
    # 기술 구현 결정 (25개)
    "{feature}은(는) {tech}로 구현",
    "{feature} 백엔드는 {tech} 기반으로 개발",
    "{feature} 프론트엔드는 {tech} 사용",
    "{feature} 데이터 저장소는 {tech} 선정",
    "{feature} 캐싱 레이어에 {tech} 도입",
    "{feature} 메시지 큐는 {tech} 활용",
    "{feature} 검색 엔진은 {tech} 적용",
    "{feature} 인증 시스템은 {tech} 기반 구축",
    "{feature} API 게이트웨이는 {tech} 사용",
    "{feature} 컨테이너 오케스트레이션은 {tech} 채택",
    "{feature} CI/CD 파이프라인은 {tech} 구성",
    "{feature} 모니터링은 {tech} 스택 사용",
    "{feature} 로깅 시스템은 {tech} 통합",
    "{feature} 테스트 프레임워크는 {tech} 선정",
    "{feature} 상태 관리는 {tech} 패턴 적용",
    "{feature} ORM은 {tech} 사용",
    "{feature} 빌드 도구는 {tech} 채택",
    "{feature} 패키지 매니저는 {tech} 통일",
    "{feature} 코드 포맷터는 {tech} 적용",
    "{feature} 린터는 {tech} 설정",
    "{feature} 문서화 도구는 {tech} 사용",
    "{feature} API 문서는 {tech} 자동 생성",
    "{feature} E2E 테스트는 {tech} 프레임워크 사용",
    "{feature} 성능 테스트는 {tech} 도구 활용",
    "{feature} 보안 스캐닝은 {tech} 도입",
    # 일정/기간 결정 (20개)
    "{topic} {duration} 내 완료 목표",
    "{feature} 개발은 {duration} 소요 예상",
    "{topic} 마이그레이션 {duration} 내 완료",
    "{feature} MVP는 {duration} 내 출시",
    "{topic} 리팩토링 {duration} 계획",
    "{feature} 베타 테스트 {duration} 진행",
    "{topic} 파일럿 운영 {duration} 실시",
    "{feature} 성능 최적화 {duration} 내 달성",
    "{topic} 기술 부채 해소 {duration} 목표",
    "{feature} 보안 강화 {duration} 내 적용",
    "{topic} 문서화 {duration} 내 완료",
    "{feature} 교육 자료 {duration} 내 준비",
    "{topic} 인수인계 {duration} 내 완료",
    "{feature} 안정화 기간 {duration} 설정",
    "{topic} 모니터링 기간 {duration} 운영",
    "{feature} A/B 테스트 {duration} 진행",
    "{topic} 데이터 수집 {duration} 실시",
    "{feature} 사용자 피드백 {duration} 수렴",
    "{topic} 개선 사항 {duration} 내 반영",
    "{feature} 정식 출시 {duration} 후 예정",
    # 리소스 배정 결정 (20개)
    "{resource} {amount} 배정",
    "{feature} 전담 {resource} {amount} 투입",
    "{topic} 지원을 위해 {resource} {amount} 할당",
    "{feature} 초기 개발에 {resource} {amount} 집중",
    "{topic} 해결을 위해 {resource} {amount} 긴급 배치",
    "{feature} 유지보수에 {resource} {amount} 상시 배치",
    "{topic} 개선에 {resource} {amount} 추가 투입",
    "{feature} QA에 {resource} {amount} 배정",
    "{topic} 연구에 {resource} {amount} 할당",
    "{feature} 운영에 {resource} {amount} 전환",
    "{topic} 자동화에 {resource} {amount} 투자",
    "{feature} 인프라에 {resource} {amount} 증설",
    "{topic} 보안에 {resource} {amount} 배정",
    "{feature} 성능 개선에 {resource} {amount} 투입",
    "{topic} 교육에 {resource} {amount} 할당",
    "{feature} 문서화에 {resource} {amount} 배정",
    "{topic} 컨설팅에 {resource} {amount} 투입",
    "{feature} 외주 개발에 {resource} {amount} 책정",
    "{topic} 파트너십에 {resource} {amount} 배정",
    "{feature} 클라우드 비용 {resource} {amount} 증액",
    # 프로세스/방법론 결정 (20개)
    "{approach} 방식으로 진행",
    "{feature} 개발은 {approach} 방법론 적용",
    "{topic} 프로젝트는 {approach} 프로세스 채택",
    "{feature} 팀은 {approach} 문화 도입",
    "{topic} 관리는 {approach} 체계 구축",
    "스프린트 주기 2주로 고정하고 {approach} 운영",
    "데일리 스탠드업 15분 이내로 {approach} 진행",
    "코드 리뷰 필수화하고 {approach} 기준 적용",
    "페어 프로그래밍 {approach} 방식 도입",
    "TDD {approach} 방식으로 개발 진행",
    "BDD {approach} 기반 테스트 작성",
    "DevOps {approach} 문화 정착",
    "GitFlow {approach} 브랜치 전략 사용",
    "트렁크 기반 개발 {approach} 방식 전환",
    "마이크로서비스 {approach} 아키텍처 채택",
    "모놀리식 우선 {approach} 전략 유지",
    "점진적 마이그레이션 {approach} 접근",
    "빅뱅 방식 대신 {approach} 단계적 전환",
    "카나리 배포 {approach} 전략 적용",
    "블루그린 배포 {approach} 방식 채택",
    # 도구/시스템 도입 결정 (15개)
    "{tool} 도입 확정",
    "{feature} 관리에 {tool} 사용",
    "{topic} 추적에 {tool} 도입",
    "{feature} 협업에 {tool} 활용",
    "{topic} 분석에 {tool} 적용",
    "{feature} 자동화에 {tool} 연동",
    "{tool}과 {tool} 통합 진행",
    "{tool} 기반 워크플로우 구축",
    "{tool} 플러그인 개발 진행",
    "{tool} API 연동 구현",
    "{tool} 대시보드 구성",
    "{tool} 알림 설정 완료",
    "{tool} 권한 체계 수립",
    "{tool} 백업 정책 수립",
    "{tool} 마이그레이션 계획 수립",
    # 정기 활동 결정 (15개)
    "매주 {day}에 {activity} 진행",
    "격주 {day}에 {activity} 실시",
    "매월 첫째 주 {day}에 {activity} 개최",
    "분기별 {activity} 정례화",
    "매일 오전 {activity} 진행",
    "매일 오후 {activity} 실시",
    "주 2회 {activity} 운영",
    "필요시 {activity} 수시 진행",
    "{activity} 참여 필수화",
    "{activity} 결과 문서화 의무화",
    "{activity} 녹화 및 공유",
    "{activity} 템플릿 표준화",
    "{activity} 시간 30분 제한",
    "{activity} 사전 준비 필수",
    "{activity} 후속 액션 추적",
    # 목표/지표 설정 결정 (20개)
    "{metric} {target} 목표 설정",
    "{feature} {metric} {target} 달성 목표",
    "{topic} 개선으로 {metric} {target} 기대",
    "SLA {metric} {target} 보장",
    "SLO {metric} {target} 설정",
    "에러 버짓 {metric} {target} 허용",
    "가용성 {metric} {target} 유지",
    "응답 시간 P99 {metric} {target} 목표",
    "처리량 {metric} {target} 확보",
    "동시 접속자 {metric} {target} 지원",
    "데이터 정합성 {metric} {target} 보장",
    "배포 빈도 {metric} {target} 목표",
    "리드 타임 {metric} {target} 단축",
    "MTTR {metric} {target} 달성",
    "변경 실패율 {metric} {target} 유지",
    "고객 만족도 {metric} {target} 목표",
    "NPS {metric} {target} 달성",
    "사용자 리텐션 {metric} {target} 유지",
    "전환율 {metric} {target} 개선",
    "이탈률 {metric} {target} 감소",
    # 단계적 진행 결정 (15개)
    "{phase} 단계로 나눠서 진행",
    "{feature} 출시 {phase} 단계 계획",
    "{topic} 전환 {phase} 단계 실행",
    "Phase 1에서 핵심 기능만 {phase} 구현",
    "Phase 2에서 부가 기능 {phase} 추가",
    "Phase 3에서 최적화 {phase} 진행",
    "1차 오픈 후 피드백 반영하여 {phase} 개선",
    "MVP 출시 후 {phase} 단계 확장",
    "파일럿 성공 시 {phase} 단계 전사 확대",
    "내부 테스트 → 베타 → 정식 {phase} 순서",
    "개발 → QA → 스테이징 → 프로덕션 {phase} 배포",
    "설계 → 구현 → 테스트 → 배포 {phase} 사이클",
    "분석 → 설계 → 개발 → 검증 {phase} 프로세스",
    "AS-IS → TO-BE → 갭 분석 → 실행 {phase} 진행",
    "현황 파악 → 개선안 도출 → 적용 → 모니터링 {phase} 순환",
]

TECHS = [
    # Frontend (25개)
    "React", "Vue", "Next.js", "Nuxt.js", "Angular", "Svelte", "SvelteKit", "Solid.js",
    "Remix", "Astro", "Qwik", "Preact", "Alpine.js", "HTMX", "Lit", "Stencil",
    "React Native", "Flutter", "Ionic", "Capacitor", "Expo", "Tauri", "Electron",
    "TypeScript", "JavaScript",
    # Backend (30개)
    "FastAPI", "Django", "Flask", "Spring Boot", "Spring Cloud", "Quarkus", "Micronaut",
    "Express.js", "NestJS", "Fastify", "Koa", "Hono", "Elysia", "Bun",
    "Go", "Gin", "Echo", "Fiber", "Chi", "Rust", "Axum", "Actix", "Rocket",
    "Ruby on Rails", "Laravel", "Symfony", "ASP.NET Core", "Ktor", "Vert.x", "Helidon",
    # Database (25개)
    "PostgreSQL", "MySQL", "MariaDB", "Oracle", "SQL Server", "SQLite",
    "MongoDB", "Cassandra", "ScyllaDB", "CouchDB", "DynamoDB", "CosmosDB",
    "Redis", "Memcached", "Valkey", "KeyDB", "Dragonfly",
    "Elasticsearch", "OpenSearch", "Meilisearch", "Typesense", "Algolia",
    "Neo4j", "ArangoDB", "TigerGraph", "Dgraph", "JanusGraph",
    # Message Queue / Streaming (15개)
    "Kafka", "RabbitMQ", "Apache Pulsar", "NATS", "Redis Streams",
    "Amazon SQS", "Google Pub/Sub", "Azure Service Bus", "ActiveMQ", "ZeroMQ",
    "Apache Flink", "Apache Spark", "Apache Storm", "Apache Beam", "Redpanda",
    # Infrastructure / DevOps (25개)
    "Kubernetes", "Docker", "Podman", "Helm", "Kustomize", "ArgoCD", "Flux",
    "Terraform", "Pulumi", "Ansible", "Chef", "Puppet", "SaltStack",
    "AWS", "GCP", "Azure", "Cloudflare", "Vercel", "Netlify", "Railway",
    "Nginx", "HAProxy", "Traefik", "Envoy", "Istio", "Linkerd",
    # Monitoring / Observability (15개)
    "Prometheus", "Grafana", "Datadog", "New Relic", "Dynatrace", "Splunk",
    "Jaeger", "Zipkin", "OpenTelemetry", "Sentry", "PagerDuty", "OpsGenie",
    "ELK Stack", "Loki", "Tempo",
    # AI/ML (15개)
    "TensorFlow", "PyTorch", "JAX", "scikit-learn", "XGBoost", "LightGBM",
    "Hugging Face", "LangChain", "LlamaIndex", "OpenAI API", "Anthropic API",
    "MLflow", "Kubeflow", "Ray", "Weights & Biases",
]

DURATIONS = [
    # 단기 (10개)
    "1일", "2일", "3일", "1주", "2주", "3주", "1개월", "5주", "6주", "2개월",
    # 중기 (10개)
    "3개월", "1분기", "4개월", "5개월", "6개월", "상반기", "하반기", "2분기", "3분기", "4분기",
    # 장기 (10개)
    "1년", "1년 반", "2년", "3년", "5년", "올해 내", "내년까지", "연말까지", "연내", "차기 버전까지",
    # 상대적 (10개)
    "즉시", "ASAP", "가능한 빨리", "다음 스프린트", "다음 릴리즈",
    "다음 마일스톤", "베타 전까지", "정식 출시 전", "연말 정산 전", "감사 전까지",
]

RESOURCES = [
    # 인력 (15개)
    "개발 인력", "프론트엔드 개발자", "백엔드 개발자", "풀스택 개발자", "DevOps 엔지니어",
    "데이터 엔지니어", "ML 엔지니어", "QA 엔지니어", "보안 전문가", "DBA",
    "디자인 리소스", "UX 디자이너", "UI 디자이너", "프로덕트 디자이너", "테크니컬 라이터",
    # 예산 (10개)
    "예산", "개발 예산", "인프라 예산", "라이선스 비용", "외주 비용",
    "클라우드 비용", "마케팅 예산", "교육 예산", "도구 구매 비용", "컨설팅 비용",
    # 인프라 (15개)
    "서버 리소스", "컴퓨팅 인스턴스", "GPU 서버", "스토리지", "네트워크 대역폭",
    "CDN 용량", "데이터베이스 인스턴스", "캐시 서버", "로드밸런서", "컨테이너 클러스터",
    "CI/CD 러너", "테스트 환경", "스테이징 환경", "DR 환경", "모니터링 인프라",
]

AMOUNTS = [
    # 인원 (15개)
    "1명", "2명", "3명", "4명", "5명", "6명", "7명", "8명", "10명",
    "1팀", "2팀", "소규모 TF", "전담팀", "크로스팀", "외부 인력 포함",
    # 금액 (20개)
    "100만원", "300만원", "500만원", "1000만원", "2000만원", "3000만원", "5000만원",
    "1억원", "2억원", "3억원", "5억원", "10억원",
    "$1,000", "$5,000", "$10,000", "$50,000", "$100,000",
    "월 100만원", "월 500만원", "연 1억원",
    # 수량/용량 (15개)
    "10대", "20대", "50대", "100대", "500대",
    "100GB", "500GB", "1TB", "5TB", "10TB",
    "1000 vCPU", "5000 vCPU", "10000 RPS", "50000 RPS", "100만 MAU",
]

APPROACHES = [
    # 방법론 (15개)
    "애자일", "스크럼", "칸반", "XP", "린", "워터폴", "하이브리드", "SAFe",
    "LeSS", "Nexus", "Crystal", "DSDM", "FDD", "RAD", "스파이럴",
    # 개발 방식 (15개)
    "TDD", "BDD", "DDD", "클린 아키텍처", "헥사고날 아키텍처", "이벤트 소싱",
    "CQRS", "마이크로서비스", "모놀리식", "서버리스", "JAMstack", "모듈러 모놀리스",
    "페어 프로그래밍", "몹 프로그래밍", "트렁크 기반 개발",
    # 배포 방식 (10개)
    "블루그린 배포", "카나리 배포", "롤링 배포", "A/B 배포", "피처 플래그",
    "GitOps", "지속적 배포", "점진적 롤아웃", "섀도우 배포", "다크 런칭",
]

TOOLS = [
    # 프로젝트 관리 (15개)
    "Jira", "Linear", "Asana", "Monday.com", "ClickUp", "Shortcut", "Trello",
    "Notion", "Confluence", "Coda", "Slite", "Outline", "GitBook", "Docusaurus", "Mintlify",
    # 커뮤니케이션 (10개)
    "Slack", "Discord", "Microsoft Teams", "Zoom", "Google Meet",
    "Gather", "Loom", "Miro", "FigJam", "Whimsical",
    # 디자인 (10개)
    "Figma", "Sketch", "Adobe XD", "Framer", "Principle",
    "Zeplin", "Abstract", "InVision", "Origami", "ProtoPie",
    # 개발 도구 (20개)
    "GitHub", "GitLab", "Bitbucket", "Azure DevOps", "Gitea",
    "VS Code", "JetBrains IDE", "Neovim", "Cursor", "Windsurf",
    "Postman", "Insomnia", "Bruno", "Hoppscotch", "Thunder Client",
    "Docker Desktop", "Rancher Desktop", "Lens", "k9s", "Portainer",
    # 모니터링/분석 (15개)
    "Datadog", "Sentry", "New Relic", "Grafana Cloud", "LogRocket",
    "FullStory", "Hotjar", "Amplitude", "Mixpanel", "Segment",
    "Google Analytics", "Posthog", "Plausible", "Heap", "Pendo",
]

DAYS = [
    "월요일", "화요일", "수요일", "목요일", "금요일",
    "월요일 오전", "월요일 오후", "화요일 오전", "화요일 오후",
    "수요일 오전", "수요일 오후", "목요일 오전", "목요일 오후",
    "금요일 오전", "금요일 오후", "주초", "주중", "주말 전",
    "매일 오전 10시", "매일 오후 2시", "격주 월요일", "격주 금요일",
]

ACTIVITIES = [
    # 정기 미팅 (15개)
    "스탠드업", "데일리 싱크", "위클리 싱크", "팀 미팅", "올핸즈",
    "1:1 미팅", "스킵 레벨", "타운홀", "AMA 세션", "브라운백",
    "런치앤런", "티타임", "커피챗", "워크샵", "오프사이트",
    # 개발 활동 (15개)
    "코드 리뷰", "아키텍처 리뷰", "디자인 리뷰", "PR 리뷰", "시큐리티 리뷰",
    "페어 프로그래밍", "몹 프로그래밍", "기술 세미나", "테크 토크", "해커톤",
    "버그 바쉬", "리팩토링 데이", "문서화 데이", "기술 부채 해소", "디버깅 세션",
    # 회고/계획 (10개)
    "회고", "스프린트 회고", "프로젝트 회고", "포스트모템", "레슨런드",
    "플래닝", "스프린트 플래닝", "백로그 그루밍", "로드맵 리뷰", "OKR 체크인",
    # 데모/공유 (10개)
    "데모", "스프린트 데모", "프로덕트 데모", "기술 데모", "POC 발표",
    "지식 공유", "온보딩 세션", "핸즈온 랩", "쇼케이스", "성과 공유",
]

METRICS = [
    # 코드 품질 (10개)
    "테스트 커버리지", "코드 커버리지", "브랜치 커버리지", "뮤테이션 스코어",
    "코드 중복률", "기술 부채 지수", "코드 복잡도", "린트 에러 수",
    "보안 취약점 수", "의존성 업데이트율",
    # 성능 (15개)
    "응답 시간", "P50 레이턴시", "P95 레이턴시", "P99 레이턴시", "TTFB",
    "TPS", "RPS", "QPS", "동시 접속자 수", "처리량",
    "CPU 사용률", "메모리 사용률", "디스크 I/O", "네트워크 대역폭", "캐시 히트율",
    # 안정성 (10개)
    "에러율", "실패율", "가용성", "업타임", "MTBF",
    "MTTR", "장애 발생 건수", "롤백 빈도", "인시던트 수", "알림 노이즈율",
    # 비즈니스 (15개)
    "DAU", "WAU", "MAU", "전환율", "리텐션율",
    "이탈률", "세션 시간", "페이지뷰", "바운스율", "NPS",
    "CSAT", "CES", "LTV", "CAC", "ARR",
    # 개발 생산성 (10개)
    "배포 빈도", "리드 타임", "변경 실패율", "복구 시간", "PR 머지 시간",
    "리뷰 대기 시간", "빌드 시간", "테스트 실행 시간", "배포 시간", "온보딩 시간",
]

TARGETS = [
    # 퍼센트 (20개)
    "80% 이상", "85% 이상", "90% 이상", "95% 이상", "99% 이상", "99.9% 이상",
    "50% 개선", "30% 개선", "20% 개선", "10% 개선", "5% 개선",
    "50% 감소", "30% 감소", "20% 감소", "10% 감소", "5% 감소",
    "2배 향상", "3배 향상", "5배 향상", "10배 향상",
    # 시간 (15개)
    "100ms 이하", "200ms 이하", "500ms 이하", "1초 이하", "3초 이하",
    "1분 이내", "5분 이내", "15분 이내", "30분 이내", "1시간 이내",
    "당일 내", "24시간 이내", "48시간 이내", "1주일 이내", "즉시",
    # 수량 (15개)
    "0건", "1건 이하", "5건 이하", "10건 이하", "제로",
    "100명", "1000명", "1만명", "10만명", "100만명",
    "월 1회", "주 1회", "일 1회", "시간당 1회", "무제한",
]

PHASES = [
    # 숫자 단계 (10개)
    "2", "3", "4", "5", "6", "7", "8", "10", "12", "여러",
    # 명명된 단계 (20개)
    "알파/베타/정식", "POC/MVP/정식", "설계/개발/테스트", "분석/구현/검증",
    "파일럿/확산/정착", "도입/성장/성숙", "계획/실행/평가", "준비/실행/마무리",
    "1차/2차/3차", "Phase 1/2/3", "v1/v2/v3", "초기/중기/후기",
    "단기/중기/장기", "MVP/MLP/MMP", "내부/베타/퍼블릭", "소프트/하드 런칭",
    "개발/QA/프로덕션", "로컬/스테이징/프로덕션", "샌드박스/테스트/라이브",
    "PoC/파일럿/전사확대",
]

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

SUGGESTION_STATUSES = ["pending", "accepted", "rejected"]
SUGGESTION_STATUS_WEIGHTS = [0.4, 0.4, 0.2]

SUGGESTION_TEMPLATES = [
    "{feature} 예산 {amount}로 조정",
    "{topic} 일정 {duration}로 변경",
    "{tech} 대신 {tech} 사용 제안",
    "{metric} 목표치 {target}로 상향",
    "{resource} {amount}로 증액",
]

COMMENT_TEMPLATES = [
    "이 결정에 동의합니다",
    "{topic} 관점에서 재검토 필요",
    "{feature} 영향도 고려 부탁드립니다",
    "좋은 방향인 것 같습니다",
    "추가 논의가 필요할 것 같습니다",
    "{tech} 호환성 검증 필요",
    "@mit {topic} 관련 데이터 분석 부탁드립니다",
]


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
        self.suggestions: list[dict] = []
        self.comments: list[dict] = []

        self.member_of: list[dict] = []
        self.hosts: list[dict] = []
        self.participated_in: list[dict] = []
        self.contains: list[dict] = []
        self.has_decision: list[dict] = []
        self.reviewed: list[dict] = []
        self.supersedes: list[dict] = []
        self.triggers: list[dict] = []
        self.assigned_to: list[dict] = []
        self.decided_in: list[dict] = []
        self.approves: list[dict] = []
        self.rejects: list[dict] = []
        self.outdates: list[dict] = []
        self.suggests: list[dict] = []
        self.creates: list[dict] = []
        self.suggestion_on: list[dict] = []
        self.user_comments: list[dict] = []
        self.comment_on: list[dict] = []
        self.reply_to: list[dict] = []

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
        summary = None

        if status in ["ongoing", "completed", "in_review", "confirmed"]:
            started = scheduled + timedelta(minutes=random.randint(0, 10))

        if status in ["completed", "in_review", "confirmed"]:
            ended = started + timedelta(minutes=random.randint(30, 120))
            summary = f"주요 결정사항: {fill_template(random.choice(DECISION_TEMPLATES))}"

        meeting = {
            "id": meeting_id,
            "title": fill_template(random.choice(MEETING_TITLES)),
            "status": status,
            "description": f"{random.choice(TOPICS)} 관련 회의",
            "summary": summary,
            "team_id": team_id,
            "scheduled_at": format_datetime(scheduled),
            "started_at": format_datetime(started) if started else None,
            "ended_at": format_datetime(ended) if ended else None,
            "created_at": format_datetime(scheduled - timedelta(days=random.randint(1, 7))),
        }
        self.meetings.append(meeting)
        self.record_count += 1

        # HOSTS 관계
        self.hosts.append({"from_id": team_id, "to_id": meeting_id})
        self.record_count += 1

        return meeting

    def generate_agenda(self, meeting_id: str, team_id: str, order: int) -> dict:
        agenda_id = f"agenda-{generate_uuid()}"
        agenda = {
            "id": agenda_id,
            "topic": fill_template(random.choice(AGENDA_TOPICS)),
            "description": f"{random.choice(TOPICS)} 관련 안건",
            "team_id": team_id,
            "created_at": format_datetime(random_datetime()),
        }
        self.agendas.append(agenda)
        self.record_count += 1

        # CONTAINS 관계 (order 추가)
        self.contains.append({"from_id": meeting_id, "to_id": agenda_id, "order": order})
        self.record_count += 1

        return agenda

    def generate_decision(self, agenda_id: str, meeting_id: str, team_id: str, status: str = None) -> dict:
        """결정사항 생성

        Args:
            agenda_id: 안건 ID
            meeting_id: 회의 ID
            team_id: 팀 ID
            status: 결정 상태 (None이면 weighted_choice로 선택)
        """
        decision_id = f"decision-{generate_uuid()}"
        if status is None:
            status = weighted_choice(DECISION_STATUSES, DECISION_STATUS_WEIGHTS)

        decision = {
            "id": decision_id,
            "content": fill_template(random.choice(DECISION_TEMPLATES)),
            "status": status,
            "context": f"{random.choice(TOPICS)} 기반 결정",
            "meeting_id": meeting_id,
            "team_id": team_id,
            "created_at": format_datetime(random_datetime()),
        }
        self.decisions.append(decision)
        self.record_count += 1

        # HAS_DECISION 관계
        self.has_decision.append({"from_id": agenda_id, "to_id": decision_id})
        self.record_count += 1

        return decision

    def generate_action_item(self, decision_id: str, meeting_id: str, team_id: str) -> dict:
        action_id = f"action-{generate_uuid()}"
        created = random_datetime()
        action_item = {
            "id": action_id,
            "content": fill_template(random.choice(ACTION_ITEM_TITLES)),
            "due_date": format_datetime(created + timedelta(days=random.randint(7, 30))),
            "status": weighted_choice(ACTION_ITEM_STATUSES, ACTION_ITEM_STATUS_WEIGHTS),
            "meeting_id": meeting_id,
            "team_id": team_id,
            "created_at": format_datetime(created),
        }
        self.action_items.append(action_item)
        self.record_count += 1

        # TRIGGERS 관계
        self.triggers.append({"from_id": decision_id, "to_id": action_id})
        self.record_count += 1

        return action_item

    def add_member_of(self, user_id: str, team_id: str):
        self.member_of.append({
            "from_id": user_id,
            "to_id": team_id,
            "role": weighted_choice(MEMBER_ROLES, MEMBER_ROLE_WEIGHTS),
        })
        self.record_count += 1

    def add_participated_in(self, user_id: str, meeting_id: str):
        self.participated_in.append({
            "from_id": user_id,
            "to_id": meeting_id,
            "role": weighted_choice(PARTICIPANT_ROLES, PARTICIPANT_ROLE_WEIGHTS),
        })
        self.record_count += 1

    def add_reviewed(self, user_id: str, decision_id: str):
        """리뷰 관계 추가

        참고: 도메인 모델에서는 DecisionReview/ReviewerApproval로 관리하나,
        시드 데이터에서는 단순화된 User -> Decision 관계로 표현
        """
        status = weighted_choice(APPROVAL_STATUSES, APPROVAL_STATUS_WEIGHTS)
        self.reviewed.append({
            "from_id": user_id,
            "to_id": decision_id,
            "status": status,
            "responded_at": format_datetime(random_datetime()) if status != "pending" else None,
        })
        self.record_count += 1

    def add_supersedes(self, new_decision_id: str, old_decision_id: str):
        """SUPERSEDES 관계 추가 (new_decision이 old_decision을 대체)

        도메인 규칙: SUPERSEDES 관계 생성 시 old_decision은 outdated 상태여야 함
        """
        self.supersedes.append({
            "from_id": new_decision_id,
            "to_id": old_decision_id,
        })
        self.record_count += 1

    def add_assigned_to(self, user_id: str, action_id: str):
        self.assigned_to.append({
            "from_id": user_id,
            "to_id": action_id,
            "assigned_at": format_datetime(random_datetime()),
        })
        self.record_count += 1

    def generate_suggestion(self, user_id: str, decision_id: str, meeting_id: str, team_id: str, status: str = None) -> dict:
        """수정 제안 생성"""
        suggestion_id = f"suggestion-{generate_uuid()}"
        if status is None:
            status = weighted_choice(SUGGESTION_STATUSES, SUGGESTION_STATUS_WEIGHTS)

        suggestion = {
            "id": suggestion_id,
            "content": fill_template(random.choice(SUGGESTION_TEMPLATES)),
            "status": status,
            "author_id": user_id,
            "decision_id": decision_id,
            "meeting_id": meeting_id,
            "team_id": team_id,
            "created_at": format_datetime(random_datetime()),
        }
        self.suggestions.append(suggestion)
        self.record_count += 1

        # SUGGESTS 관계
        self.suggests.append({"from_id": user_id, "to_id": suggestion_id})
        self.record_count += 1

        # ON 관계
        self.suggestion_on.append({"from_id": suggestion_id, "to_id": decision_id})
        self.record_count += 1

        return suggestion

    def generate_comment(self, user_id: str, decision_id: str, team_id: str, parent_id: str = None) -> dict:
        """댓글 생성"""
        comment_id = f"comment-{generate_uuid()}"
        content = fill_template(random.choice(COMMENT_TEMPLATES))

        # @mit 멘션 포함 여부 (10% 확률)
        pending_agent_reply = "@mit" in content

        comment = {
            "id": comment_id,
            "content": content,
            "author_id": user_id,
            "decision_id": decision_id,
            "parent_id": parent_id,
            "pending_agent_reply": pending_agent_reply,
            "team_id": team_id,
            "created_at": format_datetime(random_datetime()),
        }
        self.comments.append(comment)
        self.record_count += 1

        # COMMENTS 관계
        self.user_comments.append({"from_id": user_id, "to_id": comment_id})
        self.record_count += 1

        # ON 관계
        self.comment_on.append({"from_id": comment_id, "to_id": decision_id})
        self.record_count += 1

        # REPLY_TO 관계 (대댓글인 경우)
        if parent_id:
            self.reply_to.append({"from_id": comment_id, "to_id": parent_id})
            self.record_count += 1

        return comment

    def add_decided_in(self, meeting_id: str, decision_id: str):
        """DECIDED_IN 관계 추가"""
        self.decided_in.append({"from_id": meeting_id, "to_id": decision_id})
        self.record_count += 1

    def add_approves(self, user_id: str, decision_id: str):
        """APPROVES 관계 추가"""
        self.approves.append({"from_id": user_id, "to_id": decision_id})
        self.record_count += 1

    def add_rejects(self, user_id: str, decision_id: str):
        """REJECTS 관계 추가"""
        self.rejects.append({"from_id": user_id, "to_id": decision_id})
        self.record_count += 1

    def add_outdates(self, new_decision_id: str, old_decision_id: str):
        """OUTDATES 관계 추가 (new_decision이 old_decision을 대체)"""
        self.outdates.append({"from_id": new_decision_id, "to_id": old_decision_id})
        self.record_count += 1

    def add_creates(self, suggestion_id: str, decision_id: str):
        """CREATES 관계 추가 (Suggestion이 새 Decision 생성)"""
        self.creates.append({"from_id": suggestion_id, "to_id": decision_id})
        self.record_count += 1

    def generate_batch(self, target_count: int = 500):
        """하나의 배치 데이터 생성

        도메인 규칙:
        - Agenda당 최대 1개의 latest Decision만 유지
        - SUPERSEDES 관계: latest -> outdated 전이 반영
        """
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
                num_agendas = random.randint(1, 4)
                for order in range(1, num_agendas + 1):
                    agenda = self.generate_agenda(meeting["id"], team["id"], order)

                    # 결정사항 1-2개 생성 (Agenda당 최대 1개만 latest)
                    num_decisions = random.randint(1, 2)
                    agenda_decisions = []
                    has_latest = False

                    for i in range(num_decisions):
                        # 첫 번째 결정만 latest 가능, 나머지는 draft/rejected/outdated
                        if i == 0:
                            status = weighted_choice(DECISION_STATUSES, DECISION_STATUS_WEIGHTS)
                            if status == "latest":
                                has_latest = True
                        else:
                            # 이미 latest가 있으면 outdated 가능, 없으면 draft/rejected만
                            if has_latest:
                                status = random.choice(["draft", "rejected", "outdated"])
                            else:
                                status = random.choice(["draft", "rejected"])

                        decision = self.generate_decision(agenda["id"], meeting["id"], team["id"], status)
                        agenda_decisions.append(decision)

                        # DECIDED_IN 관계 추가
                        self.add_decided_in(meeting["id"], decision["id"])

                        # 승인/거절 관계 추가 (APPROVES/REJECTS)
                        reviewers = random.sample(participants, min(len(participants), random.randint(1, 3)))
                        for user in reviewers:
                            # 70% 확률로 승인, 30% 확률로 거절
                            if random.random() < 0.7:
                                self.add_approves(user["id"], decision["id"])
                            else:
                                self.add_rejects(user["id"], decision["id"])
                            # 기존 REVIEWED 관계도 유지 (호환성)
                            self.add_reviewed(user["id"], decision["id"])

                        # 액션아이템 생성 (50% 확률)
                        if random.random() > 0.5:
                            action_item = self.generate_action_item(decision["id"], meeting["id"], team["id"])

                            # 담당자 배정
                            assignee = random.choice(team_users)
                            self.add_assigned_to(assignee["id"], action_item["id"])

                        # Suggestion 생성 (30% 확률, draft Decision에만)
                        if decision["status"] == "draft" and random.random() < 0.3:
                            suggester = random.choice(participants)
                            suggestion = self.generate_suggestion(
                                suggester["id"], decision["id"], meeting["id"], team["id"]
                            )

                            # accepted인 경우 새 Decision 생성 (CREATES 관계)
                            if suggestion["status"] == "accepted":
                                new_decision = self.generate_decision(
                                    agenda["id"], meeting["id"], team["id"], status="draft"
                                )
                                self.add_creates(suggestion["id"], new_decision["id"])
                                # 기존 decision을 superseded로 변경
                                decision["status"] = "superseded"

                        # Comment 생성 (40% 확률)
                        if random.random() < 0.4:
                            num_comments = random.randint(1, 3)
                            comments = []
                            for _ in range(num_comments):
                                commenter = random.choice(participants)
                                comment = self.generate_comment(
                                    commenter["id"], decision["id"], team["id"]
                                )
                                comments.append(comment)

                            # 대댓글 생성 (20% 확률)
                            if comments and random.random() < 0.2:
                                parent_comment = random.choice(comments)
                                replier = random.choice(participants)
                                self.generate_comment(
                                    replier["id"], decision["id"], team["id"], parent_id=parent_comment["id"]
                                )

                    # SUPERSEDES 관계 (draft -> superseded 전이)
                    # 새 draft가 기존 superseded를 대체
                    draft_decisions = [d for d in agenda_decisions if d["status"] == "draft"]
                    superseded_decisions = [d for d in agenda_decisions if d["status"] == "superseded"]
                    if draft_decisions and superseded_decisions:
                        for old_d in superseded_decisions:
                            self.add_supersedes(draft_decisions[0]["id"], old_d["id"])

                    # OUTDATES 관계 (latest -> outdated 전이)
                    # 새 latest가 기존 outdated를 대체
                    latest_decisions = [d for d in agenda_decisions if d["status"] == "latest"]
                    outdated_decisions = [d for d in agenda_decisions if d["status"] == "outdated"]
                    if latest_decisions and outdated_decisions:
                        for old_d in outdated_decisions:
                            self.add_outdates(latest_decisions[0]["id"], old_d["id"])

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
                "suggestions": self.suggestions,
                "comments": self.comments,
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
                "decided_in": self.decided_in,
                "approves": self.approves,
                "rejects": self.rejects,
                "outdates": self.outdates,
                "suggests": self.suggests,
                "creates": self.creates,
                "suggestion_on": self.suggestion_on,
                "user_comments": self.user_comments,
                "comment_on": self.comment_on,
                "reply_to": self.reply_to,
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
        self.suggestions.clear()
        self.comments.clear()
        self.member_of.clear()
        self.hosts.clear()
        self.participated_in.clear()
        self.contains.clear()
        self.has_decision.clear()
        self.reviewed.clear()
        self.supersedes.clear()
        self.triggers.clear()
        self.assigned_to.clear()
        self.decided_in.clear()
        self.approves.clear()
        self.rejects.clear()
        self.outdates.clear()
        self.suggests.clear()
        self.creates.clear()
        self.suggestion_on.clear()
        self.user_comments.clear()
        self.comment_on.clear()
        self.reply_to.clear()
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
# Neo4j Import 클래스 (Async + UNWIND 최적화)
# ============================================
class Neo4jImporter:
    """
    Neo4j 비동기 임포터
    - AsyncGraphDatabase 사용
    - UNWIND로 배치 쿼리 (노드/관계 타입별 1개 쿼리)
    - asyncio.gather로 병렬 실행
    """

    def __init__(self, uri: str, user: str, password: str, database: str = "neo4j"):
        try:
            from neo4j import AsyncGraphDatabase

            self.driver = AsyncGraphDatabase.driver(
                uri,
                auth=(user, password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60,
            )
            self.database = database
        except ImportError:
            print("[오류] neo4j 패키지가 설치되지 않았습니다.")
            print("       실행: pip install neo4j")
            raise
        except Exception as e:
            print(f"[오류] Neo4j 연결 실패: {e}")
            raise

    async def verify_connection(self):
        """연결 검증"""
        await self.driver.verify_connectivity()
        print("[Neo4j] 연결 검증 완료")

    async def close(self):
        await self.driver.close()
        print("[Neo4j] 연결 종료")

    async def clear_database(self):
        """DB 전체 초기화 (주의!)"""
        async with self.driver.session(database=self.database) as session:
            await session.run("MATCH (n) DETACH DELETE n")
            print("[Neo4j] 데이터베이스 초기화 완료")

    async def create_constraints(self):
        """제약조건 및 인덱스 생성"""
        constraints = [
            "CREATE CONSTRAINT team_id_unique IF NOT EXISTS FOR (t:Team) REQUIRE t.id IS UNIQUE",
            "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT user_email_unique IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE",
            "CREATE CONSTRAINT meeting_id_unique IF NOT EXISTS FOR (m:Meeting) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT agenda_id_unique IF NOT EXISTS FOR (a:Agenda) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT decision_id_unique IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT actionitem_id_unique IF NOT EXISTS FOR (ai:ActionItem) REQUIRE ai.id IS UNIQUE",
            "CREATE CONSTRAINT suggestion_id_unique IF NOT EXISTS FOR (s:Suggestion) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT comment_id_unique IF NOT EXISTS FOR (c:Comment) REQUIRE c.id IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX team_name_idx IF NOT EXISTS FOR (t:Team) ON (t.name)",
            "CREATE INDEX user_name_idx IF NOT EXISTS FOR (u:User) ON (u.name)",
            "CREATE INDEX meeting_status_idx IF NOT EXISTS FOR (m:Meeting) ON (m.status)",
            "CREATE INDEX meeting_scheduled_idx IF NOT EXISTS FOR (m:Meeting) ON (m.scheduled_at)",
            "CREATE INDEX meeting_team_idx IF NOT EXISTS FOR (m:Meeting) ON (m.team_id)",
            "CREATE INDEX agenda_team_idx IF NOT EXISTS FOR (a:Agenda) ON (a.team_id)",
            "CREATE INDEX decision_status_idx IF NOT EXISTS FOR (d:Decision) ON (d.status)",
            "CREATE INDEX decision_team_idx IF NOT EXISTS FOR (d:Decision) ON (d.team_id)",
            "CREATE INDEX actionitem_status_idx IF NOT EXISTS FOR (ai:ActionItem) ON (ai.status)",
            "CREATE INDEX actionitem_due_idx IF NOT EXISTS FOR (ai:ActionItem) ON (ai.due_date)",
            "CREATE INDEX actionitem_team_idx IF NOT EXISTS FOR (ai:ActionItem) ON (ai.team_id)",
            "CREATE INDEX suggestion_created_idx IF NOT EXISTS FOR (s:Suggestion) ON (s.created_at)",
            "CREATE INDEX suggestion_team_idx IF NOT EXISTS FOR (s:Suggestion) ON (s.team_id)",
            "CREATE INDEX comment_created_idx IF NOT EXISTS FOR (c:Comment) ON (c.created_at)",
            "CREATE INDEX comment_team_idx IF NOT EXISTS FOR (c:Comment) ON (c.team_id)",
        ]

        async with self.driver.session(database=self.database) as session:
            for c in constraints:
                try:
                    await session.run(c)
                except Exception as e:
                    print(f"[경고] 제약조건 생성 실패: {e}")

            for i in indexes:
                try:
                    await session.run(i)
                except Exception as e:
                    print(f"[경고] 인덱스 생성 실패: {e}")

        print("[Neo4j] 제약조건/인덱스 생성 완료")

    async def import_batch(self, generator: "DataGenerator"):
        """배치 데이터를 Neo4j에 import (UNWIND + 병렬, 각 쿼리는 별도 세션)"""
        # 1단계: 노드 생성 (병렬 - 각각 별도 세션 사용)
        await asyncio.gather(
            self._create_teams(generator.teams),
            self._create_users(generator.users),
            self._create_meetings(generator.meetings),
            self._create_agendas(generator.agendas),
            self._create_decisions(generator.decisions),
            self._create_action_items(generator.action_items),
            self._create_suggestions(generator.suggestions),
            self._create_comments(generator.comments),
        )

        # 2단계: 관계 생성 (노드 생성 완료 후, 병렬)
        await asyncio.gather(
            self._create_member_of(generator.member_of),
            self._create_hosts(generator.hosts),
            self._create_participated_in(generator.participated_in),
            self._create_contains(generator.contains),
            self._create_has_decision(generator.has_decision),
            self._create_reviewed(generator.reviewed),
            self._create_supersedes(generator.supersedes),
            self._create_triggers(generator.triggers),
            self._create_assigned_to(generator.assigned_to),
            self._create_decided_in(generator.decided_in),
            self._create_approves(generator.approves),
            self._create_rejects(generator.rejects),
            self._create_outdates(generator.outdates),
            self._create_suggests(generator.suggests),
            self._create_creates(generator.creates),
            self._create_suggestion_on(generator.suggestion_on),
            self._create_user_comments(generator.user_comments),
            self._create_comment_on(generator.comment_on),
            self._create_reply_to(generator.reply_to),
        )

    # ---- 노드 생성 (UNWIND, 각각 별도 세션) ----
    async def _create_teams(self, teams: list):
        if not teams:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS t
                CREATE (:Team {id: t.id, name: t.name, description: t.description})
            """, items=teams)

    async def _create_users(self, users: list):
        if not users:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS u
                CREATE (:User {id: u.id, email: u.email, name: u.name})
            """, items=users)

    async def _create_meetings(self, meetings: list):
        if not meetings:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS m
                CREATE (:Meeting {
                    id: m.id, title: m.title, status: m.status, description: m.description,
                    summary: m.summary, team_id: m.team_id,
                    scheduled_at: CASE WHEN m.scheduled_at IS NOT NULL THEN datetime(m.scheduled_at) ELSE null END,
                    started_at: CASE WHEN m.started_at IS NOT NULL THEN datetime(m.started_at) ELSE null END,
                    ended_at: CASE WHEN m.ended_at IS NOT NULL THEN datetime(m.ended_at) ELSE null END,
                    created_at: datetime(m.created_at)
                })
            """, items=meetings)

    async def _create_agendas(self, agendas: list):
        if not agendas:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS a
                CREATE (:Agenda {id: a.id, topic: a.topic, description: a.description, team_id: a.team_id, created_at: datetime(a.created_at)})
            """, items=agendas)

    async def _create_decisions(self, decisions: list):
        if not decisions:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS d
                CREATE (:Decision {id: d.id, content: d.content, status: d.status, context: d.context, meeting_id: d.meeting_id, team_id: d.team_id, created_at: datetime(d.created_at)})
            """, items=decisions)

    async def _create_action_items(self, action_items: list):
        if not action_items:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS ai
                CREATE (:ActionItem {
                    id: ai.id, content: ai.content,
                    due_date: CASE WHEN ai.due_date IS NOT NULL THEN datetime(ai.due_date) ELSE null END,
                    status: ai.status, meeting_id: ai.meeting_id, team_id: ai.team_id, created_at: datetime(ai.created_at)
                })
            """, items=action_items)

    async def _create_suggestions(self, suggestions: list):
        if not suggestions:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS s
                CREATE (:Suggestion {
                    id: s.id, content: s.content, status: s.status,
                    author_id: s.author_id, decision_id: s.decision_id,
                    meeting_id: s.meeting_id, team_id: s.team_id,
                    created_at: datetime(s.created_at)
                })
            """, items=suggestions)

    async def _create_comments(self, comments: list):
        if not comments:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS c
                CREATE (:Comment {
                    id: c.id, content: c.content, author_id: c.author_id,
                    decision_id: c.decision_id, parent_id: c.parent_id,
                    pending_agent_reply: c.pending_agent_reply, team_id: c.team_id,
                    created_at: datetime(c.created_at)
                })
            """, items=comments)

    # ---- 관계 생성 (UNWIND, 각각 별도 세션) ----
    async def _create_member_of(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (u:User {id: r.from_id}), (t:Team {id: r.to_id})
                CREATE (u)-[:MEMBER_OF {role: r.role}]->(t)
            """, items=rels)

    async def _create_hosts(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (t:Team {id: r.from_id}), (m:Meeting {id: r.to_id})
                CREATE (t)-[:HOSTS]->(m)
            """, items=rels)

    async def _create_participated_in(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (u:User {id: r.from_id}), (m:Meeting {id: r.to_id})
                CREATE (u)-[:PARTICIPATED_IN {role: r.role}]->(m)
            """, items=rels)

    async def _create_contains(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (m:Meeting {id: r.from_id}), (a:Agenda {id: r.to_id})
                CREATE (m)-[:CONTAINS {order: r.order}]->(a)
            """, items=rels)

    async def _create_has_decision(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (a:Agenda {id: r.from_id}), (d:Decision {id: r.to_id})
                CREATE (a)-[:HAS_DECISION]->(d)
            """, items=rels)

    async def _create_reviewed(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (u:User {id: r.from_id}), (d:Decision {id: r.to_id})
                CREATE (u)-[:REVIEWED {
                    status: r.status,
                    responded_at: CASE WHEN r.responded_at IS NOT NULL THEN datetime(r.responded_at) ELSE null END
                }]->(d)
            """, items=rels)

    async def _create_supersedes(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (new_d:Decision {id: r.from_id}), (old_d:Decision {id: r.to_id})
                CREATE (new_d)-[:SUPERSEDES]->(old_d)
            """, items=rels)

    async def _create_triggers(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (d:Decision {id: r.from_id}), (ai:ActionItem {id: r.to_id})
                CREATE (d)-[:TRIGGERS]->(ai)
            """, items=rels)

    async def _create_assigned_to(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (u:User {id: r.from_id}), (ai:ActionItem {id: r.to_id})
                CREATE (u)-[:ASSIGNED_TO {assigned_at: datetime(r.assigned_at)}]->(ai)
            """, items=rels)

    async def _create_decided_in(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (m:Meeting {id: r.from_id}), (d:Decision {id: r.to_id})
                CREATE (m)-[:DECIDED_IN]->(d)
            """, items=rels)

    async def _create_approves(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (u:User {id: r.from_id}), (d:Decision {id: r.to_id})
                CREATE (u)-[:APPROVES]->(d)
            """, items=rels)

    async def _create_rejects(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (u:User {id: r.from_id}), (d:Decision {id: r.to_id})
                CREATE (u)-[:REJECTS]->(d)
            """, items=rels)

    async def _create_outdates(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (new_d:Decision {id: r.from_id}), (old_d:Decision {id: r.to_id})
                CREATE (new_d)-[:OUTDATES]->(old_d)
            """, items=rels)

    async def _create_suggests(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (u:User {id: r.from_id}), (s:Suggestion {id: r.to_id})
                CREATE (u)-[:SUGGESTS]->(s)
            """, items=rels)

    async def _create_creates(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (s:Suggestion {id: r.from_id}), (d:Decision {id: r.to_id})
                CREATE (s)-[:CREATES]->(d)
            """, items=rels)

    async def _create_suggestion_on(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (s:Suggestion {id: r.from_id}), (d:Decision {id: r.to_id})
                CREATE (s)-[:ON]->(d)
            """, items=rels)

    async def _create_user_comments(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (u:User {id: r.from_id}), (c:Comment {id: r.to_id})
                CREATE (u)-[:COMMENTS]->(c)
            """, items=rels)

    async def _create_comment_on(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (c:Comment {id: r.from_id}), (d:Decision {id: r.to_id})
                CREATE (c)-[:ON]->(d)
            """, items=rels)

    async def _create_reply_to(self, rels: list):
        if not rels:
            return
        async with self.driver.session(database=self.database) as session:
            await session.run("""
                UNWIND $items AS r
                MATCH (c1:Comment {id: r.from_id}), (c2:Comment {id: r.to_id})
                CREATE (c1)-[:REPLY_TO]->(c2)
            """, items=rels)

    async def get_stats(self) -> dict:
        """DB 통계 조회"""
        async with self.driver.session(database=self.database) as session:
            result = await session.run("""
                MATCH (n)
                WITH labels(n) AS labels, count(*) AS cnt
                UNWIND labels AS label
                RETURN label, sum(cnt) AS count
                ORDER BY label
            """)
            records = await result.data()
            nodes = {r["label"]: r["count"] for r in records}

            result = await session.run("""
                MATCH ()-[r]->()
                RETURN type(r) AS type, count(*) AS count
                ORDER BY type
            """)
            records = await result.data()
            rels = {r["type"]: r["count"] for r in records}

        return {"nodes": nodes, "relationships": rels}


async def main():
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
    print("MIT Neo4j 데이터 Augmentation (Async + UNWIND)")
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
            await importer.verify_connection()

            if clear_db:
                confirm = input("\n[경고] DB를 초기화하시겠습니까? (yes/no): ")
                if confirm.lower() == "yes":
                    await importer.clear_database()
                else:
                    print("DB 초기화를 건너뜁니다.")

            await importer.create_constraints()
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

            # Neo4j Import (async)
            if importer:
                await importer.import_batch(generator)

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
            stats = await importer.get_stats()
            print("  노드:")
            for label, count in stats["nodes"].items():
                print(f"    {label}: {count}")
            print("  관계:")
            for rel_type, count in stats["relationships"].items():
                print(f"    {rel_type}: {count}")
            await importer.close()

    print("\n" + "=" * 60)
    print(f"완료! 총 {batch_num}개 배치, {total_records}개 레코드")
    if save_csv:
        print(f"CSV 저장 위치: {OUTPUT_DIR.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
