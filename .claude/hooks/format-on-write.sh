#!/usr/bin/env bash
# Hook: PostToolUse / Write|Edit - formato/lint automatico.
#
# Defensivo a proposito: en Fase 0 todavia no existen pyproject.toml,
# package.json ni configuracion de ruff/eslint/prettier, asi que este
# hook nunca debe bloquear ni ensuciar la salida de Claude si la
# herramienta correspondiente no esta instalada todavia - simplemente
# no hace nada y sale con exit 0.

set -uo pipefail

# Extrae file_path del JSON de stdin. jq no esta garantizado en el entorno
# (no lo esta en esta maquina), asi que se intenta primero y se cae a
# python/python3 como fallback antes de rendirse en silencio.
extract_path='
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get("tool_input", {}).get("file_path") or d.get("tool_response", {}).get("filePath") or "")
except Exception:
    print("")
'

file=""
input_json="$(cat)"
if command -v jq >/dev/null 2>&1; then
  file=$(printf '%s' "$input_json" | jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null)
elif command -v python >/dev/null 2>&1; then
  file=$(printf '%s' "$input_json" | python -c "$extract_path" 2>/dev/null)
elif command -v python3 >/dev/null 2>&1; then
  file=$(printf '%s' "$input_json" | python3 -c "$extract_path" 2>/dev/null)
fi

[ -z "$file" ] && exit 0
[ -f "$file" ] || exit 0

case "$file" in
  *backend/*.py|*workers/*.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff format "$file" >/dev/null 2>&1 || true
      ruff check --fix "$file" >/dev/null 2>&1 || true
    fi
    ;;
  *frontend/*.ts|*frontend/*.tsx)
    if command -v prettier >/dev/null 2>&1; then
      prettier --write "$file" >/dev/null 2>&1 || true
    fi
    if command -v eslint >/dev/null 2>&1; then
      eslint --fix "$file" >/dev/null 2>&1 || true
    fi
    ;;
esac

exit 0
