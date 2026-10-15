#!/usr/bin/env bash
# Recordatorio de la sesión de Trello para los hooks del plugin. Uso: trello-recordatorio.sh {inicio|commit}
# Solo habla en los repos de Grupo Desa: el remote origin se llama grupodesa-* o desa-*.

dir="${CLAUDE_PROJECT_DIR:-$PWD}"
remote=$(git -C "$dir" remote get-url origin 2>/dev/null) || exit 0
remote="${remote%/}"
remote="${remote%.git}"
case "${remote##*[/:]}" in
  grupodesa-*|desa-*) ;;
  *) exit 0 ;;
esac

referencia="$(cd "$(dirname "$0")/.." && pwd)/references/trello.md"

case "$1" in
  inicio)
    evento=SessionStart
    texto="Proyecto de Grupo Desa: cada sesión de trabajo va contra una tarjeta del tablero Desarrollo Interno de Trello, sin que nadie invoque nada. Antes de la primera edición de una petición de trabajo, lee $referencia y sigue «Sesión › Vincular» (no hace falta en preguntas o exploración sin cambios; con /desa:plan, como dice plan). Al terminar ese trabajo, «Sesión › Cerrar»."
    ;;
  commit)
    evento=PostToolUse
    texto="Commit hecho en un proyecto de Grupo Desa: si con él termina el trabajo de la tarjeta de Trello vinculada a la sesión, sigue «Sesión › Cerrar» de $referencia."
    ;;
  *)
    echo "uso: $0 {inicio|commit}" >&2
    exit 64
    ;;
esac

printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}\n' "$evento" "$texto"
