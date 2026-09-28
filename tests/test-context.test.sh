#!/usr/bin/env bash
# Pruebas de plugins/desa/scripts/test-context.sh sobre proyectos temporales.
# Uso: bash tests/test-context.test.sh

set -u
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_COMMON_DIR
SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/plugins/desa/scripts/test-context.sh"
ROOT=$(mktemp -d) || { echo "mktemp falló"; exit 1; }
[ -d "$ROOT" ] || exit 1
export GIT_CEILING_DIRECTORIES="$ROOT"
trap 'rm -rf "$ROOT"' EXIT
PASS=0
FAIL=0
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

proj() {
  local d="$ROOT/$1"; shift
  mkdir -p "$d" && cd "$d" && git init -q || exit 1
  for f in "$@"; do mkdir -p "$(dirname "$f")"; : > "$f"; done
}
exe() { for f in "$@"; do mkdir -p "$(dirname "$f")"; printf '#!/bin/sh\n' > "$f"; chmod +x "$f"; done; }
fake_php() {  # fake_php NOMBRE MODULO [pcov.enabled]
  mkdir -p "$ROOT/bin-$1"
  cat > "$ROOT/bin-$1/php" <<EOF
#!/bin/sh
[ "\$1" = "-m" ] && printf '[PHP Modules]\\nCore\\n%s\\n' "$2"
[ "\$1" = "-r" ] && printf '%s' "${3:-1}"
exit 0
EOF
  chmod +x "$ROOT/bin-$1/php"
}

run() { OUT=$("$BASH" "$SCRIPT" 2>&1); }
expect() {
  if printf '%s\n' "$OUT" | grep -qx -- "$2"; then PASS=$((PASS + 1)); else
    FAIL=$((FAIL + 1)); printf 'FALLO: %s\n  esperaba: %s\n  salida: %s\n' "$1" "$2" "$(printf '%s' "$OUT" | tr '\n' ' ')"; fi
}

fake_php none "Json"
fake_php xdebug "Xdebug"
fake_php pcov "pcov"
fake_php pcov-off "pcov" 0

proj phpunit artisan composer.json phpunit.xml
exe vendor/bin/phpunit
PATH="$ROOT/bin-none:$PATH" run
expect "phpunit: stack" "STACK=backend"
expect "phpunit: runner" "RUNNER=phpunit"
expect "phpunit: sin driver" "COBERTURA=ninguna"
PATH="$ROOT/bin-xdebug:$PATH" run
expect "phpunit: xdebug" "COBERTURA=xdebug"

PATH="$ROOT/bin-pcov-off:$PATH" run
expect "pcov instalado pero desactivado no cuenta" "COBERTURA=ninguna"
expect "raíz" "RAIZ=$(cd "$ROOT/phpunit" && pwd -P)"

proj pest artisan composer.json phpunit.xml
exe vendor/bin/pest vendor/bin/phpunit
PATH="$ROOT/bin-pcov:$PATH" run
expect "pest gana a phpunit" "RUNNER=pest"
expect "pest: pcov" "COBERTURA=pcov"

proj sin-vendor artisan composer.json phpunit.xml.dist
PATH="$ROOT/bin-none:$PATH" run
expect "phpunit.xml sin vendor" "RUNNER=no-instalado"

proj sin-tests artisan composer.json
PATH="$ROOT/bin-none:$PATH" run
expect "backend sin tests" "RUNNER=ninguno"

proj web next.config.js vitest.config.js playwright.config.js tests/e2e/smoke/a.spec.js tests/e2e/smoke/b.spec.js scripts/diff-coverage.mjs
exe node_modules/.bin/vitest
mkdir -p node_modules/@vitest/coverage-v8
run
expect "websites: stack" "STACK=websites"
expect "websites: vitest" "RUNNER=vitest"
expect "websites: v8" "COBERTURA=v8"
expect "websites: playwright" "PLAYWRIGHT=si"
expect "websites: smoke" "E2E_SMOKE=2"
expect "websites: diff-coverage" "DIFF_COVERAGE=si"

proj web-sin-install next.config.mjs vitest.config.mjs
run
expect "vitest sin node_modules" "RUNNER=no-instalado"
expect "sin coverage" "COBERTURA=ninguna"

proj web-sin-tests next.config.mjs
run
expect "websites sin tests" "RUNNER=ninguno"
expect "sin smoke" "E2E_SMOKE=0"
expect "sin diff-coverage" "DIFF_COVERAGE=no"

proj mono apps/web/x.js apps/mobile/y.js
run
expect "monorepo" "STACK=monorepo"
expect "monorepo sin runner" "RUNNER=ninguno"

proj sub artisan composer.json phpunit.xml app/X.php
exe vendor/bin/phpunit
cd app
PATH="$ROOT/bin-none:$PATH" run
expect "desde subdirectorio" "RUNNER=phpunit"


# Entorno de tests efectivo del backend con APP_ENV=testing
proj env-phpunit artisan composer.json
printf '<phpunit>\n  <php>\n    <env name="APP_ENV" value="testing"/>\n    <env name="DB_CONNECTION" value="sqlite"/>\n  </php>\n</phpunit>\n' > phpunit.xml
printf 'DB_CONNECTION=mysql\n' > .env
PATH="$ROOT/bin-none:$PATH" run
expect "phpunit.xml con sqlite" "ENTORNO_TEST=aislado (DB_CONNECTION=sqlite desde phpunit.xml)"

proj env-comentado artisan composer.json
printf '<phpunit>\n  <php>\n    <!-- <env name="DB_CONNECTION" value="sqlite"/> -->\n  </php>\n</phpunit>\n' > phpunit.xml
printf 'APP_NAME=x\nDB_CONNECTION=mysql\nDB_HOST=db.example.amazonaws.com\n' > .env
PATH="$ROOT/bin-none:$PATH" run
expect "sqlite comentado y sin .env.testing" "ENTORNO_TEST=no-aislado (DB_CONNECTION=mysql desde .env (no hay .env.testing))"
printf 'DB_CONNECTION="sqlite"\nDB_DATABASE=:memory:\n' > .env.testing
PATH="$ROOT/bin-none:$PATH" run
expect "con .env.testing sqlite" "ENTORNO_TEST=aislado (DB_CONNECTION=sqlite desde .env.testing)"
printf 'DB_CONNECTION=mysql\n' > .env.testing
PATH="$ROOT/bin-none:$PATH" run
expect ".env.testing con mysql" "ENTORNO_TEST=no-aislado (DB_CONNECTION=mysql desde .env.testing)"

proj env-nada artisan composer.json phpunit.xml
PATH="$ROOT/bin-none:$PATH" run
expect "sin DB_CONNECTION en ningún sitio" "ENTORNO_TEST=desconocido (no se encuentra DB_CONNECTION)"

proj env-web next.config.js
run
if printf '%s\n' "$OUT" | grep -q '^ENTORNO_TEST='; then FAIL=$((FAIL + 1)); echo "FALLO: websites no debe imprimir ENTORNO_TEST"; else PASS=$((PASS + 1)); fi

printf '\n%s pruebas OK, %s fallos\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
