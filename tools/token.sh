#!/usr/bin/env bash
# Instagram token storage. The current token lives encrypted in data/ig_token.enc
# (AES-256, key = TOKEN_KEY secret). Falls back to the IG_TOKEN secret if the file is missing.
#   source tools/token.sh load   -> exports IG_TOKEN (masked in logs)
#   tools/token.sh save "$NEW"   -> writes data/ig_token.enc
set -euo pipefail
ENC_FILE="$(dirname "${BASH_SOURCE[0]}")/../data/ig_token.enc"

case "${1:-}" in
  load)
    if [ -f "$ENC_FILE" ] && [ -n "${TOKEN_KEY:-}" ]; then
      IG_TOKEN=$(openssl enc -d -aes-256-cbc -pbkdf2 -a -A -pass env:TOKEN_KEY < "$ENC_FILE")
    fi
    if [ -z "${IG_TOKEN:-}" ]; then echo "no Instagram token available" >&2; exit 1; fi
    echo "::add-mask::$IG_TOKEN"
    export IG_TOKEN
    ;;
  save)
    printf '%s' "$2" | openssl enc -e -aes-256-cbc -pbkdf2 -salt -a -A -pass env:TOKEN_KEY > "$ENC_FILE"
    ;;
  *)
    echo "usage: source tools/token.sh load | tools/token.sh save TOKEN" >&2; exit 2 ;;
esac
