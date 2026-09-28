#!/usr/bin/env bash
# Pruebas de plugins/desa/scripts/diff-context.sh sobre repos temporales.
# Uso: bash tests/diff-context.test.sh   (prueba el script con el mismo bash que ejecuta la suite)

set -u
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES \
      GIT_COMMON_DIR GIT_TEMPLATE_DIR GIT_PREFIX GIT_NAMESPACE
SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/plugins/desa/scripts/diff-context.sh"
ROOT=$(mktemp -d) || { echo "mktemp falló"; exit 1; }
[ -d "$ROOT" ] || { echo "sin directorio temporal"; exit 1; }
ROOT=$(cd "$ROOT" && pwd -P)
trap 'chmod -R u+rw "$ROOT" 2>/dev/null; rm -rf "$ROOT"' EXIT
export GIT_CEILING_DIRECTORIES="$ROOT"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
PASS=0
FAIL=0

new_repo() {
  local d="$ROOT/$1"
  mkdir -p "$d" && cd "$d" && git init -q -b main || exit 1
  shift
  for f in "$@"; do mkdir -p "$(dirname "$f")" && echo x > "$f" || exit 1; done
  git add -A && git commit -qm init || exit 1
}

run() { OUT=$("$BASH" "$SCRIPT" "$@" 2>&1); CODE=$?; }
field() { printf '%s\n' "$OUT" | sed -n "s/^$1=//p"; }

ok() { PASS=$((PASS + 1)); }
ko() { FAIL=$((FAIL + 1)); printf 'FALLO: %s\n%s\n' "$1" "$(printf '%s\n' "$OUT" | sed 's/^/    /')"; }
expect() { if printf '%s\n' "$OUT" | grep -qxF -- "$2"; then ok; else ko "$1 (esperaba: $2)"; fi; }
expect_no() { if printf '%s\n' "$OUT" | grep -qxF -- "$2"; then ko "$1 (no esperaba: $2)"; else ok; fi; }
expect_code() { if [ "$CODE" = "$2" ]; then ok; else ko "$1 (exit $CODE, esperaba $2)"; fi; }

# Ejecuta el DIFF emitido desde el directorio actual, en bash y en zsh, y exige que no salga vacío.
expect_diff_runs() {
  local cmd n
  cmd=$(field DIFF)
  n=$(bash -c "$cmd" 2>/dev/null | wc -l | tr -d ' ')
  if [ "${n:-0}" -gt 0 ]; then ok; else ko "$1: DIFF vacío o roto en bash: $cmd"; fi
  if command -v zsh >/dev/null; then
    n=$(zsh -c "$cmd" 2>/dev/null | wc -l | tr -d ' ')
    if [ "${n:-0}" -gt 0 ]; then ok; else ko "$1: DIFF vacío o roto en zsh: $cmd"; fi
  fi
}

MONO=(apps/web/src/a.js apps/mobile/b.js packages/core/c.js)

# Fuera de un repo
mkdir -p "$ROOT/fuera" && cd "$ROOT/fuera" && run
expect_code "fuera de un repo sale con 1" 1
expect "fuera de un repo" "ERROR=no es un repositorio git"

# El bug original: cambio sin stagear solo en mobile
new_repo mobile-unstaged "${MONO[@]}"
echo y >> apps/mobile/b.js
run
expect "mobile unstaged: fuente" "FUENTE=unstaged"
expect "mobile unstaged: tipo" "TIPOS=mobile"
expect "mobile unstaged: repo" "REPO=monorepo"
expect "mobile unstaged: raíz" "RAIZ=$ROOT/mobile-unstaged"
expect "mobile unstaged: diff" "DIFF=git diff"
expect_diff_runs "mobile unstaged"

# Staged web + unstaged mobile + nuevo: revisa lo staged y avisa del resto
new_repo staged-y-resto "${MONO[@]}"
echo y >> apps/web/src/a.js && git add apps/web/src/a.js
echo y >> apps/mobile/b.js
echo nuevo > apps/web/src/nuevo.js
run
expect "staged: fuente" "FUENTE=staged"
expect "staged: tipo" "TIPOS=frontend"
expect "staged: diff" "DIFF=git diff --staged"
expect "staged: aviso" "AVISO=hay 2 ficheros con cambios sin stagear o sin trackear fuera de esta revisión"
expect "staged: sin trackear no entra" "SIN_TRACKEAR=0"

# Solo un fichero nuevo sin trackear; los de herramientas no cuentan
new_repo solo-nuevo "${MONO[@]}"
echo nuevo > apps/web/src/nuevo.js
mkdir -p .claude/plans .expo .idea && echo p > .claude/plans/p.md && echo d > .expo/devices.json && echo i > .idea/x.xml
run
expect "nuevo: fuente" "FUENTE=unstaged"
expect "nuevo: contado" "SIN_TRACKEAR=1"
expect "nuevo: listado" "?? apps/web/src/nuevo.js"
expect "nuevo: tipo" "TIPOS=frontend"
expect "nuevo: total" "FICHEROS=1"
expect "nuevo: excluidos" "EXCLUIDOS=3 (sin trackear en .claude/, .idea/, .expo/, .vscode/ o .cursor/)"

# Solo ficheros de herramientas: no hay nada que revisar en el árbol, así que va al último commit
new_repo solo-herramientas "${MONO[@]}"
echo y >> apps/mobile/b.js && git commit -qam dos
mkdir -p .claude && echo p > .claude/x.md
run
expect "herramientas: último commit" "FUENTE=ultimo-commit"
expect "herramientas: tipo del commit" "TIPOS=mobile"

# Web y mobile a la vez; renombrado y borrado
new_repo ambos "${MONO[@]}"
echo y >> apps/web/src/a.js && echo y >> apps/mobile/b.js
run
expect "ambos: tipos" "TIPOS=frontend mobile"
expect "ambos: total" "FICHEROS=2"
new_repo renombres "${MONO[@]}"
git mv apps/web/src/a.js apps/web/src/renombrado.js && git rm -q packages/core/c.js
run
expect "renombre: destino" "apps/web/src/renombrado.js"
expect "borrado: listado" "packages/core/c.js"
expect_no "renombre: origen no" "apps/web/src/a.js"

# Solo packages/core cuenta como frontend
new_repo core "${MONO[@]}"
echo y >> packages/core/c.js
run
expect "core: tipo" "TIPOS=frontend"

# Árbol limpio en una rama con dos commits frente a main
new_repo rama "${MONO[@]}"
git checkout -qb feat
echo y >> apps/web/src/a.js && git commit -qam uno
echo y >> apps/mobile/b.js && git commit -qam dos
run
expect "rama: fuente" "FUENTE=rama:main...HEAD"
expect "rama: diff" "DIFF=git diff main...HEAD"
expect "rama: tipos" "TIPOS=frontend mobile"
expect "rama: total" "FICHEROS=2"
expect_diff_runs "rama"
git checkout -q --detach
run
expect "HEAD separado por delante de main: rama" "FUENTE=rama:main...HEAD"
git checkout -q main && git checkout -q --detach
run
expect "HEAD separado en main: último commit" "FUENTE=ultimo-commit"

# Rama sin commits propios: último commit
new_repo rama-vacia "${MONO[@]}"
git checkout -qb feat
run
expect "rama sin commits: último commit" "FUENTE=ultimo-commit"

# Árbol limpio en main: último commit
new_repo main-limpio "${MONO[@]}"
echo y >> apps/mobile/b.js && git commit -qam dos
run
expect "main: fuente" "FUENTE=ultimo-commit"
expect "main: diff" "DIFF=git diff HEAD~1"
expect "main: tipo" "TIPOS=mobile"

# Repo con un solo commit
new_repo un-commit "${MONO[@]}"
run
expect "un commit: fuente" "FUENTE=ultimo-commit"
expect "un commit: diff" "DIFF=git show HEAD"
expect "un commit: total" "FICHEROS=3"

# Base desde origin/HEAD de un clon real, con develop como rama de integración
mkdir -p "$ROOT/remoto" && git init -q --bare -b main "$ROOT/remoto/r.git" || exit 1
new_repo origen artisan composer.json app/Models/X.php
git remote add origin "$ROOT/remoto/r.git" && git push -q origin main || exit 1
git checkout -qb develop
for i in 1 2 3; do echo d > "app/Dev$i.php" && git add -A && git commit -qm "dev $i"; done
git push -q origin develop || exit 1
git clone -q "$ROOT/remoto/r.git" "$ROOT/clon" && cd "$ROOT/clon" || exit 1
git checkout -qb feat origin/main && echo y >> app/Models/X.php && git commit -qam cambio
run
expect "clon: base origin/main" "FUENTE=rama:origin/main...HEAD"
expect "clon: backend" "TIPOS=backend"
git checkout -qb feat2 origin/develop && echo m > app/Mio.php && git add -A && git commit -qm mio
run
expect "rama sacada de develop: base develop" "FUENTE=rama:origin/develop...HEAD"
expect "rama sacada de develop: solo lo suyo" "FICHEROS=1"
git checkout -q develop 2>/dev/null || git checkout -qb develop origin/develop
run
expect "en develop: último commit" "FUENTE=ultimo-commit"

# origin/HEAD colgando (tras renombrar la rama por defecto en el remoto)
cd "$ROOT/clon" && git checkout -q feat
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/master
run
expect "origin/HEAD colgando: cae a origin/main" "FUENTE=rama:origin/main...HEAD"

# Clon superficial: no se inventa el último commit
git clone -q --depth 1 "file://$ROOT/remoto/r.git" "$ROOT/superficial" && cd "$ROOT/superficial" || exit 1
run
expect_code "clon superficial sale con 3" 3

# websites, backend y desconocido
new_repo web next.config.mjs src/a.js
echo y >> src/a.js
run
expect "websites: repo" "REPO=websites"
expect "websites: tipo" "TIPOS=websites"
new_repo back artisan composer.json app/X.php
echo y >> app/X.php
run
expect "backend: tipo" "TIPOS=backend"
new_repo nada README.md
echo y >> README.md
run
expect "desconocido: repo" "REPO=unknown"
expect "desconocido: tipo" "TIPOS=unknown"

# --path desde un subdirectorio, con rutas raras, y ejecutando el DIFF emitido
new_repo ruta "${MONO[@]}" apps/web/src/b.js "apps/mobile/app/(auth)/login.jsx" "apps/mobile/app/order/[id].jsx" \
  "apps/web/src/mi dir/f.js" "apps/web/src/l'élément.js"
for f in apps/web/src/a.js apps/web/src/b.js apps/mobile/b.js "apps/mobile/app/(auth)/login.jsx" \
         "apps/mobile/app/order/[id].jsx" "apps/web/src/mi dir/f.js" "apps/web/src/l'élément.js"; do echo y >> "$f"; done
cd apps/web
run --path src/a.js
expect "path: alcance" "ALCANCE=apps/web/src/a.js"
expect "path: total" "FICHEROS=1"
expect "path: fichero relativo a la raíz" "apps/web/src/a.js"
expect_no "path: no mete otros" "apps/mobile/b.js"
expect "path: diff anclado" "DIFF=git diff -- ':(top)apps/web/src/a.js'"
expect_diff_runs "path desde subdirectorio"
run --path ../mobile/b.js
expect "path con ../" "ALCANCE=apps/mobile/b.js"
expect_diff_runs "path con ../"
run --path "src/mi dir/f.js"
expect "path con espacio" "FICHEROS=1"
expect_diff_runs "path con espacio"
run --path "src/l'élément.js"
expect "path con comilla" "FICHEROS=1"
expect_diff_runs "path con comilla"
run --path "../mobile/app/(auth)/login.jsx"
expect "path (grupo)" "FICHEROS=1"
expect_diff_runs "path (grupo)"
run --path "../mobile/app/order/[id].jsx"
expect "path [param]" "FICHEROS=1"
expect_diff_runs "path [param]"
run --path src
expect "path a directorio" "ALCANCE=apps/web/src"
expect "path a directorio: total" "FICHEROS=4"
run --path "$ROOT/ruta/apps/web/src/a.js"
expect "path absoluta" "ALCANCE=apps/web/src/a.js"
ln -s "$ROOT/ruta" "$ROOT/enlace"
run --path "$ROOT/enlace/apps/web/src/a.js"
expect "path absoluta por symlink" "ALCANCE=apps/web/src/a.js"
run
expect "subdir sin path: todo el repo" "FICHEROS=7"
run --path "$ROOT/ruta/"
expect "path a la raíz" "ALCANCE=."
run --path /otro/sitio.js
expect_code "path absoluta fuera del repo" 64
run --path ../../../fuera.js
expect_code "path relativa fuera del repo" 64
run --path src/noexiste.js
expect_code "path que no existe" 64
git rm -q --cached ../mobile/b.js && rm ../mobile/b.js && git commit -qm borra
run --path ../mobile/b.js
expect_code "path borrada pero en HEAD~1 no está en HEAD" 64
run --path src/a.js src/b.js
expect_code "argumentos de más" 64
run --path
expect_code "path sin valor" 64

# --repo
cd "$ROOT/ruta"
run --repo
expect "repo: tipo" "REPO=monorepo"
expect "repo: apps" "APPS=web mobile"
run --repo x
expect_code "repo con argumentos de más" 64

# Nombres raros sin escapar y clasificados bien
new_repo nombres "${MONO[@]}"
echo x > "apps/web/src/configuración.js"
echo x > 'apps/mobile/"raro".jsx'
run
expect "tildes" "?? apps/web/src/configuración.js"
expect "comillas en el nombre" '?? apps/mobile/"raro".jsx'
expect "comillas: tipo mobile" "TIPOS=frontend mobile"

# Git falla: error explícito, no «no hay cambios»
new_repo roto "${MONO[@]}"
echo y >> apps/web/src/a.js
chmod 000 .git/index
run
chmod 644 .git/index
expect_code "git falla sale con 3" 3
expect_no "git falla: no dice ninguna" "FUENTE=ninguna"

# No modifica el índice
new_repo sin-escribir "${MONO[@]}"
touch apps/web/src/a.js
before=$(ls -l --time-style=+%s .git/index 2>/dev/null || stat -f %m .git/index)
run
after=$(ls -l --time-style=+%s .git/index 2>/dev/null || stat -f %m .git/index)
if [ "$before" = "$after" ]; then ok; else ko "el índice se ha reescrito"; fi

# --pr con un gh simulado
new_repo pr "${MONO[@]}"
mkdir -p "$ROOT/bin"
cat > "$ROOT/bin/gh" <<EOF
#!/usr/bin/env bash
case "\$1 \$2" in
  "pr diff") printf 'apps/web/src/a.js\napps/mobile/b.js\n' ;;
  "pr view") cat "$ROOT/pr-head" ;;
esac
EOF
chmod +x "$ROOT/bin/gh"
git rev-parse HEAD > "$ROOT/pr-head"
PATH="$ROOT/bin:$PATH" run --pr '#42'
expect "pr: fuente" "FUENTE=pr:42"
expect "pr: diff" "DIFF=gh pr diff 42"
expect "pr: tipos" "TIPOS=frontend mobile"
expect "pr: en worktree" "PR_EN_WORKTREE=si"
mkdir -p .claude && echo p > .claude/p.md
PATH="$ROOT/bin:$PATH" run --pr 42
expect "pr: .claude no cuenta" "PR_EN_WORKTREE=si"
echo n > notas.md
PATH="$ROOT/bin:$PATH" run --pr 42
expect "pr: sin trackear avisa" "PR_EN_WORKTREE=si"
expect "pr: aviso sin trackear" "AVISO=hay 1 ficheros sin trackear en el working tree; pueden afectar a los tests de la PR"
echo y >> apps/web/src/a.js
PATH="$ROOT/bin:$PATH" run --pr 42
expect "pr: árbol sucio" "PR_EN_WORKTREE=no"
PATH="$ROOT/bin:$PATH" run --pr abc
expect_code "pr: número no válido" 64
printf '#!/bin/sh\nexit 1\n' > "$ROOT/bin/gh"
PATH="$ROOT/bin:$PATH" run --pr 42
expect_code "pr: gh falla sale con 2" 2

run --otra
expect_code "argumento no reconocido" 64

printf '\n%s pruebas OK, %s fallos\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
