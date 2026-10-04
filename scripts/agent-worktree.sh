#!/usr/bin/env bash
# One git worktree per agent, so parallel agents never edit the same checkout.
#
#   scripts/agent-worktree.sh new <name> [base]   create ../<repo>.worktrees/<name> on branch agent/<name>
#   scripts/agent-worktree.sh list                show every worktree
#   scripts/agent-worktree.sh remove <name>       delete the worktree (git refuses if it has
#                                                 uncommitted changes); the branch is kept
#
# Worktrees are created with relative paths (git 2.48 or newer) so the devcontainer can
# mount them; see docs/worktrees.md for why and how to start an agent's sandbox in one.
set -euo pipefail

die() { echo "agent-worktree: $*" >&2; exit 2; }

root=$(git rev-parse --show-toplevel 2>/dev/null) || die "run this inside the repo"
# The main checkout, even when run from inside a worktree.
main=$(cd "$(git rev-parse --git-common-dir)/.." && pwd)
home="$(dirname "$main")/$(basename "$main").worktrees"

need_relative_paths() {
  # `git worktree add --relative-paths` arrived in git 2.48.
  local version major minor
  version=$(git --version | awk '{print $3}')
  major=${version%%.*}
  minor=${version#*.}
  minor=${minor%%.*}
  if [ "$major" -lt 2 ] || { [ "$major" -eq 2 ] && [ "$minor" -lt 48 ]; }; then
    die "git $version is too old; worktrees for the sandbox need git 2.48+ (--relative-paths)"
  fi
}

check_name() {
  [[ "${1:-}" =~ ^[a-z0-9][a-z0-9-]{0,39}$ ]] ||
    die "name must be 1-40 lowercase letters, digits or dashes, e.g. \"docs-fix\""
}

case "${1:-}" in
  new)
    check_name "${2:-}"
    need_relative_paths
    name=$2
    base=${3:-HEAD}
    path="$home/$name"
    [ ! -e "$path" ] || die "$path already exists"
    mkdir -p "$home"
    git -C "$root" worktree add --relative-paths -b "agent/$name" "$path" "$base"
    cat <<EOF

Worktree ready: $path (branch agent/$name)
Start the agent's sandbox in it:
  npx @devcontainers/cli@0.89.0 up --workspace-folder "$path" --mount-git-worktree-common-dir
EOF
    ;;
  list)
    git -C "$root" worktree list
    ;;
  remove)
    check_name "${2:-}"
    git -C "$root" worktree remove "$home/$2"
    echo "Removed $home/$2. Branch agent/$2 is kept; delete it with: git branch -d agent/$2"
    ;;
  *)
    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
