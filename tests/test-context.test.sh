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

# Sin las variables de BD de quien ejecuta las pruebas; runenv añade las que se le pasen.
CLEAN=(env -u DB_CONNECTION -u DB_DATABASE -u DB_URL -u DATABASE_URL -u APP_CONFIG_CACHE)
run() { OUT=$("${CLEAN[@]}" "$BASH" "$SCRIPT" 2>&1); }
runenv() { OUT=$("${CLEAN[@]}" "$@" "$BASH" "$SCRIPT" 2>&1); }
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
printf '<phpunit>\n  <php>\n    <env name="APP_ENV" value="testing"/>\n    <env name="DB_CONNECTION" value="sqlite"/>\n    <env name="DB_DATABASE" value=":memory:"/>\n  </php>\n</phpunit>\n' > phpunit.xml
printf 'DB_CONNECTION=mysql\nDB_DATABASE=grupodesa\n' > .env
PATH="$ROOT/bin-none:$PATH" run
expect "phpunit.xml con sqlite" "ENTORNO_TEST=aislado (DB_CONNECTION=sqlite desde phpunit.xml; DB_DATABASE=:memory: desde phpunit.xml)"
PATH="$ROOT/bin-none:$PATH" runenv DB_CONNECTION=mysql
expect "la variable del proceso gana al <env>" "ENTORNO_TEST=no-aislado (DB_CONNECTION=mysql desde la variable DB_CONNECTION del entorno)"
PATH="$ROOT/bin-none:$PATH" runenv DATABASE_URL=mysql://u:p@db.example.com/grupodesa
expect "DATABASE_URL en el entorno" "ENTORNO_TEST=no-aislado (DATABASE_URL definida desde la variable DATABASE_URL del entorno: la URL decide el driver)"
PATH="$ROOT/bin-none:$PATH" runenv DB_URL=sqlite:///tmp/x.sqlite
expect "DB_URL de sqlite no cuenta" "ENTORNO_TEST=aislado (DB_CONNECTION=sqlite desde phpunit.xml; DB_DATABASE=:memory: desde phpunit.xml)"
PATH="$ROOT/bin-none:$PATH" runenv DB_DATABASE=grupodesa
expect "DB_DATABASE del entorno" "ENTORNO_TEST=no-aislado (sqlite con DB_DATABASE=grupodesa desde la variable DB_DATABASE del entorno: puede ser la BD de desarrollo)"

sed -i.bak 's|<env name="DB_CONNECTION" value="sqlite"/>|<env name="DB_CONNECTION" value="sqlite" force="true"/>|' phpunit.xml
PATH="$ROOT/bin-none:$PATH" runenv DB_CONNECTION=mysql
expect "force=true no gana a la variable del proceso" "ENTORNO_TEST=no-aislado (DB_CONNECTION=mysql desde la variable DB_CONNECTION del entorno)"

printf '<phpunit>\n  <php>\n    <server value="sqlite" name="DB_CONNECTION"/>\n    <env name=\x27DB_DATABASE\x27 value=\x27:memory:\x27/>\n  </php>\n</phpunit>\n' > phpunit.xml
PATH="$ROOT/bin-none:$PATH" runenv DB_CONNECTION=mysql
expect "<server> gana a la variable, atributos en otro orden y comillas simples" "ENTORNO_TEST=aislado (DB_CONNECTION=sqlite desde phpunit.xml (<server>); DB_DATABASE=:memory: desde phpunit.xml)"

printf '<phpunit>\n  <php>\n    <server name="APP_ENV" value="local"/>\n    <env name="DB_CONNECTION" value="sqlite"/>\n    <env name="DB_DATABASE" value=":memory:"/>\n  </php>\n</phpunit>\n' > phpunit.xml
PATH="$ROOT/bin-none:$PATH" run
expect "<server> APP_ENV anula el prefijo" "ENTORNO_TEST=no-aislado (phpunit.xml fija APP_ENV=local con <server>, que anula APP_ENV=testing)"

printf '<phpunit>\n  <php>\n    <env name="DB_CONNECTION" value="sqlite"/>\n  </php>\n</phpunit>\n' > phpunit.xml
printf 'DB_CONNECTION=mysql\n' > .env
PATH="$ROOT/bin-none:$PATH" run
expect "sqlite sin DB_DATABASE" "ENTORNO_TEST=no-aislado (sqlite sin DB_DATABASE: Laravel usaría database/database.sqlite, que puede ser la BD de desarrollo)"

proj env-cache artisan composer.json
printf '<phpunit>\n  <php>\n    <env name="DB_CONNECTION" value="sqlite"/>\n    <env name="DB_DATABASE" value=":memory:"/>\n  </php>\n</phpunit>\n' > phpunit.xml
mkdir -p bootstrap/cache && printf '<?php return [];\n' > bootstrap/cache/config.php
PATH="$ROOT/bin-none:$PATH" run
expect "configuración cacheada" "ENTORNO_TEST=no-aislado (configuración cacheada en bootstrap/cache/config.php: Laravel no lee .env, .env.testing ni phpunit.xml; php artisan config:clear)"
rm bootstrap/cache/config.php
printf '<?php return [];\n' > "$ROOT/otra-cache.php"
PATH="$ROOT/bin-none:$PATH" runenv APP_CONFIG_CACHE="$ROOT/otra-cache.php"
expect "APP_CONFIG_CACHE" "ENTORNO_TEST=no-aislado (configuración cacheada en $ROOT/otra-cache.php: Laravel no lee .env, .env.testing ni phpunit.xml; php artisan config:clear)"
PATH="$ROOT/bin-none:$PATH" run
expect "sin caché vuelve a aislado" "ENTORNO_TEST=aislado (DB_CONNECTION=sqlite desde phpunit.xml; DB_DATABASE=:memory: desde phpunit.xml)"

proj env-dist artisan composer.json
printf '<phpunit>\n  <php>\n    <env name="DB_CONNECTION" value="sqlite"/>\n    <env name="DB_DATABASE" value=":memory:"/>\n  </php>\n</phpunit>\n' > phpunit.dist.xml
PATH="$ROOT/bin-none:$PATH" run
expect "phpunit.dist.xml" "ENTORNO_TEST=aislado (DB_CONNECTION=sqlite desde phpunit.dist.xml; DB_DATABASE=:memory: desde phpunit.dist.xml)"

proj env-comentado artisan composer.json
printf '<phpunit>\n  <php>\n    <!-- <env name="DB_CONNECTION" value="sqlite"/> -->\n  </php>\n</phpunit>\n' > phpunit.xml
printf 'APP_NAME=x\nDB_CONNECTION=mysql\nDB_HOST=db.example.amazonaws.com\n' > .env
PATH="$ROOT/bin-none:$PATH" run
expect "sqlite comentado y sin .env.testing" "ENTORNO_TEST=no-aislado (DB_CONNECTION=mysql desde .env (no hay .env.testing))"
printf 'DB_CONNECTION="sqlite"\nDB_DATABASE=:memory:\n' > .env.testing
PATH="$ROOT/bin-none:$PATH" run
expect "con .env.testing sqlite" "ENTORNO_TEST=aislado (DB_CONNECTION=sqlite desde .env.testing; DB_DATABASE=:memory: desde .env.testing)"
printf 'export DB_CONNECTION=sqlite # tests\nDB_DATABASE=\x27:memory:\x27\n' > .env.testing
PATH="$ROOT/bin-none:$PATH" run
expect ".env.testing con export, comentario y comillas simples" "ENTORNO_TEST=aislado (DB_CONNECTION=sqlite desde .env.testing; DB_DATABASE=:memory: desde .env.testing)"
printf 'DB_CONNECTION=sqlite\nDB_DATABASE=:memory:\nDATABASE_URL=mysql://u:p@db.example.com/x\n' > .env.testing
PATH="$ROOT/bin-none:$PATH" run
expect "DATABASE_URL en .env.testing" "ENTORNO_TEST=no-aislado (DATABASE_URL definida desde .env.testing: la URL decide el driver)"
PATH="$ROOT/bin-none:$PATH" runenv DB_CONNECTION=mysql
expect "variable del proceso frente a .env.testing" "ENTORNO_TEST=no-aislado (DATABASE_URL definida desde .env.testing: la URL decide el driver)"
printf 'DB_CONNECTION=sqlite\nDB_DATABASE=:memory:\n' > .env.testing
PATH="$ROOT/bin-none:$PATH" runenv DB_CONNECTION=mysql
expect "la variable del proceso gana a .env.testing" "ENTORNO_TEST=no-aislado (DB_CONNECTION=mysql desde la variable DB_CONNECTION del entorno)"
printf 'DB_CONNECTION=mysql\n' > .env.testing
PATH="$ROOT/bin-none:$PATH" run
expect ".env.testing con mysql" "ENTORNO_TEST=no-aislado (DB_CONNECTION=mysql desde .env.testing)"
rm .env.testing
printf 'DB_CONNECTION=sqlite\nDB_DATABASE=/Users/dev/proyecto/database/database.sqlite\n' > .env
PATH="$ROOT/bin-none:$PATH" run
expect "sqlite de .env es la BD de desarrollo" "ENTORNO_TEST=no-aislado (DB_CONNECTION=sqlite desde .env (no hay .env.testing): puede ser la BD de desarrollo)"
PATH="$ROOT/bin-none:$PATH" runenv DB_CONNECTION=sqlite
expect "sqlite del entorno" "ENTORNO_TEST=no-aislado (DB_CONNECTION=sqlite desde la variable DB_CONNECTION del entorno: puede ser la BD de desarrollo)"

proj env-nada artisan composer.json phpunit.xml
PATH="$ROOT/bin-none:$PATH" run
expect "sin DB_CONNECTION en ningún sitio" "ENTORNO_TEST=desconocido (no se encuentra DB_CONNECTION)"

proj env-web next.config.js
run
if printf '%s\n' "$OUT" | grep -q '^ENTORNO_TEST='; then FAIL=$((FAIL + 1)); echo "FALLO: websites no debe imprimir ENTORNO_TEST"; else PASS=$((PASS + 1)); fi

printf '\n%s pruebas OK, %s fallos\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
