#!/usr/bin/env bash
# Install the pre-push hook so nothing reaches GitHub without the fast checks.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT_DIR/.git/hooks/pre-push"
cat > "$HOOK" <<'HOOKEOF'
#!/usr/bin/env bash
# Installed by scripts/install_git_hooks.sh. Full end-to-end runs happen in CI.
exec "$(git rev-parse --show-toplevel)/scripts/test_all.sh" --fast
HOOKEOF
chmod +x "$HOOK"
echo "pre-push hook installed: $HOOK"
