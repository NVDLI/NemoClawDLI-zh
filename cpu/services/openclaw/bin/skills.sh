#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# skills.sh. Simple skill manager for OpenClaw.
#
# Skills are auto-discovered from workspace/skills/*/SKILL.md.
# This script is a convenience wrapper around filesystem operations.
# There is no registry and no apply step. Changes are live immediately.
#
# Usage:  skills.sh <command> [options]
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
WORKSPACE="${WORKSPACE:-$(dirname "$SCRIPT_DIR")}"
SKILLS_DIR="${WORKSPACE}/skills"
SNAPSHOTS_DIR="${WORKSPACE}/.skill-snapshots"
TRASH_DIR="${WORKSPACE}/.skill-trash"

# ── Style ─────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  C_G=$'\033[32m' C_Y=$'\033[33m' C_R=$'\033[31m' C_B=$'\033[1m' C_D=$'\033[2m' C_RST=$'\033[0m'
else
  C_G='' C_Y='' C_R='' C_B='' C_D='' C_RST=''
fi
ok()  { printf "  ${C_G}✓${C_RST} %s\n" "$*"; }
err() { printf "  ${C_R}✗${C_RST} %s\n" "$*" >&2; }
die() { err "$*"; exit 1; }

mkdir -p "$SKILLS_DIR"

# ── list ──────────────────────────────────────────────────────────────────
cmd_list() {
  local count=0
  printf "\n${C_B}%-24s %s${C_RST}\n" "SKILL" "DESCRIPTION"
  printf "%-24s %s\n" "$(printf '─%.0s' {1..24})" "$(printf '─%.0s' {1..50})"
  for d in "$SKILLS_DIR"/*/; do
    [[ -f "$d/SKILL.md" ]] || continue
    local name desc
    name=$(basename "$d")
    desc=$(sed -n '/^---$/,/^---$/{ /^description:/{ s/^description: *"\{0,1\}\(.*\)"\{0,1\}$/\1/; p; } }' "$d/SKILL.md" | head -1)
    printf "%-24s %s\n" "$name" "${desc:-(no description)}"
    count=$((count + 1))
  done
  echo
  printf "%d skill(s) installed.\n\n" "$count"
}

# ── add ───────────────────────────────────────────────────────────────────
cmd_add() {
  local name="" from_path="" desc=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --from) shift; from_path="$1" ;;
      --desc) shift; desc="$1" ;;
      -*) die "Unknown flag: $1" ;;
      *) name="$1" ;;
    esac
    shift
  done
  [[ -n "$name" ]] || die "Usage: skills.sh add <name> [--from DIR] [--desc TEXT]"
  [[ -d "$SKILLS_DIR/$name" ]] && die "'$name' already exists. Remove it first."

  if [[ -n "$from_path" ]]; then
    [[ -d "$from_path" ]] || die "Source must be a directory: $from_path"
    [[ -f "$from_path/SKILL.md" ]] || die "Source must contain SKILL.md"
    cp -r "$from_path" "$SKILLS_DIR/$name"
    ok "Imported '$name' from $from_path"
  else
    mkdir -p "$SKILLS_DIR/$name"
    cat > "$SKILLS_DIR/$name/SKILL.md" <<SKILL
---
name: $name
description: "${desc:-TODO: describe this skill}"
---

# ${name}

TODO: Add skill instructions here.
SKILL
    ok "Created '$name'. Edit it at $SKILLS_DIR/$name/SKILL.md"
  fi
}

# ── remove ────────────────────────────────────────────────────────────────
cmd_remove() {
  local name="${1:-}"
  [[ -n "$name" ]] || die "Usage: skills.sh remove <name>"
  [[ -d "$SKILLS_DIR/$name" ]] || die "'$name' not found."
  mkdir -p "$TRASH_DIR"
  mv "$SKILLS_DIR/$name" "$TRASH_DIR/${name}.$(date +%s)"
  ok "Removed '$name' (recoverable in .skill-trash/)"
}

# ── snapshot / restore ────────────────────────────────────────────────────
cmd_snapshot() {
  local name="${1:-}"
  [[ -n "$name" ]] || die "Usage: skills.sh snapshot <name>"
  mkdir -p "$SNAPSHOTS_DIR"
  tar czf "$SNAPSHOTS_DIR/${name}.tar.gz" -C "$WORKSPACE" skills/
  ok "Snapshot saved: $name"
}

cmd_restore() {
  local name="${1:-}"
  [[ -n "$name" ]] || die "Usage: skills.sh restore <name>"
  [[ -f "$SNAPSHOTS_DIR/${name}.tar.gz" ]] || die "Snapshot '$name' not found."
  # Backup current state first
  cmd_snapshot "_pre_restore_$(date +%s)" 2>/dev/null || true
  rm -rf "$SKILLS_DIR"
  tar xzf "$SNAPSHOTS_DIR/${name}.tar.gz" -C "$WORKSPACE"
  ok "Restored from: $name"
}

# ── seed (bulk import from directory) ─────────────────────────────────────
cmd_seed() {
  local src="${1:-}" no_clobber=false
  [[ "$2" == "--no-clobber" ]] 2>/dev/null && no_clobber=true
  [[ -n "$src" && -d "$src" ]] || die "Usage: skills.sh seed <directory> [--no-clobber]"
  local imported=0 skipped=0
  for item in "$src"/*/; do
    [[ -f "$item/SKILL.md" ]] || continue
    local name
    name=$(basename "$item")
    # Strip .skill suffix if present (from old ocstack-seed format)
    name="${name%.skill}"
    if [[ -d "$SKILLS_DIR/$name" ]] && $no_clobber; then
      skipped=$((skipped + 1)); continue
    fi
    rm -rf "$SKILLS_DIR/$name" 2>/dev/null || true
    cp -r "$item" "$SKILLS_DIR/$name"
    imported=$((imported + 1))
  done
  printf "  Seeded %d skill(s), %d skipped.\n" "$imported" "$skipped"
}

# ── help ──────────────────────────────────────────────────────────────────
cmd_help() {
  cat <<EOF
${C_B}skills.sh${C_RST} is a simple skill manager for OpenClaw.

${C_B}Commands:${C_RST}
  ${C_G}list${C_RST}                          Show installed skills
  ${C_G}add${C_RST}    <name> [--from DIR]    Create or import a skill
  ${C_G}remove${C_RST} <name>                 Remove (recoverable in .skill-trash/)
  ${C_G}snapshot${C_RST} <name>               Save all skills to a checkpoint
  ${C_G}restore${C_RST}  <name>               Restore from a checkpoint
  ${C_G}seed${C_RST}   <dir> [--no-clobber]   Bulk import skills from a directory
  ${C_G}help${C_RST}                          This message

Skills are live immediately, with no apply step needed.
Directory: $SKILLS_DIR
EOF
}

# ── dispatch ──────────────────────────────────────────────────────────────
case "${1:-help}" in
  list|ls)      cmd_list ;;
  add)          shift; cmd_add "$@" ;;
  remove|rm)    shift; cmd_remove "$@" ;;
  snapshot)     shift; cmd_snapshot "$@" ;;
  restore)      shift; cmd_restore "$@" ;;
  seed)         shift; cmd_seed "$@" ;;
  help|--help)  cmd_help ;;
  *)            die "Unknown command '$1'. Run 'skills.sh help'." ;;
esac
