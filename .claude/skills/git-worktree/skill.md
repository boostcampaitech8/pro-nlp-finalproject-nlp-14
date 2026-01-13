# Git Worktree Skill

Git worktree를 사용하여 별도의 작업 디렉토리에서 기능을 개발합니다.

## 사용 시나리오

- 새로운 기능 브랜치에서 작업할 때
- 현재 작업을 유지하면서 다른 브랜치에서 작업해야 할 때
- 코드 리뷰나 테스트를 위해 다른 브랜치를 체크아웃해야 할 때

## Worktree 생성

```bash
# 새 브랜치와 함께 worktree 생성
git worktree add -b <branch-name> <path> <base-branch>

# 예시: feat/MIT-3-add-web-vad 브랜치를 main에서 분기
git worktree add -b feat/MIT-3-add-web-vad ../mit-MIT-3 main
```

### 명명 규칙

| 항목 | 형식 | 예시 |
|------|------|------|
| 브랜치명 | `feat/<ticket>-<description>` | `feat/MIT-3-add-web-vad` |
| 디렉토리 | `../<project>-<ticket>` | `../mit-MIT-3` |

## Worktree 관리

```bash
# worktree 목록 조회
git worktree list

# worktree 삭제
git worktree remove <path>

# 강제 삭제 (변경 사항이 있을 때)
git worktree remove --force <path>
```

## 작업 흐름

1. **Worktree 생성**: 새 브랜치와 디렉토리 생성
2. **작업 디렉토리 이동**: 생성된 worktree에서 작업
3. **변경 사항 커밋**: 기능 구현 완료 후 커밋
4. **PR 생성**: 메인 브랜치로 PR
5. **Worktree 정리**: PR 머지 후 worktree 삭제

## 주의 사항

- 동일 브랜치를 여러 worktree에서 체크아웃할 수 없음
- worktree 디렉토리는 `.gitignore`에 추가 권장
- `pnpm install` 등 의존성 설치가 필요할 수 있음

## Claude Code 작업 시

worktree에서 작업할 때:

1. 현재 worktree 경로 확인: `git worktree list`
2. worktree 디렉토리로 이동하여 파일 수정
3. 커밋하지 않고 커밋 메시지만 추천 (사용자가 직접 커밋)
4. 작업 완료 후 원본 프로젝트 디렉토리로 복귀
