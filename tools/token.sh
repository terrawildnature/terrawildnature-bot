#!/usr/bin/env bash
# Token storage. Each current token lives encrypted in data/<name>_token.enc
# (AES-256, key = TOKEN_KEY secret). Falls back to the <NAME>_TOKEN secret if the file is missing.
#   source tools/token.sh load [ig|threads]   -> exports IG_TOKEN / THREADS_TOKEN (masked in logs)
#   tools/token.sh save "$NEW" [ig|threads]   -> writes data/<name>_token.enc
set -euo pipefail
_dir="$(dirname "${BASH_SOURCE[0]}")/../data"

case "${1:-}" in
  load)
    _name="${2:-ig}"; _var="$(echo "$_name" | tr a-z A-Z)_TOKEN"; _file="$_dir/${_name}_token.enc"
    if [ -f "$_file" ] && [ -n "${TOKEN_KEY:-}" ]; then
      printf -v "$_var" '%s' "$(openssl enc -d -aes-256-cbc -pbkdf2 -a -A -pass env:TOKEN_KEY < "$_file")"
    fi
    if [ -z "${!_var:-}" ]; then echo "no $_var available" >&2; return 1 2>/dev/null || exit 1; fi
    echo "::add-mask::${!_var}"
    export "$_var"
    ;;
  save)
    _name="${3:-ig}"
    printf '%s' "$2" | openssl enc -e -aes-256-cbc -pbkdf2 -salt -a -A -pass env:TOKEN_KEY > "$_dir/${_name}_token.enc"
    ;;
  *)
    echo "usage: source tools/token.sh load [ig|threads] | tools/token.sh save TOKEN [ig|threads]" >&2; exit 2 ;;
esac
