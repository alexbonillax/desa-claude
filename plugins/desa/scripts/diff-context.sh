#!/usr/bin/env bash
# Contexto de cambios para /desa:review y /desa:plan. No modifica el repo.
#
#   diff-context.sh                cambios locales (ver orden de fuentes abajo)
#   diff-context.sh --path RUTA    igual, limitado a RUTA (fichero o directorio)
#   diff-context.sh --pr N         ficheros de la PR N (requiere gh)
#   diff-context.sh --repo         solo el tipo de repositorio
#
# Orden de fuentes: staged; si no hay, unstaged más los ficheros sin trackear; con el árbol
# limpio fuera de una rama de integración, la rama frente a su base (la de merge-base más
# cercana entre origin/HEAD, main, master, develop y dev; si empatan, en ese orden); si no,
# el último commit.
#
# Salida: líneas CLAVE=valor y, tras "FICHEROS:", un fichero por línea relativo a RAIZ
# ("?? " delante si está sin trackear). DIFF y DIFF_U0 (el mismo diff sin contexto, para cruzar
# líneas añadidas con la cobertura) son órdenes listas para ejecutar desde cualquier directorio
# del repo. Exit: 0 bien, 1 no es un repo git, 2 fallo de gh, 3 fallo de git,
# 64 uso incorrecto.

set -u

die() { echo "ERROR=$2"; exit "$1"; }

MODE=local
TARGET=""
case "${1:-}" in
  --repo) MODE=repo; [ $# -eq 1 ] || die 64 "argumentos de más: $*" ;;
  --pr|--path)
    [ $# -eq 2 ] && [ -n "$2" ] || die 64 "$1 necesita exactamente un valor (ruta con espacios: entre comillas)"
    MODE=${1#--}; TARGET=$2 ;;
  "") [ $# -eq 0 ] || die 64 "argumento vacío" ;;
  *) die 64 "argumento no reconocido: $1" ;;
esac

ORIG=$(pwd -P)
TOP=$(git rev-parse --show-toplevel 2>/dev/null) || die 1 "no es un repositorio git"
TOP=$(cd "$TOP" && pwd -P) || die 1 "no se puede entrar en la raíz del repositorio"
cd "$TOP" || exit 1

TMP=$(mktemp) || die 3 "no se pudo crear un fichero temporal"
trap 'rm -f "$TMP"' EXIT

g() { git -c core.quotePath=false -c core.safecrlf=false --no-optional-locks "$@"; }
quote() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"; }
is_tool() { case "$1" in .claude/*|.idea/*|.expo/*|.vscode/*|.cursor/*) return 0 ;; esac; return 1; }

repo_type() {
  if [ -f artisan ] && [ -f composer.json ]; then echo backend
  elif [ -d apps/web ] || [ -d apps/mobile ] || [ -d packages/core ]; then echo monorepo
  elif [ -f next.config.js ] || [ -f next.config.mjs ] || [ -f next.config.ts ]; then echo websites
  else echo unknown
  fi
}

REPO=$(repo_type)
echo "REPO=$REPO"
echo "RAIZ=$TOP"

if [ "$MODE" = repo ]; then
  if [ "$REPO" = monorepo ]; then
    apps=""
    [ -d apps/web ] && apps="web"
    [ -d apps/mobile ] && apps="${apps:+$apps }mobile"
    echo "APPS=$apps"
  fi
  exit 0
fi

NL_SKIPPED=0

STAGED=""; UNSTAGED=""; UNTRACKED=""; EXCLUDED=0
read_status() {
  local entry xy p orig
  g status --porcelain=v1 -z --untracked-files=all "$@" > "$TMP" 2>/dev/null || die 3 "falló: git status"
  while IFS= read -r -d '' entry; do
    xy=${entry:0:2}; p=${entry:3}
    case "$xy" in R*|C*) IFS= read -r -d '' orig ;; esac
    case "$p" in *$'\n'*) NL_SKIPPED=$((NL_SKIPPED + 1)); continue ;; esac
    if [ "$xy" = "??" ]; then
      if is_tool "$p"; then EXCLUDED=$((EXCLUDED + 1)); else UNTRACKED="$UNTRACKED$p"$'\n'; fi
    else
      [ "${xy:0:1}" != " " ] && STAGED="$STAGED$p"$'\n'
      [ "${xy:1:1}" != " " ] && UNSTAGED="$UNSTAGED$p"$'\n'
    fi
  done < "$TMP"
}

# Nombres de un git diff/diff-tree en $FILES; sale con 3 si git falla. -z va justo tras el
# subcomando: detrás de un "--" git lo tomaría como pathspec.
read_names() {
  local n sub=$1
  shift
  g "$sub" -z "$@" > "$TMP" 2>/dev/null || die 3 "falló: git $sub $*"
  FILES=""
  while IFS= read -r -d '' n; do
    case "$n" in *$'\n'*) NL_SKIPPED=$((NL_SKIPPED + 1)); continue ;; esac
    FILES="$FILES$n"$'\n'
  done < "$TMP"
}

# Rutas con cambios de todo el árbol que quedan fuera de $1, sin contar las de herramientas
# sin trackear. Un rename cuenta por sus dos rutas: puede cruzar el límite de la ruta.
dirty_outside() {
  local entry xy p orig q n=0 seen=$'\n'
  g status --porcelain=v1 -z --untracked-files=all > "$TMP" 2>/dev/null || { echo 0; return; }
  while IFS= read -r -d '' entry; do
    xy=${entry:0:2}; p=${entry:3}; orig=""
    case "$xy" in R*|C*) IFS= read -r -d '' orig ;; esac
    [ "$xy" = "??" ] && is_tool "$p" && continue
    for q in "$p" "$orig"; do
      [ -n "$q" ] || continue
      case "$q" in "$1"|"$1"/*) continue ;; esac
      case "$seen" in *$'\n'"$q"$'\n'*) continue ;; esac
      seen="$seen$q"$'\n'; n=$((n + 1))
    done
  done < "$TMP"
  echo "$n"
}

resolve_rel() {
  local t=$1 d rest abs
  case "$t" in /*) ;; *) t="$ORIG/$t" ;; esac
  while [ "${t%/}" != "$t" ] && [ "$t" != / ]; do t=${t%/}; done
  if [ -d "$t" ]; then
    abs=$(cd "$t" && pwd -P) || return 1
  else
    d=$(dirname "$t"); rest=$(basename "$t")
    while [ ! -d "$d" ]; do rest="$(basename "$d")/$rest"; d=$(dirname "$d"); done
    abs="$(cd "$d" && pwd -P)/$rest"
  fi
  if [ "$abs" = "$TOP" ]; then echo .; return 0; fi
  case "$abs" in "$TOP"/*) echo "${abs#"$TOP"/}" ;; *) return 1 ;; esac
}

pick_base() {
  local cands="" c oh mb n best="" bestn=""
  oh=$(git symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null)
  for c in $oh origin/main origin/master origin/develop origin/dev main master develop dev; do
    git rev-parse --verify -q "$c^{commit}" >/dev/null || continue
    case " $cands " in *" $c "*) continue ;; esac
    cands="$cands $c"
  done
  for c in $cands; do
    mb=$(git merge-base "$c" HEAD 2>/dev/null) || continue
    n=$(git rev-list --count "$mb..HEAD" 2>/dev/null) || continue
    if [ -z "$bestn" ] || [ "$n" -lt "$bestn" ]; then best=$c; bestn=$n; fi
  done
  if [ -n "$best" ] && [ "$bestn" -gt 0 ]; then echo "$best"; fi
}

WARN=""
PR_OK=""
PR_BASE=""
ALCANCE=""
FILES=""
DIFF_U0=""
STAGED_OK=""

if [ "$MODE" = pr ]; then
  N="${TARGET#\#}"
  case "$N" in ''|*[!0-9]*) die 64 "número de PR no válido: $TARGET" ;; esac
  FILES=$(gh pr diff "$N" --name-only 2>/dev/null) || die 2 "gh pr diff $N falló (¿gh autenticado? ¿existe la PR?)"
  FUENTE="pr:$N"
  DIFF="gh pr diff $N"
  HEAD_PR=$(gh pr view "$N" --json headRefOid -q .headRefOid 2>/dev/null)
  BASE_REF=$(gh pr view "$N" --json baseRefName -q .baseRefName 2>/dev/null)
  BASE_OID=$(gh pr view "$N" --json baseRefOid -q .baseRefOid 2>/dev/null)
  read_status
  HEAD_NOW=$(git rev-parse HEAD 2>/dev/null)
  if [ -n "$HEAD_PR" ] && [ -z "$STAGED$UNSTAGED" ] && [ "$HEAD_NOW" = "$HEAD_PR" ]; then
    PR_OK=si
    # La base es el commit de la base que ve GitHub: con origin/{base} desactualizado, el
    # merge-base sería antiguo y DIFF_U0 metería commits ajenos a la PR.
    ORIGIN_OID=""
    [ -n "$BASE_REF" ] && ORIGIN_OID=$(git rev-parse --verify -q "origin/$BASE_REF^{commit}" 2>/dev/null)
    if [ -n "$BASE_OID" ] && [ "$ORIGIN_OID" = "$BASE_OID" ]; then
      PR_BASE="origin/$BASE_REF"
    elif [ -n "$BASE_OID" ] && git cat-file -e "$BASE_OID^{commit}" 2>/dev/null; then
      PR_BASE=$BASE_OID
      [ -n "$ORIGIN_OID" ] && WARN="origin/$BASE_REF no coincide con la base actual de la PR; se usa la de GitHub (${BASE_OID:0:12})"
    elif [ -n "$BASE_OID" ]; then
      WARN="la base de la PR (${BASE_OID:0:12}) no está en local, así que no hay DIFF_U0 (git fetch origin ${BASE_REF:-su rama base})"
    elif [ -n "$ORIGIN_OID" ]; then
      PR_BASE="origin/$BASE_REF"
      WARN="gh no ha dado la base de la PR: no se ha comprobado que origin/$BASE_REF esté al día"
    else
      WARN="sin la base de la PR en local no hay DIFF_U0 (git fetch origin ${BASE_REF:-su rama base})"
    fi
    if [ -n "$PR_BASE" ] && ! git merge-base "$PR_BASE" HEAD >/dev/null 2>&1; then
      WARN="${WARN:+$WARN; }la base de la PR no tiene merge-base con HEAD en este clon (superficial: git fetch --unshallow, o fetch-depth: 0 en GitHub Actions), así que no hay DIFF_U0"
      PR_BASE=""
    fi
    [ -n "$PR_BASE" ] && DIFF_U0="git diff --unified=0 $PR_BASE...HEAD"
  elif [ -n "$HEAD_PR" ] && [ -z "$STAGED$UNSTAGED" ] && [ "$(git rev-parse -q --verify HEAD^2 2>/dev/null)" = "$HEAD_PR" ]; then
    # checkout de GitHub Actions en pull_request: HEAD es el merge de la PR sobre su base.
    PR_OK=si
    PR_BASE="HEAD^1"
    DIFF_U0="git diff --unified=0 HEAD^1 HEAD"
    WARN="HEAD es el merge commit de la PR sobre su base (checkout de GitHub Actions)"
  else
    PR_OK=no
    if [ -n "$HEAD_PR" ] && [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = true ] \
       && ! git rev-parse -q --verify HEAD^2 >/dev/null 2>&1; then
      WARN="clon superficial: no se puede comprobar si HEAD es el merge commit de la PR (en GitHub Actions, actions/checkout con fetch-depth: 2 o más)"
    fi
  fi
  if [ "$PR_OK" = si ] && [ -n "$UNTRACKED" ]; then
    WARN="${WARN:+$WARN; }hay $(printf '%s' "$UNTRACKED" | grep -c .) ficheros sin trackear en el working tree; pueden afectar a los tests de la PR"
  fi
  UNTRACKED=""
else
  PS=()
  PSTXT=""
  if [ "$MODE" = path ]; then
    REL=$(resolve_rel "$TARGET") || die 64 "la ruta está fuera del repositorio: $TARGET"
    if [ "$REL" != . ] && [ ! -e "$TOP/$REL" ] && ! git cat-file -e "HEAD:$REL" 2>/dev/null \
       && [ -z "$(g ls-files -- ":(top)$REL" 2>/dev/null)" ]; then
      die 64 "la ruta no existe ni en el árbol ni en HEAD: $TARGET"
    fi
    ALCANCE=$REL
    PS=(-- ":(top)$REL")
    PSTXT=" -- $(quote ":(top)$REL")"
  fi

  read_status ${PS[@]+"${PS[@]}"}

  if [ -n "$STAGED" ]; then
    FUENTE=staged
    FILES="$STAGED"
    DIFF="git diff --staged$PSTXT"
    DIFF_U0="git diff --staged --unified=0$PSTXT"
    BOTH=$(printf '%s' "$STAGED" | grep -Fxf <(printf '%s' "$UNSTAGED" | grep .) 2>/dev/null)
    if [ -n "$BOTH" ]; then STAGED_OK=no; else STAGED_OK=si; fi
    OUTSIDE=$(printf '%s%s' "$UNSTAGED" "$UNTRACKED" | grep . | sort -u)
    [ -n "$OUTSIDE" ] && WARN="hay $(printf '%s\n' "$OUTSIDE" | grep -c .) ficheros con cambios sin stagear o sin trackear fuera de esta revisión"
    UNTRACKED=""
  elif [ -n "$UNSTAGED$UNTRACKED" ]; then
    FUENTE=unstaged
    FILES="$UNSTAGED"
    DIFF="git diff$PSTXT"
    DIFF_U0="git diff --unified=0$PSTXT"
  else
    CUR=$(git symbolic-ref -q --short HEAD 2>/dev/null)
    OH=$(git symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null)
    BASE=""
    case " main master develop dev ${OH#origin/} " in
      *" $CUR "*) [ -n "$CUR" ] || BASE=$(pick_base) ;;
      *) BASE=$(pick_base) ;;
    esac
    if [ -n "$BASE" ]; then
      FUENTE="rama:$BASE...HEAD"
      read_names diff --name-only "$BASE...HEAD" ${PS[@]+"${PS[@]}"}
      DIFF="git diff $BASE...HEAD$PSTXT"
      DIFF_U0="git diff --unified=0 $BASE...HEAD$PSTXT"
    elif git rev-parse --verify -q HEAD~1 >/dev/null; then
      FUENTE=ultimo-commit
      read_names diff --name-only HEAD~1 HEAD ${PS[@]+"${PS[@]}"}
      DIFF="git diff HEAD~1$PSTXT"
      DIFF_U0="git diff --unified=0 HEAD~1$PSTXT"
    elif git rev-parse --verify -q HEAD >/dev/null; then
      [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = true ] \
        && die 3 "clon superficial: no se puede saber qué cambió el último commit (git fetch --unshallow)"
      FUENTE=ultimo-commit
      read_names diff-tree --root --no-commit-id --name-only -r HEAD ${PS[@]+"${PS[@]}"}
      DIFF="git show HEAD$PSTXT"
      DIFF_U0="git show --unified=0 HEAD$PSTXT"
    fi
    [ -z "$FILES" ] && FUENTE=ninguna && DIFF="" && DIFF_U0=""
  fi
  if [ "$MODE" = path ] && [ "$REL" != . ]; then
    OUT_PATH=$(dirty_outside "$REL")
    [ "$OUT_PATH" -gt 0 ] && WARN="${WARN:+$WARN; }hay $OUT_PATH ficheros con cambios sin commitear fuera de $REL, que los tests del Paso 6 también verán"
  fi
fi

ALL=$(printf '%s\n%s\n' "$FILES" "$UNTRACKED" | grep . | sort -u)

types_for() {
  case "$REPO" in
    backend|websites) [ -n "$1" ] && echo "$REPO" ;;
    monorepo)
      [ -n "$1" ] || return 0
      t=""
      printf '%s\n' "$1" | grep -qv '^apps/mobile/' && t="frontend"
      printf '%s\n' "$1" | grep -q '^apps/mobile/' && t="${t:+$t }mobile"
      echo "$t"
      ;;
    *) echo unknown ;;
  esac
}
count() { [ -z "$1" ] && echo 0 || printf '%s\n' "$1" | grep -c .; }

[ -n "$ALCANCE" ] && echo "ALCANCE=$ALCANCE"
echo "FUENTE=$FUENTE"
echo "DIFF=$DIFF"
echo "DIFF_U0=$DIFF_U0"
[ -n "$STAGED_OK" ] && echo "STAGED_LIMPIO=$STAGED_OK"
echo "TIPOS=$(types_for "$ALL")"
echo "FICHEROS=$(count "$ALL")"
echo "SIN_TRACKEAR=$(count "$UNTRACKED")"
[ "$EXCLUDED" -gt 0 ] && echo "EXCLUIDOS=$EXCLUDED (sin trackear en .claude/, .idea/, .expo/, .vscode/ o .cursor/)"
[ -n "$PR_OK" ] && echo "PR_EN_WORKTREE=$PR_OK"
[ -n "$PR_BASE" ] && echo "PR_BASE=$PR_BASE"
[ "$NL_SKIPPED" -gt 0 ] && WARN="${WARN:+$WARN; }$NL_SKIPPED ficheros con salto de línea en el nombre, no listados"
[ -n "$WARN" ] && echo "AVISO=$WARN"
echo "FICHEROS:"
[ -n "$FILES" ] && printf '%s\n' "$FILES" | grep . | sort -u
[ -n "$UNTRACKED" ] && printf '%s\n' "$UNTRACKED" | grep . | sort -u | sed 's/^/?? /'
exit 0
