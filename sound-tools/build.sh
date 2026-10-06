#!/usr/bin/env bash
# Usage: ./build.sh /path/to/speaker-rigging
# Builds dist/음향도구-통합.html and the Synology image tars (amd64, arm64).
set -euo pipefail

cd "$(dirname "$0")"
REPO="${1:?speaker-rigging 저장소 경로를 넣으세요}"
VERSION="$(date +%Y.%m.%d)"
PAGE="dist/음향도구-통합.html"

git -C "$REPO" fetch --quiet origin main claude/gallant-davinci-3jr45t
python3 build.py --repo "$REPO" --out "$PAGE"

for arch in amd64 arm64; do
  (cd server && CGO_ENABLED=0 GOOS=linux GOARCH="$arch" \
    go build -trimpath -ldflags="-s -w" -o "../build/server-linux-$arch" .)
  python3 make_image.py --arch "$arch" \
    --server "build/server-linux-$arch" --page "$PAGE" \
    --tag latest --tag "$VERSION" \
    --out "dist/sound-tools-$arch.tar"
done
