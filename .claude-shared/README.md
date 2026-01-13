# Claude Shared Configuration

이 디렉토리는 모든 worktree에서 공유하는 Claude 설정과 리소스를 포함합니다.

## 구조

```
.claude-shared/
├── README.md                    # 이 파일
├── settings.json                # 공유 설정 (MCP 서버 등)
├── agents/                      # 공유 에이전트 설정
├── commands/                    # 공유 커맨드
├── mcp/                         # MCP 설정
├── refactor/                    # 리팩토링 가이드
└── skills/                      # 스킬 정의
```

## Worktree 설정 방법

새 worktree를 생성한 후:

```bash
# 1. Worktree 생성
git worktree add ../Mit-feature feature-branch

# 2. 공유 설정 심볼릭 링크
cd ../Mit-feature
ln -s ../Mit/.claude-shared .claude-shared

# 3. 로컬 .claude 디렉토리 생성
mkdir -p .claude
ln -s ../.claude-shared/settings.json .claude/settings.json
ln -s ../.claude-shared/agents .claude/agents
ln -s ../.claude-shared/commands .claude/commands
ln -s ../.claude-shared/mcp .claude/mcp
ln -s ../.claude-shared/refactor .claude/refactor
ln -s ../.claude-shared/skills .claude/skills

# 4. 로컬 설정 생성 (각 worktree 독립)
cat > .claude/settings.local.json << 'EOF'
{
  "customInstructions": "",
  "mcpServers": {}
}
EOF
```

또는 자동화 스크립트 사용:

```bash
./scripts/setup-worktree-claude.sh ../Mit-feature
```
