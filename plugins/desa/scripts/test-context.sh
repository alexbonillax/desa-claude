#!/usr/bin/env bash
# Runner de tests y cobertura del proyecto, para el Paso 6 de /desa:review. Solo lee: no ejecuta tests.
#
# Salida (CLAVE=valor):
#   STACK        backend | websites | monorepo | desconocido
#   RUNNER       pest | phpunit | vitest | no-instalado | ninguno
#   COBERTURA    xdebug | pcov | v8 | istanbul | ninguna
#   PLAYWRIGHT   si | no
#   E2E_SMOKE    número de specs en tests/e2e/smoke
#   DIFF_COVERAGE  si | no   (scripts/diff-coverage.mjs del proyecto)

set -u

TOP=$(git rev-parse --show-toplevel 2>/dev/null) || TOP=$(pwd)
cd "$TOP" || exit 1

any_file() { for f in "$@"; do [ -f "$f" ] && return 0; done; return 1; }

if [ -f artisan ] && [ -f composer.json ]; then
  STACK=backend
  if [ -x vendor/bin/pest ]; then RUNNER=pest
  elif [ -x vendor/bin/phpunit ]; then RUNNER=phpunit
  elif [ -f phpunit.xml ] || [ -f phpunit.xml.dist ]; then RUNNER=no-instalado
  else RUNNER=ninguno
  fi
  COBERTURA=$(php -m 2>/dev/null | tr '[:upper:]' '[:lower:]' | grep -xE 'xdebug|pcov' | head -1)
  COBERTURA=${COBERTURA:-ninguna}
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

echo "STACK=$STACK"
echo "RUNNER=$RUNNER"
echo "COBERTURA=$COBERTURA"
echo "PLAYWRIGHT=$PLAYWRIGHT"
echo "E2E_SMOKE=$E2E_SMOKE"
echo "DIFF_COVERAGE=$DIFF_COVERAGE"
