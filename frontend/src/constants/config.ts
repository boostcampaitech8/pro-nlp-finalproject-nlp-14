/**
 * 앱 설정 상수
 * 환경 변수 기반 런타임 설정값
 */

// 최대 팀원 수 (환경 변수 또는 기본값 7)
export const MAX_TEAM_MEMBERS =
  Number(import.meta.env.VITE_MAX_TEAM_MEMBERS) || 7;
