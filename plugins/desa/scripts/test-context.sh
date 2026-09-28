#!/usr/bin/env bash
# Runner de tests y cobertura del proyecto, para el Paso 6 de /desa:review. Solo lee: no ejecuta tests.
#
# Salida (CLAVE=valor):
#   RAIZ         raíz del repo: las órdenes del Paso 6 se ejecutan desde ahí
#   STACK        backend | websites | monorepo | desconocido
#   RUNNER       pest | phpunit | vitest | no-instalado | ninguno
#   COBERTURA    xdebug | pcov | v8 | istanbul | ninguna
#   PLAYWRIGHT   si | no
#   E2E_SMOKE    número de specs en tests/e2e/smoke
#   DIFF_COVERAGE  si | no   (scripts/diff-coverage.mjs del proyecto)
#   ENTORNO_TEST aislado | no-aislado | desconocido (solo backend), con el motivo. Con
#                APP_ENV=testing, la BD la decide el <env> de phpunit.xml; si no la fija,
#                .env.testing si existe; si no, .env. Solo sqlite cuenta como aislado.

set -u

TOP=$(git rev-parse --show-toplevel 2>/dev/null) || TOP=$(pwd -P)
TOP=$(cd "$TOP" && pwd -P) || exit 1
cd "$TOP" || exit 1

any_file() { for f in "$@"; do [ -f "$f" ] && return 0; done; return 1; }

# DB_CONNECTION que fija phpunit.xml (sin contar comentarios), o nada.
phpunit_db() {
  local f
  for f in phpunit.xml phpunit.xml.dist; do
    [ -f "$f" ] || continue
    perl -0pe 's/<!--.*?-->//gs' "$f" 2>/dev/null \
      | perl -ne 'print "$1\n" if /<(?:env|server)\s[^>]*name="DB_CONNECTION"[^>]*value="([^"]*)"/' | tail -1
    return 0
  done
}
dotenv_db() {
  [ -f "$1" ] || return 0
  sed -n 's/^[[:space:]]*DB_CONNECTION[[:space:]]*=[[:space:]]*//p' "$1" | tail -1 | tr -d '"'"'"'\r '
}
entorno_test() {
  local db src
  db=$(phpunit_db); src="phpunit.xml"
  if [ -z "$db" ] && [ -f .env.testing ]; then db=$(dotenv_db .env.testing); src=".env.testing"; fi
  if [ -z "$db" ] && [ ! -f .env.testing ]; then db=$(dotenv_db .env); src=".env (no hay .env.testing)"; fi
  if [ -z "$db" ]; then echo "desconocido (no se encuentra DB_CONNECTION)"
  elif [ "$db" = sqlite ]; then echo "aislado (DB_CONNECTION=sqlite desde $src)"
  else echo "no-aislado (DB_CONNECTION=$db desde $src)"
  fi
}

if [ -f artisan ] && [ -f composer.json ]; then
  STACK=backend
  if [ -x vendor/bin/pest ]; then RUNNER=pest
  elif [ -x vendor/bin/phpunit ]; then RUNNER=phpunit
  elif [ -f phpunit.xml ] || [ -f phpunit.xml.dist ]; then RUNNER=no-instalado
  else RUNNER=ninguno
  fi
  MODS=$(php -m 2>/dev/null | tr '[:upper:]' '[:lower:]')
  COBERTURA=ninguna
  if printf '%s\n' "$MODS" | grep -qx pcov && [ "$(php -r 'echo ini_get("pcov.enabled");' 2>/dev/null)" = 1 ]; then
    COBERTURA=pcov
  elif printf '%s\n' "$MODS" | grep -qx xdebug; then
    COBERTURA=xdebug
  fi
  ENTORNO_TEST=$(entorno_test)
elif [ -d apps/web ] || [ -d apps/mobile ] || [ -d packages/core ]; then
  STACK=monorepo
  RUNNER=ninguno
  COBERTURA=ninguna
else
  if [ -f next.config.js ] || [ -f next.config.mjs ] || [ -f next.config.ts ]; then STACK=websites; else STACK=desconocido; fi
  if any_file vitest.config.js vitest.config.mjs vitest.config.ts; then
    if [ -x node_modules/.bin/vitest ]; then RUNNER=vitest; else RUNNER=no-instalado; fi
  else
    RUNNER=ninguno
  fi
  if [ -d node_modules/@vitest/coverage-v8 ]; then COBERTURA=v8
  elif [ -d node_modules/@vitest/coverage-istanbul ]; then COBERTURA=istanbul
  else COBERTURA=ninguna
  fi
fi

PLAYWRIGHT=no
any_file playwright.config.js playwright.config.mjs playwright.config.ts && PLAYWRIGHT=si
E2E_SMOKE=0
for f in tests/e2e/smoke/*.spec.*; do [ -f "$f" ] && E2E_SMOKE=$((E2E_SMOKE + 1)); done
DIFF_COVERAGE=no
[ -f scripts/diff-coverage.mjs ] && DIFF_COVERAGE=si

echo "RAIZ=$TOP"
echo "STACK=$STACK"
echo "RUNNER=$RUNNER"
echo "COBERTURA=$COBERTURA"
echo "PLAYWRIGHT=$PLAYWRIGHT"
echo "E2E_SMOKE=$E2E_SMOKE"
echo "DIFF_COVERAGE=$DIFF_COVERAGE"
[ "$STACK" = backend ] && echo "ENTORNO_TEST=$ENTORNO_TEST"
exit 0
