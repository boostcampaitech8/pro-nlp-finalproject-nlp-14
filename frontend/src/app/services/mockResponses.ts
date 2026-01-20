// Mock 응답 데이터 정의
// 실제 백엔드 API 연동 전까지 사용

import type { CommandField, ModalData, AgentTool } from '@/app/types/command';
import {
  PROJECT_X_BUDGET_TIMELINE,
  ACTION_ITEMS,
} from '@/app/constants/mockData';

// Mock 응답 인터페이스
export interface MockResponse {
  type: 'form' | 'direct' | 'modal';
  tool?: AgentTool;
  title?: string;
  description?: string;
  icon?: string;
  fields?: CommandField[];
  message?: string;
  previewType?: string;
  previewContent?: string;
  modalData?: ModalData;
}

// Mock 응답 데이터
export const MOCK_RESPONSES: Record<string, MockResponse> = {
  // 회의 관련 - 모달로 처리
  meeting_create: {
    type: 'modal',
    tool: 'mit_action',
    modalData: {
      modalType: 'meeting',
    },
  },

  // 검색 관련
  search: {
    type: 'form',
    tool: 'mit_search',
    title: '회의록 검색',
    description: '검색 조건을 입력해주세요',
    icon: '🔍',
    fields: [
      {
        id: 'keyword',
        label: '검색어',
        type: 'text',
        placeholder: '찾고 싶은 키워드',
        required: true,
      },
      {
        id: 'dateRange',
        label: '검색 기간',
        type: 'select',
        options: ['최근 1주일', '최근 1개월', '최근 3개월', '전체 기간'],
      },
      {
        id: 'team',
        label: '팀 필터',
        type: 'select',
        options: ['전체', '개발팀', '디자인팀', '마케팅팀'],
      },
    ],
  },

  // 예산 관련 (기획서 예시)
  budget: {
    type: 'form',
    tool: 'mit_branch',
    title: '예산 변경 제안',
    description: '예산 변경 내용을 입력해주세요',
    icon: '💰',
    fields: [
      {
        id: 'amount',
        label: '변경 금액',
        type: 'text',
        placeholder: '예: 6,000만원',
        required: true,
      },
      {
        id: 'reason',
        label: '변경 사유',
        type: 'textarea',
        placeholder: '예산 변경이 필요한 이유를 설명해주세요',
        required: true,
      },
      {
        id: 'reviewer',
        label: '리뷰어 지정',
        type: 'select',
        options: ['김OO', '이OO', '박OO', '최OO'],
      },
    ],
  },

  // Blame 이력 조회
  blame: {
    type: 'direct',
    tool: 'mit_blame',
    message: '예산 변경 이력을 조회했습니다.',
    previewType: 'timeline',
    previewContent: JSON.stringify(PROJECT_X_BUDGET_TIMELINE),
  },

  // 일정 조회
  schedule: {
    type: 'direct',
    tool: 'mit_search',
    message: '오늘 예정된 회의가 2건 있습니다.',
    previewType: 'meeting',
    previewContent: `## 오늘의 일정

### 1. 주간 팀 미팅
- 시간: 10:00 - 11:00
- 참여자: 개발팀 전원 (8명)
- 장소: 회의실 A

### 2. 프로젝트 리뷰
- 시간: 14:00 - 15:30
- 참여자: 김OO, 이OO, 박OO
- 장소: 회의실 B`,
  },

  // 팀 현황
  team_status: {
    type: 'direct',
    tool: 'mit_search',
    message: '팀 현황을 불러왔습니다.',
    previewType: 'document',
    previewContent: `## 팀 현황 요약

### 개발팀
- 총 인원: 8명
- 진행 중인 프로젝트: 3개
- 이번 주 회의: 5회

### 최근 활동
- 어제: 스프린트 회고 회의
- 그제: 기술 리뷰 세션
- 지난주: 신규 입사자 온보딩`,
  },

  // Action Items
  action_items: {
    type: 'direct',
    tool: 'mit_action',
    message: '이번 주 Action Item 목록입니다.',
    previewType: 'action-items',
    previewContent: JSON.stringify(ACTION_ITEMS),
  },

  // Merge
  merge: {
    type: 'direct',
    tool: 'mit_merge',
    message: '변경 사항이 확정되었습니다.',
    previewType: 'timeline',
  },

  // 기본 응답
  default: {
    type: 'form',
    title: '명령 상세 입력',
    description: '추가 정보가 필요합니다',
    icon: '📝',
    fields: [
      {
        id: 'detail',
        label: '상세 내용',
        type: 'textarea',
        placeholder: '원하시는 작업을 자세히 설명해주세요',
        required: true,
      },
    ],
  },
};
