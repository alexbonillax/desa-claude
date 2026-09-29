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
#   ENTORNO_TEST aislado | no-aislado | desconocido (solo backend), con el motivo. Es la BD que
#                vería Laravel con APP_ENV=testing delante, en este mismo entorno:
#                - con la configuración cacheada (bootstrap/cache/config.php), Laravel ignora
#                  .env, .env.testing y phpunit.xml: no-aislado;
#                - un <server name="APP_ENV"> de phpunit.xml distinto de testing anula el prefijo;
#                - DB_CONNECTION sale, por este orden, de un <server> de phpunit.xml, de la
#                  variable del proceso (gana a un <env>, aunque lleve force="true"), de un <env>,
#                  de .env.testing si existe y, si no, de .env;
#                - DB_URL o DATABASE_URL, en cualquiera de esas fuentes, deciden el driver.
#                Solo cuenta como aislado sqlite fijado en phpunit.xml o .env.testing, sin URL que
#                no sea sqlite, y con DB_DATABASE=:memory: o fijado también ahí. El sqlite de .env o
#                del entorno, o el database/database.sqlite por defecto, pueden ser la BD de desarrollo.

set -u

TOP=$(git rev-parse --show-toplevel 2>/dev/null) || TOP=$(pwd -P)
TOP=$(cd "$TOP" && pwd -P) || exit 1
cd "$TOP" || exit 1

any_file() { for f in "$@"; do [ -f "$f" ] && return 0; done; return 1; }

# Fichero de configuración que usaría PHPUnit sin -c.
phpunit_file() {
  local f
  for f in phpunit.xml phpunit.dist.xml phpunit.xml.dist; do [ -f "$f" ] && { echo "$f"; return 0; }; done
  return 1
}
# Valor del último <$1 name="$2" value="…"> de phpunit.xml, sin contar comentarios, con los
# atributos en cualquier orden y comillas simples o dobles. Nada si no está.
phpunit_var() {
  local f
  f=$(phpunit_file) || return 0
  T="$1" N="$2" perl -0777 -ne '
    s/<!--.*?-->//gs;
    my $v;
    while (/<\Q$ENV{T}\E\b([^>]*)>/g) {
      my ($a, %h) = ($1);
      $h{$1} = defined $2 ? $2 : $3 while $a =~ /([\w:-]+)\s*=\s*(?:"([^"]*)"|\x27([^\x27]*)\x27)/g;
      $v = $h{value} if defined $h{name} && $h{name} eq $ENV{N} && defined $h{value};
    }
    print "$v\n" if defined $v;' "$f" 2>/dev/null
}
# Valor de $2 en el fichero dotenv $1 (acepta export, comillas y comentarios al final).
dotenv_var() {
  [ -f "$1" ] || return 0
  N="$2" perl -ne '
    s/\r?\n$//;
    next unless /^\s*(?:export\s+)?\Q$ENV{N}\E\s*=\s*(.*)$/;
    my $v = $1;
    if ($v =~ /^"((?:[^"\\]|\\.)*)"/) { $v = $1 }
    elsif ($v =~ /^\x27([^\x27]*)\x27/) { $v = $1 }
    else { $v =~ s/\s+#.*$//; $v =~ s/\s+$//; }
    $last = $v;
    END { print "$last\n" if defined $last }' "$1" 2>/dev/null
}
# Primera fuente que define $1, en el orden en que la vería Laravel: "valor<TAB>fuente".
laravel_var() {
  local v
  v=$(phpunit_var server "$1"); [ -n "$v" ] && { printf '%s\t%s\n' "$v" "$(phpunit_file) (<server>)"; return; }
  v=$(printenv "$1"); [ -n "$v" ] && { printf '%s\t%s\n' "$v" "la variable $1 del entorno"; return; }
  v=$(phpunit_var env "$1"); [ -n "$v" ] && { printf '%s\t%s\n' "$v" "$(phpunit_file)"; return; }
  if [ -f .env.testing ]; then
    v=$(dotenv_var .env.testing "$1"); [ -n "$v" ] && printf '%s\t%s\n' "$v" ".env.testing"
  else
    v=$(dotenv_var .env "$1"); [ -n "$v" ] && printf '%s\t%s\n' "$v" ".env (no hay .env.testing)"
  fi
}
entorno_test() {
  local cache app r db src u url dbn dsrc
  cache=${APP_CONFIG_CACHE:-bootstrap/cache/config.php}
  if [ -f "$cache" ]; then
    echo "no-aislado (configuración cacheada en $cache: Laravel no lee .env, .env.testing ni phpunit.xml; php artisan config:clear)"; return
  fi
  app=$(phpunit_var server APP_ENV)
  if [ -n "$app" ] && [ "$app" != testing ]; then
    echo "no-aislado ($(phpunit_file) fija APP_ENV=$app con <server>, que anula APP_ENV=testing)"; return
  fi
  for u in DB_URL DATABASE_URL; do
    r=$(laravel_var "$u")
    [ -n "$r" ] || continue
    url=${r%%$'\t'*}
    case "$url" in sqlite:*) ;; *) echo "no-aislado ($u definida desde ${r#*$'\t'}: la URL decide el driver)"; return ;; esac
  done
  r=$(laravel_var DB_CONNECTION)
  db=${r%%$'\t'*}; src=${r#*$'\t'}
  if [ -z "$r" ]; then echo "desconocido (no se encuentra DB_CONNECTION)"; return; fi
  if [ "$db" != sqlite ]; then echo "no-aislado (DB_CONNECTION=$db desde $src)"; return; fi
  if ! test_source "$src"; then echo "no-aislado (DB_CONNECTION=sqlite desde $src: puede ser la BD de desarrollo)"; return; fi
  r=$(laravel_var DB_DATABASE)
  dbn=${r%%$'\t'*}; dsrc=${r#*$'\t'}
  if [ -z "$r" ]; then
    echo "no-aislado (sqlite sin DB_DATABASE: Laravel usaría database/database.sqlite, que puede ser la BD de desarrollo)"
  elif [ "$dbn" = ":memory:" ] || test_source "$dsrc"; then
    echo "aislado (DB_CONNECTION=sqlite desde $src; DB_DATABASE=$dbn desde $dsrc)"
  else
    echo "no-aislado (sqlite con DB_DATABASE=$dbn desde $dsrc: puede ser la BD de desarrollo)"
  fi
}
# ¿La fuente es solo de tests (phpunit.xml o .env.testing)?
test_source() { case "$1" in phpunit.xml*|phpunit.dist.xml*|.env.testing) return 0 ;; esac; return 1; }

if [ -f artisan ] && [ -f composer.json ]; then
  STACK=backend
  if [ -x vendor/bin/pest ]; then RUNNER=pest
  elif [ -x vendor/bin/phpunit ]; then RUNNER=phpunit
  elif phpunit_file >/dev/null; then RUNNER=no-instalado
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
