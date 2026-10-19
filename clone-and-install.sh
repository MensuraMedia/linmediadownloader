#!/usr/bin/env bash
#
# clone-and-install.sh — get the LinMediaDownloader source into a folder you choose,
# then install that checkout (program menu, icon, Python environment).
#
#   curl -fsSL https://raw.githubusercontent.com/MensuraMedia/linmediadownloader/feat/2.0-gtk4/clone-and-install.sh | bash
#   curl -fsSL …/clone-and-install.sh | bash -s -- ~/src/linmediadownloader     # another folder
#
# Unlike install.sh's one-command mode (a hidden copy in ~/.local/opt that it updates for
# you), this gives you a full git clone to read, change and pull yourself. The menu entry
# runs that checkout. Default folder: ~/projects/linmediadownloader.
#
# Environment: LMD_BRANCH (git branch), LMD_REPO (git URL), LMD_SKIP_APT=1 (skip system packages).
#
set -euo pipefail

REPO_URL="${LMD_REPO:-https://github.com/MensuraMedia/linmediadownloader.git}"
BRANCH="${LMD_BRANCH:-feat/2.0-gtk4}"  # 2.0 lives here until it is merged into main
TARGET="${1:-$HOME/projects/linmediadownloader}"

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null || {
    say "Installing git (may ask for your password)…"
    sudo apt-get update -qq && sudo apt-get install -y --no-install-recommends git
}

if [ -d "$TARGET/.git" ]; then
    say "$TARGET is already a clone; pulling $BRANCH…"
    git -C "$TARGET" fetch origin "$BRANCH"
    git -C "$TARGET" checkout -q "$BRANCH"
    git -C "$TARGET" pull --ff-only origin "$BRANCH" || die "Could not fast-forward $TARGET (local changes?)."
elif [ -e "$TARGET" ] && [ -n "$(ls -A "$TARGET" 2>/dev/null)" ]; then
    die "$TARGET exists and is not empty. Pass another folder: … | bash -s -- /path/to/folder"
else
    say "Cloning $REPO_URL ($BRANCH) into $TARGET…"
    mkdir -p "$(dirname "$TARGET")"
    git clone --branch "$BRANCH" "$REPO_URL" "$TARGET"
fi

say "Installing from $TARGET…"
exec bash "$TARGET/install.sh"
