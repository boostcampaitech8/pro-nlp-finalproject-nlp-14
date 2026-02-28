/**
 * AI 에이전트 상수
 *
 * 멘션 가능한 AI 에이전트 목록
 */

export interface AIAgent {
  id: string;
  name: string;
  displayName: string;
  mention: string;
  description: string;
  avatarUrl?: string;
}

/**
 * 멘션 가능한 AI 에이전트 목록
 */
export const AI_AGENTS: AIAgent[] = [
  {
    id: '11111111-1111-1111-1111-111111111111', // PR #62 AGENT_USER_ID와 동일
    name: '부덕이',
    displayName: '부덕이',
    mention: '@부덕이',
    description: '이 결정 사항에 대해 궁금한 점이 있으면 언제든지 물어보세요!',
    avatarUrl: '/agent.png',
  },
];

/**
 * 기본 AI 에이전트
 */
export const DEFAULT_AI_AGENT = AI_AGENTS[0];

/**
 * 에이전트 멘션 패턴 (정규식용)
 */
export const AGENT_MENTION_PATTERN = new RegExp(
  `(${AI_AGENTS.map((a) => a.mention.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})\\b`,
  'gi'
);

/**
 * 입력 텍스트에서 에이전트 멘션 여부 확인
 */
export function hasAgentMention(text: string): boolean {
  return AGENT_MENTION_PATTERN.test(text);
}

/**
 * 입력된 @ 뒤 텍스트로 에이전트 검색
 */
export function searchAgents(query: string): AIAgent[] {
  const lowerQuery = query.toLowerCase();
  return AI_AGENTS.filter(
    (agent) =>
      agent.mention.toLowerCase().includes(`@${lowerQuery}`) ||
      agent.displayName.toLowerCase().includes(lowerQuery)
  );
}

/**
 * 에이전트 ID로 에이전트인지 확인
 */
export function isAIAgent(authorId: string): boolean {
  return AI_AGENTS.some((agent) => agent.id === authorId);
}

/**
 * 에이전트 ID로 에이전트 정보 조회
 */
export function getAIAgentById(authorId: string): AIAgent | undefined {
  return AI_AGENTS.find((agent) => agent.id === authorId);
}
