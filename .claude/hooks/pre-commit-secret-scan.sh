#!/usr/bin/env bash
# Hook: PreToolUse / Bash, filtrado a comandos "git commit" via el campo
# "if" del hook en .claude/settings.json.
#
# Refuerza RNF-010 (docs/SRS.md): bloquea el commit si el diff staged
# contiene patrones de secretos (API keys, private keys, passwords
# hardcodeados entre comillas).
#
# LIMITACION IMPORTANTE: este hook solo protege commits ejecutados por
# Claude Code a traves del tool Bash. NO protege commits que el usuario
# haga directamente desde su propia terminal fuera de Claude Code — para
# eso haria falta un git hook nativo (.git/hooks/pre-commit) o una
# herramienta como pre-commit/husky, que no se instala en Fase 0.

set -uo pipefail

# Patrones de alta confianza (API keys, private keys): se revisan en TODO
# el diff, tests incluidos - una key real nunca deberia aparecer ni de
# ejemplo.
high_confidence_pattern="(sk-[A-Za-zA-Z0-9]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"

# El patron generico de password= tiene falsos positivos esperables en
# fixtures de test (passwords de prueba hardcodeadas a proposito, ej.
# "correcthorsebattery"), asi que se excluyen paths de tests/ de ESTE
# patron especifico - los patrones de alta confianza arriba siguen
# aplicando ahi igual.
password_pattern="password[[:space:]]*=[[:space:]]*[\"'][^\"']{4,}[\"']"

hit=""

if git diff --cached 2>/dev/null | grep -qEi "$high_confidence_pattern"; then
  hit="1"
fi

if [ -z "$hit" ] && git diff --cached -- . ':!**/tests/**' ':!**/*test*' 2>/dev/null | grep -qEi "$password_pattern"; then
  hit="1"
fi

if [ -n "$hit" ]; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Posible secreto detectado en git diff --cached (RNF-010). Revisa el commit antes de continuar - ver docs/security/threat-model.md."}}'
else
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
fi
