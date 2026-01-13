#!/bin/bash

# Claude 설정을 공유하는 새 worktree 설정 스크립트
# 사용법: ./scripts/setup-worktree-claude.sh <worktree-path> [branch-name]

set -e

WORKTREE_PATH="$1"
BRANCH_NAME="${2:-}"
MAIN_REPO="/Users/ys/Code/Mit"

if [ -z "$WORKTREE_PATH" ]; then
    echo "Usage: $0 <worktree-path> [branch-name]"
    echo "Example: $0 ../Mit-feature feature-branch"
    exit 1
fi

# Worktree 생성
if [ -n "$BRANCH_NAME" ]; then
    echo "Creating worktree at $WORKTREE_PATH for branch $BRANCH_NAME..."
    git worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
else
    echo "Creating worktree at $WORKTREE_PATH..."
    git worktree add "$WORKTREE_PATH"
fi

cd "$WORKTREE_PATH"

# .claude-shared 심볼릭 링크
echo "Setting up .claude-shared link..."
ln -s "$MAIN_REPO/.claude-shared" .claude-shared

# .claude 디렉토리 생성
echo "Setting up .claude directory..."
mkdir -p .claude

# 공유 설정 및 리소스 링크
ln -s "$PWD/.claude-shared/settings.json" .claude/settings.json
ln -s "$PWD/.claude-shared/agents" .claude/agents
ln -s "$PWD/.claude-shared/commands" .claude/commands
ln -s "$PWD/.claude-shared/mcp" .claude/mcp
ln -s "$PWD/.claude-shared/refactor" .claude/refactor
ln -s "$PWD/.claude-shared/skills" .claude/skills

# 프로젝트 문서 링크 (선택적)
for doc in "$MAIN_REPO/.claude"/*.md; do
    if [ -f "$doc" ]; then
        ln -s "$doc" ".claude/$(basename "$doc")"
    fi
done

# 로컬 설정 파일 생성 (각 worktree 독립)
cat > .claude/settings.local.json << 'EOF'
{
  "customInstructions": "",
  "mcpServers": {}
}
EOF

# 환경 변수 파일 링크 (선택사항)
if [ -f "$MAIN_REPO/.env" ]; then
    echo "Linking .env file..."
    ln -s "$MAIN_REPO/.env" .env
fi

if [ -f "$MAIN_REPO/.env.local" ]; then
    echo "Linking .env.local file..."
    ln -s "$MAIN_REPO/.env.local" .env.local
fi

# Docker 환경 변수 파일 복사
if [ -f "$MAIN_REPO/docker/.env" ]; then
    echo "Copying docker/.env file..."
    mkdir -p docker
    cp "$MAIN_REPO/docker/.env" docker/.env
fi

echo "✅ Worktree setup complete!"
echo ""
echo "Claude configuration shared from main repo:"
echo "  - settings.json (MCP servers, global config)"
echo "  - agents, commands, mcp, refactor, skills directories"
echo "  - Project documentation (.md files)"
echo ""
echo "Independent in this worktree:"
echo "  - settings.local.json (local overrides)"
echo "  - Chat history and context"
echo ""
echo "To start using this worktree:"
echo "  cd $WORKTREE_PATH"
echo "  code . # or your preferred editor"
