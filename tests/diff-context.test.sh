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


# DIFF_U0 ejecutado de verdad: sin líneas de contexto y con las añadidas
expect_u0_runs() {
  local cmd out
  cmd=$(field DIFF_U0)
  out=$(bash -c "$cmd" 2>/dev/null)
  if printf '%s\n' "$out" | grep -q '^+[^+]' && ! printf '%s\n' "$out" | grep -q '^ '; then ok; else ko "$1: DIFF_U0 roto o con contexto: $cmd"; fi
}

# --path con fuente rama y último commit (el -z iba detrás del pathspec y salía vacío)
new_repo path-rama "${MONO[@]}" apps/web/src/b.js
printf 'l1\nl2\nl3\nl4\nl5\n' > apps/web/src/a.js && git commit -qam base
git checkout -qb feat
printf 'l1\nl2\nNUEVA\nl3\nl4\nl5\n' > apps/web/src/a.js && echo y >> apps/web/src/b.js && git commit -qam cambio
cd apps/web
run --path src/a.js
expect "path + rama: fuente" "FUENTE=rama:main...HEAD"
expect "path + rama: un fichero" "FICHEROS=1"
expect_diff_runs "path + rama"
expect_u0_runs "path + rama"
git checkout -q main && git merge -q --ff-only feat
run --path src/a.js
expect "path + último commit: fuente" "FUENTE=ultimo-commit"
expect "path + último commit: un fichero" "FICHEROS=1"
expect_u0_runs "path + último commit"
cd "$ROOT/path-rama"
run
expect_u0_runs "último commit sin path"

# STAGED_LIMPIO: lo staged tiene además cambios sin stagear en el mismo fichero
new_repo staged-sucio "${MONO[@]}" apps/web/src/b.js
echo uno >> apps/web/src/a.js && git add apps/web/src/a.js && echo dos >> apps/web/src/a.js
run
expect "staged con el mismo fichero sin stagear" "STAGED_LIMPIO=no"
expect_u0_runs "staged"
new_repo staged-limpio "${MONO[@]}" apps/web/src/b.js
echo uno >> apps/web/src/a.js && git add apps/web/src/a.js && echo dos >> apps/web/src/b.js
run
expect "staged limpio aunque haya otros sin stagear" "STAGED_LIMPIO=si"
git reset -q
run
expect "tras reset: unstaged" "FUENTE=unstaged"
expect_no "unstaged no imprime STAGED_LIMPIO" "STAGED_LIMPIO=si"

# PR: checkout de la cabeza con origin/{base} y merge commit de GitHub Actions
new_repo pr-merge "${MONO[@]}"
MAIN_SHA=$(git rev-parse HEAD)
git update-ref refs/remotes/origin/main "$MAIN_SHA"
git checkout -qb pr && echo y >> apps/web/src/a.js && git commit -qam pr
PR_SHA=$(git rev-parse HEAD)
mkdir -p "$ROOT/bin2"
cat > "$ROOT/bin2/gh" <<EOF
#!/usr/bin/env bash
case "\$*" in
  "pr diff 7 --name-only") echo apps/web/src/a.js ;;
  *headRefOid*) echo "$PR_SHA" ;;
  *baseRefName*) echo main ;;
esac
EOF
chmod +x "$ROOT/bin2/gh"
PATH="$ROOT/bin2:$PATH" run --pr 7
expect "pr en la cabeza: worktree" "PR_EN_WORKTREE=si"
expect "pr en la cabeza: base" "PR_BASE=origin/main"
expect "pr en la cabeza: diff sin contexto" "DIFF_U0=git diff --unified=0 origin/main...HEAD"
expect_u0_runs "pr en la cabeza"
git checkout -q main && echo z >> packages/core/c.js && git commit -qam base2 && git merge -q --no-ff pr -m "Merge pr"
PATH="$ROOT/bin2:$PATH" run --pr 7
expect "pr en merge commit: worktree" "PR_EN_WORKTREE=si"
expect "pr en merge commit: base" "PR_BASE=HEAD^1"
expect "pr en merge commit: aviso" "AVISO=HEAD es el merge commit de la PR sobre su base (checkout de GitHub Actions)"
expect_u0_runs "pr en merge commit"
git checkout -q --detach "$MAIN_SHA"
PATH="$ROOT/bin2:$PATH" run --pr 7
expect "pr: otro commit" "PR_EN_WORKTREE=no"

# PR: la base es el commit que da GitHub (baseRefOid), no un origin/{base} desactualizado
new_repo pr-base "${MONO[@]}"
OLD_MAIN=$(git rev-parse HEAD)
echo ajeno > packages/core/otro.js && git add -A && git commit -qm "commit ajeno en main"
NEW_MAIN=$(git rev-parse HEAD)
git checkout -qb feat && echo y >> apps/web/src/a.js && git commit -qam feat
FEAT_SHA=$(git rev-parse HEAD)
mkdir -p "$ROOT/bin3"
cat > "$ROOT/bin3/gh" <<EOF
#!/usr/bin/env bash
case "\$*" in
  "pr diff 9 --name-only") echo apps/web/src/a.js ;;
  *headRefOid*) echo "$FEAT_SHA" ;;
  *baseRefName*) echo main ;;
  *baseRefOid*) cat "$ROOT/pr-base-oid" ;;
esac
EOF
chmod +x "$ROOT/bin3/gh"
echo "$NEW_MAIN" > "$ROOT/pr-base-oid"
git update-ref refs/remotes/origin/main "$NEW_MAIN"
PATH="$ROOT/bin3:$PATH" run --pr 9
expect "pr con origin al día: base" "PR_BASE=origin/main"
if printf '%s\n' "$OUT" | grep -q '^AVISO='; then ko "pr con origin al día no avisa"; else ok; fi
git update-ref refs/remotes/origin/main "$OLD_MAIN"
PATH="$ROOT/bin3:$PATH" run --pr 9
expect "pr con origin desactualizado: base de GitHub" "PR_BASE=$NEW_MAIN"
expect "pr con origin desactualizado: aviso" "AVISO=origin/main no coincide con la base actual de la PR; se usa la de GitHub (${NEW_MAIN:0:12})"
u0=$(bash -c "$(field DIFF_U0)" 2>/dev/null)
if printf '%s\n' "$u0" | grep -q 'otro.js'; then ko "pr con origin desactualizado: DIFF_U0 mete el commit ajeno"; else ok; fi
echo 0123456789abcdef0123456789abcdef01234567 > "$ROOT/pr-base-oid"
PATH="$ROOT/bin3:$PATH" run --pr 9
expect "pr sin la base en local: sin PR_BASE" "DIFF_U0="
expect_no "pr sin la base en local: no da PR_BASE" "PR_BASE=origin/main"
expect "pr sin la base en local: aviso" "AVISO=la base de la PR (0123456789ab) no está en local, así que no hay DIFF_U0 (git fetch origin main)"

# PR en un clon superficial del merge commit: no se puede comprobar, y se dice
git checkout -q main && git update-ref refs/remotes/origin/main "$NEW_MAIN"
git merge -q --no-ff feat -m "Merge feat"
git clone -q --depth 1 "file://$ROOT/pr-base" "$ROOT/pr-shallow" && cd "$ROOT/pr-shallow" || exit 1
PATH="$ROOT/bin3:$PATH" run --pr 9
expect "pr en clon superficial: no en worktree" "PR_EN_WORKTREE=no"
expect "pr en clon superficial: aviso" "AVISO=clon superficial: no se puede comprobar si HEAD es el merge commit de la PR (en GitHub Actions, actions/checkout con fetch-depth: 2 o más)"

# --path avisa de los cambios sin commitear de fuera de la ruta
new_repo path-fuera "${MONO[@]}" apps/web/src/b.js
git checkout -qb feat && echo y >> apps/web/src/a.js && git commit -qam feat
echo z >> apps/web/src/b.js && echo n > apps/web/src/nuevo.js
run --path apps/web/src/a.js
expect "path con árbol sucio fuera: fuente" "FUENTE=rama:main...HEAD"
expect "path con árbol sucio fuera: aviso" "AVISO=hay 2 ficheros con cambios sin commitear fuera de apps/web/src/a.js, que los tests del Paso 6 también verán"
git checkout -q -- apps/web/src/b.js && rm apps/web/src/nuevo.js
run --path apps/web/src/a.js
if printf '%s\n' "$OUT" | grep -q '^AVISO='; then ko "path con árbol limpio no avisa"; else ok; fi

# --path: un rename que cruza el límite de la ruta cuenta como cambio de fuera
new_repo path-rename "${MONO[@]}"
git mv apps/web/src/a.js packages/core/a.js
run --path apps/web/src
expect "rename hacia fuera de la ruta: aviso" "AVISO=hay 1 ficheros con cambios sin commitear fuera de apps/web/src, que los tests del Paso 6 también verán"
git reset -q --hard
git mv packages/core/c.js apps/web/src/c.js
echo m > apps/mobile.txt
run --path apps/web/src
expect "rename desde fuera más otro cambio: los dos" "AVISO=hay 2 ficheros con cambios sin commitear fuera de apps/web/src, que los tests del Paso 6 también verán"

# PR en un clon superficial con la cabeza y la base sin historia común
new_repo pr-sinbase "${MONO[@]}"
git checkout -qb feat && echo y >> apps/web/src/a.js && git commit -qam feat
git checkout -q main && echo z >> packages/core/c.js && git commit -qam main2
git clone -q --depth 1 --branch feat "file://$ROOT/pr-sinbase" "$ROOT/pr-sinbase-shallow" && cd "$ROOT/pr-sinbase-shallow" || exit 1
git fetch -q --depth 1 origin main:refs/remotes/origin/main
SB_FEAT=$(git rev-parse HEAD); SB_MAIN=$(git rev-parse origin/main)
mkdir -p "$ROOT/bin4"
cat > "$ROOT/bin4/gh" <<EOF
#!/usr/bin/env bash
case "\$*" in
  "pr diff 5 --name-only") echo apps/web/src/a.js ;;
  *headRefOid*) echo "$SB_FEAT" ;;
  *baseRefName*) echo main ;;
  *baseRefOid*) echo "$SB_MAIN" ;;
esac
EOF
chmod +x "$ROOT/bin4/gh"
PATH="$ROOT/bin4:$PATH" run --pr 5
expect "pr sin merge-base: en worktree" "PR_EN_WORKTREE=si"
expect "pr sin merge-base: sin DIFF_U0" "DIFF_U0="
expect_no "pr sin merge-base: sin PR_BASE" "PR_BASE=origin/main"
expect "pr sin merge-base: aviso" "AVISO=la base de la PR no tiene merge-base con HEAD en este clon (superficial: git fetch --unshallow, o fetch-depth: 0 en GitHub Actions), así que no hay DIFF_U0"

# Rename en el working tree (git add -N): trae dos rutas en -z, como uno staged
new_repo rename-wt "${MONO[@]}"
mv packages/core/c.js packages/core/d.js && git add -N packages/core/d.js
run
expect "rename en el working tree: el fichero nuevo" "packages/core/d.js"
expect_no "rename en el working tree: sin rutas cortadas" "kages/core/c.js"
run --path packages/core
if printf '%s\n' "$OUT" | grep -q '^AVISO='; then ko "rename en el working tree con --path no avisa en falso"; else ok; fi

# --path con muchos ficheros sin trackear fuera: recuento lineal
new_repo path-muchos "${MONO[@]}"
mkdir -p apps/mobile/gen && (cd apps/mobile/gen && i=0; while [ $i -lt 3000 ]; do : > "f$i.js"; i=$((i + 1)); done)
echo y >> apps/web/src/a.js
t0=$(date +%s); run --path apps/web/src; t1=$(date +%s)
expect "muchos fuera: aviso" "AVISO=hay 3000 ficheros con cambios sin commitear fuera de apps/web/src, que los tests del Paso 6 también verán"
if [ $((t1 - t0)) -le 10 ]; then ok; else ko "3000 ficheros fuera de la ruta tardan $((t1 - t0)) s"; fi

# PR con un nombre de rama base que podría inyectar órdenes: se usa el commit
new_repo pr-inj "${MONO[@]}"
INJ_MAIN=$(git rev-parse HEAD)
git update-ref "refs/remotes/origin/rel;true>pwned" "$INJ_MAIN"
git checkout -qb feat && echo y >> apps/web/src/a.js && git commit -qam feat
INJ_FEAT=$(git rev-parse HEAD)
mkdir -p "$ROOT/bin5"
cat > "$ROOT/bin5/gh" <<EOF
#!/usr/bin/env bash
case "\$*" in
  "pr diff 6 --name-only") echo apps/web/src/a.js ;;
  *headRefOid*) echo "$INJ_FEAT" ;;
  *baseRefName*) echo 'rel;true>pwned' ;;
  *baseRefOid*) echo "$INJ_MAIN" ;;
esac
EOF
chmod +x "$ROOT/bin5/gh"
PATH="$ROOT/bin5:$PATH" run --pr 6
expect "rama base con caracteres raros: se usa el commit" "PR_BASE=$INJ_MAIN"
expect "rama base con caracteres raros: DIFF_U0 con el commit" "DIFF_U0=git diff --unified=0 $INJ_MAIN...HEAD"
if printf '%s\n' "$OUT" | grep -q 'pwned'; then ko "el nombre de la rama base no debe salir en la salida"; else ok; fi

run --otra
expect_code "argumento no reconocido" 64

printf '\n%s pruebas OK, %s fallos\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
