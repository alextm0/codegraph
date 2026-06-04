#!/usr/bin/env sh
# Point this repo at tracked hooks in .githooks/ (strips Cursor co-author trailers).
set -e
cd "$(dirname "$0")/.."
chmod +x .githooks/commit-msg
git config core.hooksPath .githooks
echo "Installed git hooks: core.hooksPath=.githooks"
