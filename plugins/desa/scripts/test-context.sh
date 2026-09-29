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
#                Solo cuenta como aislado sqlite fijado en phpunit.xml o .env.testing, en memoria o
#                en un fichero fijado ahí que no sea el de desarrollo, y sin URL que no sea sqlite en
#                memoria. El sqlite de .env o del entorno, o database/database.sqlite, pueden ser la
#                BD de desarrollo. Con Laravel 7 o anterior, o con un <env> repetido, un valor que
#                no se sabe qué fuente gana da no-aislado.
#   CONEXIONES_REALES  (solo backend, si hay) conexiones de config/database.php con un servidor
#                que no es local, escrito en el fichero o en las variables de env() que usa, o
#                "desconocido (…)" si no se puede analizar; ENTORNO_TEST solo mira la conexión por
#                defecto.

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
# Valor de <$1 name="$2" value="…"> en phpunit.xml, sin contar comentarios, con los atributos en
# cualquier orden y comillas simples o dobles. <server> se asigna tal cual, así que manda el
# último. En <env>, PHPUnit 9+ se queda con el primero (o con el último forzado) y el 7.5 con el
# último: si hay varios con valores distintos, imprime !CONFLICTO. Nada si no está.
phpunit_var() {
  local f
  f=$(phpunit_file) || return 0
  T="$1" N="$2" perl -0777 -ne '
    s/<!--.*?-->//gs;
    my @v;
    while (/<\Q$ENV{T}\E\b([^>]*)>/g) {
      my ($a, %h) = ($1);
      $h{$1} = defined $2 ? $2 : $3 while $a =~ /([\w:-]+)\s*=\s*(?:"([^"]*)"|\x27([^\x27]*)\x27)/g;
      push @v, $h{value} if defined $h{name} && $h{name} eq $ENV{N} && defined $h{value};
    }
    exit unless @v;
    my %d = map { $_ => 1 } @v;
    print $ENV{T} eq "env" && keys %d > 1 ? "!CONFLICTO\n" : "$v[-1]\n";' "$f" 2>/dev/null
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
# Versión mayor de laravel/framework instalada, o nada.
laravel_major() {
  sed -n "s/.*const VERSION = '\([0-9]*\)\..*/\1/p" vendor/laravel/framework/src/Illuminate/Foundation/Application.php 2>/dev/null | head -1
}
# Primera fuente que define $1, en el orden en que la vería Laravel: "valor<TAB>fuente", o
# "!CONFLICTO<TAB>motivo" si no se puede saber qué valor gana.
laravel_var() {
  local sv pe ev pf major n
  pf=$(phpunit_file)
  sv=$(phpunit_var server "$1"); pe=$(printenv "$1"); ev=$(phpunit_var env "$1")
  if [ "$ev" = "!CONFLICTO" ]; then printf '!CONFLICTO\t%s define %s varias veces con valores distintos\n' "$pf" "$1"; return; fi
  major=$(laravel_major)
  if [ -n "$major" ] && [ "$major" -ge 8 ]; then
    # Laravel 8+ (phpdotenv 5) lee $_SERVER, luego $_ENV: <server>, la variable del proceso, <env>.
    [ -n "$sv" ] && { printf '%s\t%s\n' "$sv" "$pf (<server>)"; return; }
    [ -n "$pe" ] && { printf '%s\t%s\n' "$pe" "la variable $1 del entorno"; return; }
    [ -n "$ev" ] && { printf '%s\t%s\n' "$ev" "$pf"; return; }
  else
    # Laravel 7 o anterior lee $_ENV, getenv y $_SERVER, y cuál gana depende de variables_order:
    # con valores distintos no se puede saber.
    n=$(printf '%s\n' "$sv" "$pe" "$ev" | grep . | sort -u | grep -c .)
    if [ "$n" -gt 1 ]; then printf '!CONFLICTO\t%s y la variable del entorno dan valores distintos a %s (Laravel %s)\n' "$pf" "$1" "${major:-desconocido}"; return; fi
    [ -n "$ev" ] && { printf '%s\t%s\n' "$ev" "$pf"; return; }
    [ -n "$pe" ] && { printf '%s\t%s\n' "$pe" "la variable $1 del entorno"; return; }
    [ -n "$sv" ] && { printf '%s\t%s\n' "$sv" "$pf (<server>)"; return; }
  fi
  if [ -f .env.testing ]; then
    v=$(dotenv_var .env.testing "$1"); [ -n "$v" ] && printf '%s\t%s\n' "$v" ".env.testing"
  else
    v=$(dotenv_var .env "$1"); [ -n "$v" ] && printf '%s\t%s\n' "$v" ".env (no hay .env.testing)"
  fi
}
# Ruta absoluta y normalizada de una BD sqlite, como la abriría Laravel desde la raíz.
sqlite_path() {
  local p=$1
  case "$p" in /*) ;; *) p="$TOP/$p" ;; esac
  perl -MFile::Spec -e 'print File::Spec->canonpath($ARGV[0])' "$p"
}
is_memory() { case "$1" in *:memory:*|*mode=memory*) return 0 ;; esac; return 1; }
entorno_test() {
  local cache app r db src u url dbn dsrc dev
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
    url=${r%%$'\t'*}; src=${r#*$'\t'}
    [ "$url" = "!CONFLICTO" ] && { echo "no-aislado ($src)"; return; }
    # La URL decide el driver y la base de datos, y pisa DB_DATABASE. Una de sqlite en memoria de
    # un fichero de tests no aísla por sí sola: puede que la conexión no la lea, y según la forma
    # (sqlite::memory:, sqlite://:memory:) Laravel abre un fichero. Se sigue con las demás reglas.
    if [ "${url#sqlite:}" != "$url" ] && is_memory "$url" && test_source "$src"; then continue; fi
    echo "no-aislado ($u definida desde $src: la URL decide el driver y la base de datos)"; return
  done
  r=$(laravel_var DB_CONNECTION)
  db=${r%%$'\t'*}; src=${r#*$'\t'}
  if [ -z "$r" ]; then echo "desconocido (no se encuentra DB_CONNECTION)"; return; fi
  [ "$db" = "!CONFLICTO" ] && { echo "no-aislado ($src)"; return; }
  if [ "$db" != sqlite ]; then echo "no-aislado (DB_CONNECTION=$db desde $src)"; return; fi
  if ! test_source "$src"; then echo "no-aislado (DB_CONNECTION=$db desde $src: puede ser la BD de desarrollo)"; return; fi
  r=$(laravel_var DB_DATABASE)
  dbn=${r%%$'\t'*}; dsrc=${r#*$'\t'}
  if [ -z "$r" ]; then
    echo "no-aislado (sqlite sin DB_DATABASE: Laravel usaría database/database.sqlite, que puede ser la BD de desarrollo)"; return
  fi
  [ "$dbn" = "!CONFLICTO" ] && { echo "no-aislado ($dsrc)"; return; }
  if is_memory "$dbn"; then echo "aislado (DB_CONNECTION=sqlite desde $src; DB_DATABASE=$dbn desde $dsrc)"; return; fi
  if ! test_source "$dsrc"; then echo "no-aislado (sqlite con DB_DATABASE=$dbn desde $dsrc: puede ser la BD de desarrollo)"; return; fi
  # Un fichero de tests que es el mismo que el de desarrollo (p. ej. tras cp .env .env.testing).
  for dev in database/database.sqlite "$(dotenv_var .env DB_DATABASE)"; do
    [ -n "$dev" ] && ! is_memory "$dev" || continue
    if [ "$(sqlite_path "$dbn")" = "$(sqlite_path "$dev")" ]; then
      echo "no-aislado (sqlite con DB_DATABASE=$dbn desde $dsrc: es el mismo fichero que la BD de desarrollo)"; return
    fi
  done
  echo "aislado (DB_CONNECTION=sqlite desde $src; DB_DATABASE=$dbn desde $dsrc)"
}
# ¿La fuente es solo de tests (phpunit.xml o .env.testing)?
test_source() { case "$1" in phpunit.xml*|phpunit.dist.xml*|.env.testing) return 0 ;; esac; return 1; }
# Conexiones de config/database.php cuyo host, dsn o url es un servidor que no es local: escrito
# en el fichero, como valor por defecto de env() o como valor de la variable de env() en el
# entorno de tests (resuelta con laravel_var). Laravel las usa tal cual con APP_ENV=testing, y el
# código puede escribir en ellas con DB::connection('…'). Lee el fichero con el tokenizer de PHP,
# que no lo ejecuta; si no puede, imprime "desconocido (…)".
CONEX_PHP='
$src = @file_get_contents($argv[1]);
if ($src === false) exit(2);
try { $toks = token_get_all($src, TOKEN_PARSE); } catch (Throwable $e) { exit(2); }
$t = [];
foreach ($toks as $x) if (!is_array($x) || !in_array($x[0], [T_WHITESPACE, T_COMMENT, T_DOC_COMMENT], true)) $t[] = $x;
$lit = function ($x) { return is_array($x) && $x[0] === T_CONSTANT_ENCAPSED_STRING ? stripcslashes(substr($x[1], 1, -1)) : null; };
$st = [];
for ($i = 0, $n = count($t); $i < $n; $i++) {
    $x = $t[$i]; $v = is_array($x) ? $x[1] : $x;
    if ($v === "[") { $st[] = ["arr" => true, "key" => null]; continue; }
    if (is_array($x) && $x[0] === T_ARRAY && ($t[$i + 1] ?? null) === "(") { $st[] = ["arr" => true, "key" => null]; $i++; continue; }
    if ($v === "(") {
        $env = $i > 0 && is_array($t[$i - 1]) && $t[$i - 1][0] === T_STRING && strtolower($t[$i - 1][1]) === "env";
        $st[] = ["arr" => false, "env" => $env, "arg" => 0]; continue;
    }
    if ($v === "]" || $v === ")") { array_pop($st); continue; }
    $k = count($st) - 1;
    if ($v === ",") { if ($k >= 0) { if ($st[$k]["arr"]) $st[$k]["key"] = null; else $st[$k]["arg"]++; } continue; }
    $s = $lit($x);
    if ($s === null) continue;
    if (is_array($t[$i + 1] ?? null) && $t[$i + 1][0] === T_DOUBLE_ARROW) { if ($k >= 0 && $st[$k]["arr"]) $st[$k]["key"] = $s; $i++; continue; }
    $names = [];
    foreach ($st as $e) if ($e["arr"]) $names[] = $e["key"];
    $c = array_search("connections", $names, true);
    if ($c === false || !isset($names[$c + 1])) continue;
    $key = null;
    foreach (array_slice($names, $c + 2) as $u) if (in_array($u, ["host", "dsn", "url"], true)) { $key = $u; break; }
    if ($key === null) continue;
    $top = $st[$k];
    $kind = !$top["arr"] && $top["env"] && $top["arg"] === 0 ? "VAR" : "LIT";
    echo $names[$c + 1], "\t", $key, "\t", $kind, "\t", str_replace(["\t", "\n"], " ", $s), "\n";
}
'
conexiones_reales() {
  [ -f config/database.php ] || return 0
  local out conn key kind val v real=""
  if ! out=$(php -r "$CONEX_PHP" config/database.php 2>/dev/null); then
    echo "desconocido (no se ha podido analizar config/database.php con el tokenizer de php)"; return
  fi
  while IFS=$'\t' read -r conn key kind val; do
    [ -n "$conn" ] || continue
    if [ "$kind" = VAR ]; then v=$(laravel_var "$val"); v=${v%%$'\t'*}; else v=$val; fi
    [ -n "$v" ] || continue
    if [ "$key" = host ]; then case "$v" in localhost|127.0.0.1|::1) continue ;; esac; fi
    case " $real " in *" $conn "*) ;; *) real="${real:+$real }$conn" ;; esac
  done <<EOF
$out
EOF
  [ -n "$real" ] && printf '%s\n' $real | sort | tr '\n' ' ' | sed 's/ $//' && echo
  return 0
}

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
  CONEXIONES_REALES=$(conexiones_reales)
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
[ "$STACK" = backend ] && [ -n "$CONEXIONES_REALES" ] && echo "CONEXIONES_REALES=$CONEXIONES_REALES"
exit 0
