#!/usr/bin/env bash
# Install the repo's git hooks into .git/hooks/. Idempotent.
#
# Installs every hook in this directory's git-hooks/ (pre-commit, pre-push) so the
# standalone repo (task1 as the root) runs the same gates the DLI wrapper runs via its
# own core.hooksPath: pre-commit = nb_audit + canvas-HTML + page-runtime guard;
# pre-push = rebase guard + SKILL consistency + layout + projection link gate.
set -e

# Anchor on this script's own dir (task1/scripts), so it works whether task1 is a subdir
# (DLI wrapper) or the repo root (the open-source release).
HERE="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_DIR="$REPO_ROOT/.git/hooks"

for name in pre-commit pre-push; do
    src="$HERE/git-hooks/$name"
    dst="$HOOK_DIR/$name"
    if [ ! -f "$src" ]; then
        echo "error: $src not found"
        exit 1
    fi
    chmod +x "$src"
    if [ -L "$dst" ]; then
        rm "$dst"
    elif [ -f "$dst" ]; then
        echo "warning: $dst already exists; moving to ${dst}.bak"
        mv "$dst" "${dst}.bak"
    fi
    ln -s "$src" "$dst"
    echo "installed: $dst -> $src"
done

echo ""
echo "Verify:"
echo "  ls -la $HOOK_DIR"
echo "  python3 $HERE/nb_audit.py            # pre-commit corruption guard"
echo "  python3 $HERE/validate_layout.py     # pre-push layout/link gate"
