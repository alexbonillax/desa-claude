# Changelog

All notable changes to the `desa` plugin will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.18.0] — 2026-09-29

Correcciones de la verificación adversarial de la 1.17.0.

### Security

- **Conexiones a servidores reales en `config/database.php`** — `ENTORNO_TEST` solo mira la conexión por defecto. En grupodesa-backend sale «aislado» (sqlite en memoria), pero `spyro_transfer`, `gdapps` y `snowflake-admin` tienen el servidor escrito en el propio fichero, son de producción, y el código escribe en ellas (`SpyroService` hace `DB::connection('spyro_transfer')->insert(...)`). `test-context.sh` imprime ahora `CONEXIONES_REALES` con las conexiones que tienen un host no local, un `dsn` o una `url` escritos en el fichero, o como valor por defecto de `env()`. Con ellas, review no ejecuta los tests sola: lo ofrece en «Acciones propuestas», y ningún test generado puede llegar a esas conexiones. Hoy salen en grupodesa-backend y desa-connect (las tres) y en gdapps (`desaverse`).
- **`ENTORNO_TEST`, más casos en que daba «aislado» sin serlo**:
  - una `DB_URL` o `DATABASE_URL` de sqlite pisa `DB_DATABASE`. Ahora solo cuenta una URL de sqlite en memoria fijada en `phpunit.xml` o `.env.testing`;
  - con un `<env>` repetido, PHPUnit 9 y posteriores se quedan con el primero y el 7.5 con el último. Con valores distintos ya no cuenta como aislado;
  - un `DB_DATABASE` de tests que apunta al mismo fichero que la BD de desarrollo (tras `cp .env .env.testing`, o `database/database.sqlite`);
  - con Laravel 7 o anterior, el orden entre `<server>`, la variable del proceso y `<env>` depende de `variables_order`. Si dan valores distintos, ya no cuenta como aislado.

### Fixed

- **`/desa:update` se quedaba bloqueado** — Claude Code actualiza el clon con `git pull origin HEAD`, que no mueve `origin/main`. Tras la primera actualización, el paso 2 veía como «commits sin subir» todo lo que había llegado, y los listados con `@{u}` salían vacíos. Ahora hace `git fetch origin` antes de comprobar, y los listados vuelven a `{gitCommitSha}..HEAD`.
- **`terms.py`**:
  - un fichero de idioma con un array vacío (`return [];`) hacía abortar el sync entero desde la 1.17.0;
  - `\X41`, con la X en mayúscula, se leía distinto de PHP;
  - upsert y delete también imprimen `CAMBIA_FORMATO` y avisan si reescribirían un fichero con otro formato, perdiendo sus comentarios. translations pide confirmación en ese caso.
- **`diff-context.sh`**:
  - un rename que cruza el límite de `--path` ya cuenta como cambio de fuera;
  - en modo PR, si la base no tiene merge-base con HEAD (clon superficial), no da `PR_BASE` ni `DIFF_U0` y lo avisa, en vez de dar una orden que falla.
- **Paso 7 de review** — Con un informe de cobertura por fichero de test, una línea está cubierta si algún informe le da `count` mayor que 0.
- CHANGELOG 1.17.0: la orden de cobertura sigue saliendo con 0; lo que cambia es el `EXIT=` por fichero.
- magic-factorial ya no aparece como pendiente de decisión en la auditoría, el README, los evals ni el CHANGELOG 1.16.0: queda fuera por decisión del autor. La skill no cambia.

## [1.17.0] — 2026-09-29

Correcciones de la verificación adversarial de la 1.14.0 y la 1.15.0.

### Security

- **`ENTORNO_TEST` calcula la BD que vería Laravel de verdad** — Solo miraba ficheros, y daba «aislado» en casos en que los tests irían contra la BD real:
  - una variable del proceso (`DB_CONNECTION`, `DB_DATABASE`) gana al `<env>` de `phpunit.xml`, aunque lleve `force="true"`, y a `.env.testing`;
  - `DB_URL` o `DATABASE_URL` deciden el driver aunque la conexión sea `sqlite`;
  - un `<server name="APP_ENV">` distinto de `testing` anula el prefijo `APP_ENV=testing`;
  - con la configuración cacheada (`bootstrap/cache/config.php` o `APP_CONFIG_CACHE`), Laravel no lee ni `.env` ni `.env.testing` ni `phpunit.xml`;
  - el sqlite de `.env` o del entorno, o el `database/database.sqlite` por defecto, pueden ser la BD de desarrollo del dev.

  Ahora solo cuenta como aislado un sqlite fijado en `phpunit.xml` o `.env.testing`, en memoria o en un fichero fijado ahí, sin URL que no sea sqlite. Lee también `phpunit.dist.xml`, atributos en cualquier orden y con comillas simples, y `export`, comillas y comentarios en los `.env`. grupodesa-backend sigue saliendo aislado (`.env.testing` con `:memory:`).

- **`terms.py` ya no borra ni corrompe datos ajenos al cambio**:
  - `delete --code ''` (o `--ns ''`) borraba el primer term del namespace, porque la API ignora los filtros vacíos y devuelve un listado. Y como la API no distingue mayúsculas, `--code Global.Save` borraba `global.save`. Ahora `--ns` y `--code` se validan con el formato de la API y se aborta si la API devuelve un term distinto del pedido;
  - en upsert, los idiomas del term que no están en `/locales` se quitaban del POST, y la API sustituye `value` entero: se borraban. Ahora se conservan;
  - en gdapps, `upsert --ns app` escribía en el `app` propio del proyecto un term del `app` de grupodesa. Con esa clave compartida, el siguiente sync proponía dar de baja las 1.258 claves locales. upsert y delete se niegan ahora con `NAMESPACE_AJENO`;
  - `parse_php` leía distinto de PHP los escapes `\x` y octales (bytes en PHP), un `$` seguido de un carácter no ASCII y los comentarios que acaban en CR o en `?>`. Como upsert y delete reescriben el fichero entero, corrompían claves que no tenían que ver. Ahora se leen como en PHP o el fichero se rechaza, comprobado con unos 1.000 ficheros aleatorios y con los 110 reales frente a PHP 8.2;
  - la escritura local es atómica (temporal y `os.replace`) y se codifica antes de llamar a la API. Si falla, `ERROR_LOCAL=` dice qué se escribió y qué no, también en sync;
  - `sync --include-ns auth` sobrescribía el fichero de Laravel, y `--include-ns` no podía sustituir un `NAMESPACE_AJENO` aunque el aviso lo ofreciera. Las dos cosas quedan corregidas.

### Fixed

- **`terms.py`**:
  - `lang/vendor` (de `vendor:publish`) ya no bloquea sync, upsert ni delete;
  - `CAMBIA_FORMATO=N` marca los ficheros que se reescribirían con otro formato y perderían sus comentarios, con o sin cambios de datos. En grupodesa-api y gdapps pasa con todos, y translations pide confirmación;
  - los errores de red de `http.client` salen como error de red.
- **`desa_api.py`**:
  - una respuesta de error cortada o con timeout sale con 3, no con un traceback;
  - los tokens tienen que ser ASCII visible, así que un espacio de ancho cero pegado del portapapeles ya no acaba en un traceback que enseña su posición;
  - las rutas solo admiten dígitos ASCII;
  - `~/.cache/desa` no se sigue si es un enlace, y un fichero con enlaces duros dentro de él se rechaza, porque `--content-from` podría enviar a la wiki un fichero de fuera;
  - `--save-content` comprueba el destino antes de la petición y no guarda nada si la respuesta no es un documento;
  - `--save-content` y `--content-from` conservan los saltos de línea (CRLF y CR sueltos), así que los párrafos que no se tocan viajan de verdad tal cual.
- **Paso 6 de `/desa:review`: un fichero de test por ejecución** — PHPUnit 9 y 10 solo ejecutan el primer fichero que se les pasa e ignoran el resto sin avisar, así que con varios el verde era falso. La orden es ahora un bucle que imprime `EXIT=` por fichero.
- **La orden de cobertura da un `EXIT=` por fichero** — Sigue terminando en `echo`, así que la llamada sale con 0 aunque falle el runner: el resultado se lee en las líneas `EXIT=`, y cada fichero deja su informe en el directorio `COV`.
- **Paso 7**: los ficheros sin trackear cuentan enteros como líneas añadidas (no salen en `DIFF_U0`), y en modo PR sin base local las líneas añadidas salen del `gh pr diff`.
- **Modo PR con `origin/{base}` desactualizado** — `diff-context.sh` usa como base el commit que da GitHub (`baseRefOid`). Con `origin/{base}` atrasado, el merge-base era antiguo y `DIFF_U0` metía commits ajenos a la PR. Si esa base no está en local, no da `PR_BASE` ni `DIFF_U0` y lo avisa.
- **Clon superficial en GitHub Actions** — Con `fetch-depth: 1` no se puede reconocer el merge commit de la PR: ahora lo dice un `AVISO`, y review.md documenta que hace falta `fetch-depth: 2`.
- **Árbol distinto del revisado** — Con `--path`, un `AVISO` cuenta los cambios sin commitear de fuera de la ruta, que los tests también ven. Con `FUENTE=staged`, si un test derivado del diff tiene cambios sin stagear, los tests se omiten.
- **Fallos ajenos al diff** — Las reglas del Paso 7 los contaban como rojo y a la vez decían que no bloqueaban. Ya no bloquean, y el informe los lista en «Fallos ajenos al diff».
- CHANGELOG 1.14.0: en gdapps el sqlite no está comentado en `phpunit.xml`, no aparece.
- **review.md, lo que quedaba de P1-21** — Tras compactar se conservan unos 5.000 tokens del principio de la skill, y review.md tiene unos 7.000. El formato del Paso 8 y los límites del Paso 7 quedaban fuera, y con ellos la prohibición de `RefreshDatabase` en los tests generados y la de commit y push. Ahora el principio lleva un resumen del informe y los límites irreversibles de los Pasos 6 y 7, y dice que se relean también los `criterios-*.md` si ya no está su texto.
- **La plantilla «Sin incidencias» lleva el recuento de descartadas** — Sin incidencias reportadas, las descartadas volvían a desaparecer.
- **`/desa:update`**:
  - comprueba antes de actualizar que el clon del marketplace no tiene cambios ni commits sin subir. Si el `git pull` falla, Claude Code vuelve a clonar y los borra sin avisar, y el comando sale bien;
  - compara también con la versión que tiene cargada la sesión, para no decir «ya tenías la última» sin avisar de `/reload-plugins`;
  - lista solo lo publicado (`{gitCommitSha}..@{u}`);
  - avisa de que las órdenes `git -C` pedirán permiso.
- **`/desa:triage`** — El encargo de cada agente incluye que solo mida en local y sin tocar una BD: `Explore` tiene Bash, pero no puede pedir la confirmación que la skill exige para el resto. Incluye también el aviso de `EXPLAIN ANALYZE`. La regla de `http_code` ya no descarta los 404 y 401 que se miden a propósito al aislar capas. La invocación de `/desa:plan` lleva «Medido» y «Regla de paro», y plan no los reconstruye si no vienen.
- Referencias obsoletas: plan.md seguía citando «los #N de review.md» y «las dos secciones», y wiki.md remitía a un «Antes de cualquier POST» que ya no existe. Quitadas también las mayúsculas de reglas que no son irreversibles.

### Notes

- Un term antiguo con un code que no cumple el formato actual de la API (p. ej. con mayúsculas) ya no se puede buscar ni borrar con `terms.py`: se rechaza antes de llamar a la API.
- En un backend, upsert y delete piden ahora a la API todas las páginas del namespace cuando existe en local, para comprobar `NAMESPACE_AJENO`.

## [1.16.0] — 2026-09-28

Bloque 6 de la auditoría (`docs/auditorias/2026-09-28-skills-opus-5-5.md`): evals y documentación.

### Added

- **Evals en `plugins/desa/evals/`** para `claude plugin eval`, con fixtures de repos de juguete. Fijan fallos que ya se dieron: un cambio sin stagear solo en `apps/mobile` se revisa como mobile y cita #65 (el bug de `DIFF_FILES`); `/desa:plan` reconoce un websites; el formato A de triage; que translations se invoque cuando lo pide el `CLAUDE.md` y nadie edite a mano los ficheros de idioma; y que `/desa:update` no se lance sola. El de magic-factorial falla a propósito: la skill queda fuera por decisión del autor. Están escritos con la documentación de `plugin eval` y sin ejecutar: la 2.1.236 aún no tiene el subcomando.
- **CI en `.github/workflows/ci.yml`** — En cada PR y en cada push a `main`: las pruebas de `tests/`, `claude plugin validate --strict` del marketplace y del plugin, que la versión suba y tenga su entrada en el CHANGELOG si cambia `plugins/desa/`, y un aviso si alguna skill preaprueba intérpretes, red o git/gh completos.
- **Entrada 1.9.0 del CHANGELOG**, que faltaba.

### Changed

- **README** — Tabla de las 7 skills con qué escribe cada una fuera del chat y si el modelo la puede lanzar sola, una sección por skill, el token de la API, la política de `allowed-tools`, el mantenimiento de los criterios, versiones, pruebas, CI y evals. «Actualización» usa `/desa:update` (antes solo refrescaba el catálogo, no el plugin instalado) y menciona `/reload-plugins`.

## [1.15.0] — 2026-09-28

Bloque 5 de la auditoría (`docs/auditorias/2026-09-28-skills-opus-5-5.md`): contexto y estilo para Opus 5.5.

### Changed

- **Los criterios de `/desa:review` salen a `plugins/desa/references/`** — `criterios-compartidos.md` (#1-9), `criterios-backend.md` (#10-33), `criterios-frontend.md` (#34-81), `criterios-mobile.md` (#65 y #82-85) y `criterios-websites.md` (#86-106), cada criterio una vez y con su texto. La skill carga solo los del tipo que toca el diff, y `/desa:plan` lee los mismos ficheros en vez de una copia. Revierte la decisión de la 1.8.0 de no crear subcarpetas: los criterios eran el 57 % de review.md, y tras una compactación, que solo conserva el principio de cada skill, se perdían el formato del informe y las reglas. Los `#N` no se renumeran nunca; los nuevos van al final de su fichero (el siguiente es #107) y los retirados se marcan. Los gemelos de websites llevan `(= #N)`, y mobile declara que no hereda los criterios de frontend.
- **review.md empieza por el flujo, la severidad y los límites**, y dice que se relea el fichero si tras compactar falta algo. Las secciones de reglas se llaman «Límites» en review, plan, triage y translations; wiki ya no tiene una sección de reglas aparte, y magic-factorial queda fuera por decisión del autor.
- **Umbral de confianza con evidencia** — Una incidencia solo se reporta con su evidencia (la línea del diff y, en los criterios de patrón, el fichero de referencia leído) y confianza >= 75. Las descartadas se cuentan en el Resumen en vez de omitirse en silencio, y `--verbose` las lista con su evidencia.
- **Linter frente a criterios** — La regla de no reportar lo que ve un linter solo cubre lo que no tiene criterio propio: los numerados, como #34 o #86, se aplican siempre.
- **Diffs de más de 20 ficheros** — Se revisan todos, con aviso de que por directorio sale más detalle, y lo que no se revise va en «sin revisar».
- **CLAUDE.md y memoria, si no están ya en contexto** — review, plan y triage los aplican sin releerlos si Claude Code ya los cargó, y los leen si no. review lee además los `CLAUDE.md` de los subdirectorios del diff, que Claude Code no carga solo porque el diff llega por Bash.
- **Avisos condensados** — Los avisos largos de «Paso 6 incondicional» y del Paso 7 quedan en una frase cada uno, con su porqué y su antecedente (la validación de la 1.8.0).
- **`/desa:plan`** — description que dice cuándo usarla; si no hay plan mode, llama a `EnterPlanMode` o entrega el plan en el chat; lo que dejó cerrado `/desa:triage` no se vuelve a explorar; las tres iteraciones de revisión pasan a principios del borrador (caminos infelices por stack y simplificación); el plan lleva «Supuestos sin comprobar».
- **`/desa:triage`** — description que la excluye de las implementaciones de alcance claro; formato A de tres líneas; la salida completa abre con `**Veredicto**`, compara el presupuesto declarado con el gastado y añade la columna `alcance` a «Medido»; encargo explícito para cada agente (tipo `Explore`, que no puede lanzar los suyos, y el adversario sin el razonamiento que refuta); qué hacer en nivel 3 cuando nadie puede responder; aviso de que `EXPLAIN ANALYZE` ejecuta la sentencia; tiempo de servidor con `time_starttransfer − time_pretransfer` y `http_code` en cada muestra; minutos solo si se han medido.
- **`/desa:update`** — Anota la versión antes y después con `claude plugin list --json`, resume el CHANGELOG de las versiones nuevas y distingue «actualizado de X a Y» de «ya tenías la última»; si hay commits sin subida de versión, lo dice y ofrece el procedimiento del README. Recuerda `/reload-plugins`. No da por hecho nada que los comandos no muestren.
- **`/desa:wiki`** — Sin role-play; flujo de documentar numerado de principio a fin, con la vista previa, el POST y el resumen como pasos; sección «Fuentes»: solo se documenta lo visto en la sesión, lo no confirmado se pregunta o queda fuera, y las referencias `fichero:línea` van en la vista previa y el resumen, nunca en las páginas de negocio; las consultas pueden ir por el conector MCP de la wiki si la sesión lo tiene; los ids de la estructura llevan la fecha en que se anotaron.
- **Ortografía en un solo fichero** — `plugins/desa/references/ortografia.md` sustituye las dos tablas de wiki y translations. Quita de «siempre con tilde» las formas que también son verbo (*publica*, *numero*, *catalogo*, *vehiculo*) y *mas*, que pasan a «según el caso», y deja *período* como estilo de la casa. La comprobación antes de cada escritura se mantiene.
- **descriptions** — Las de review, plan, triage, wiki y translations dicen cuándo usarlas. review sigue siendo invocable por el modelo (hay reglas `allow Skill(desa:review)` en tres repos), y su description avisa de que puede escribir y stagear tests.

## [1.14.0] — 2026-09-28

### Security

- **El token de la API ya no pasa por la conversación ni por los comandos** — `/desa:wiki` y `/desa:translations` lo imprimían con un `python3 -c` y lo pegaban en cada `curl`, así que acababa en el transcript, en los avisos de permiso y en `ps`. Ahora todo pasa por `plugins/desa/scripts/desa_api.py`, que:
  - lo lee por su cuenta, en este orden: `DESA_API_TOKEN`, `~/.config/desa/api-token` y las claves `desa_api_token` o `desa_wiki_token` de `~/.claude/settings.json`;
  - no lo imprime nunca, tampoco si tiene espacios o caracteres de control (entonces responde `TOKEN_INVALIDO` sin enseñarlo);
  - solo lo envía a `api2.grupodesa.app`: no sigue redirecciones (la API tiene GET que redirigen a S3 o a Factorial) y solo admite las rutas de la wiki y de terms (`/documents…`, `/terms…`, `/locales`), así que un GET preaprobado no puede llegar, por ejemplo, a `/customers/{id}/token`.

  Para guardarlo sin pegarlo en el chat: `! pbpaste | python3 …/desa_api.py set-token --stdin` (fichero 600, carpeta 700). A quien ya lo tenga en `desa_wiki_token` no le hace falta cambiar nada. No se mueve a la clave `env` de settings.json porque eso lo exportaría a todos los procesos de Bash.
- **El Paso 6 de `/desa:review` no ejecuta tests de backend si el entorno no está aislado** — `APP_ENV=testing` solo es seguro si `phpunit.xml` o `.env.testing` fijan una BD sqlite. En grupodesa-api, gdapps y desa-connect no es así (en grupodesa-api y desa-connect el sqlite de `phpunit.xml` está comentado, en gdapps no aparece, y ninguno tiene `.env.testing`), así que Laravel carga `.env`, que es MySQL remoto, y un test con `RefreshDatabase` haría `migrate:fresh` sobre él. `test-context.sh` imprime ahora `ENTORNO_TEST=aislado|no-aislado|desconocido` con el motivo, y sin `aislado` la revisión no ejecuta ningún test. Hoy solo grupodesa-backend está aislado.

### Added

- **`scripts/terms.py`** para `/desa:translations`: `project`, `locales`, `find`, `search`, `upsert`, `delete` y `sync`. Sin `--apply` no escribe nada y enseña lo que haría. Además:
  - pagina, y aborta sin escribir ni en la API ni en local ante cualquier error HTTP;
  - calcula los cambios locales antes de escribir en la API. Si la escritura local falla después, lo dice aparte con `ERROR_LOCAL`;
  - escribe los ficheros con el orden y el formato actuales: regenerar los 6 JSON de grupodesa-front y los 13 PHP de grupodesa-backend da bytes idénticos;
  - lee los PHP de idioma sin ejecutarlos, con un parser propio que coincide con PHP en los 110 ficheros planos de los backends del equipo. Si un fichero no es plano, se niega y pide `--allow-php`, que no está preaprobado;
  - aplica el escapado de `php_str()`;
  - valida los idiomas contra `/locales` y las rutas contra la raíz de idiomas;
  - normaliza los `value` vacíos, `null` o `[]` de la API;
  - no toca los ficheros propios de Laravel;
  - saca los namespaces de backend de los ficheros locales, no toca los que la API no gestiona y marca como `NAMESPACE_AJENO` los que se llaman igual que uno de la API pero no comparten ninguna clave. En gdapps, el `app` local no comparte ninguna clave con el `app` de grupodesa: sin esa marca, un sync propondría 1.258 bajas;
  - reconoce `lang/` además de `resources/lang/`.
- Pruebas con la biblioteca estándar en `tests/test_desa_api.py` y `tests/test_terms.py` (63). Usan servidores HTTP locales y una API simulada, y comprueban, entre otras cosas:
  - los tres casos de `php_str()` de P0-2, con ida y vuelta en PHP;
  - que el token no sale por stdout ni por stderr, ni con una redirección ni con un salto de línea;
  - que no se escribe nada si la API falla en la página 2 o si un fichero local está roto;
  - que el dry-run de sync no ejecuta el PHP del repo.

### Fixed

- **`diff-context.sh`**:
  - con `--path` y la fuente rama o último commit, `-z` quedaba detrás del pathspec y la revisión salía vacía (`FUENTE=ninguna`);
  - el modo PR acepta el merge commit que deja el checkout de GitHub Actions;
  - con `FUENTE=staged`, `STAGED_LIMPIO=no` avisa de que los ficheros revisados tienen además cambios sin stagear, y entonces no se ejecutan tests;
  - `DIFF_U0` da el diff sin contexto listo para ejecutar en todas las fuentes, y `PR_BASE` da la base de la PR.

  Pasa de 109 a 132 pruebas.
- **Pasos 6 y 7 de `/desa:review`**:
  - las órdenes se ejecutan desde `RAIZ`;
  - el informe de cobertura va a una ruta nueva en cada revisión, con `XDEBUG_MODE=coverage`, y si el runner no lo genera (PHPUnit 11 ignora el `<coverage><include>` antiguo) se dice;
  - `test-context.sh` solo da `pcov` si está activo;
  - en websites se ejecuta la suite unitaria entera, como CI, para que los huecos de cobertura sean los mismos;
  - un test en rojo puede ser también un «fallo ajeno al diff», que no bloquea el Paso 7;
  - la tabla de valores de Tests y Cobertura cubre todos los caminos, y el informe termina siempre en incidencias, Resumen, Descartadas y Acciones propuestas.

  `test-context.sh` pasa de 22 a 30 pruebas.

### Changed

- **`/desa:wiki`**:
  - antes de cualquier POST enseña una vista previa (acción, padre, visibilidad, fuentes) y espera un sí explícito, como ya hacía con el DELETE. El diff de una actualización se hace contra el texto real de la API: `GET … --save-content`, Edit y `POST … --content-from`, así que los párrafos que no se tocan viajan tal cual;
  - justo antes de actualizar vuelve a leer la página, porque el backend no tiene bloqueo optimista. Si `updated_at` ha cambiado, no envía nada y vuelve a pedir confirmación;
  - todos los parámetros van en `--param`, así que los espacios, `&` o `#` ya no rompen la petición.
- **`/desa:translations`** pasa de 439 a 179 líneas: toda la operativa va por `terms.py`, y salen los siete ejemplos de `curl` con el token en línea, el script de paginación que se regeneraba en cada sesión y los ejemplos en portugués de Brasil (`Salvar`), porque los datos son pt-PT. La confirmación va antes de sobrescribir valores, de publicar traducciones propuestas por el modelo o de corregir la ortografía del usuario, y en el sync, cuando hay bajas o cambios sin commitear. Además:
  - si el `CLAUDE.md` del proyecto pide todos los idiomas, se proponen los que falten;
  - la tabla de errores queda alineada con la de la wiki;
  - ante «actualiza las traducciones», que es ambiguo, pregunta.
- `allowed-tools` de wiki y translations preaprueba solo `token-status`, `workdir`, `desa_api.py GET` (limitado a las rutas de la wiki y de terms) y los subcomandos de `terms.py` que no escriben ni ejecutan PHP. `POST`, `DELETE`, `--apply` y `--allow-php` piden permiso.

### Notes

- Es el bloque 4 de la auditoría, con las correcciones de la verificación de los bloques 3 y 4.

## [1.13.0] — 2026-09-28

### Fixed

- **Paso 6 de `/desa:review` en los backends reales** — la skill buscaba `./vendor/bin/pest` porque existía `phpunit.xml`, pero grupodesa-backend, grupodesa-api, gdapps y desa-connect solo tienen PHPUnit (7.5 a 11.5), así que el Paso 6 acababa siempre en «no ejecutables». Además, pasaba rutas a `--filter`, que compara nombres de test: PHPUnit respondía «No tests executed!» con exit 0, un falso verde. Ahora un script nuevo, `plugins/desa/scripts/test-context.sh` (22 pruebas en `tests/test-context.test.sh`), detecta el runner por lo instalado (`pest` o `phpunit`, `vitest`) y el driver de cobertura por los módulos de PHP (`xdebug`, `pcov`) o los paquetes (`@vitest/coverage-v8`). Los ficheros de test van como argumentos posicionales, y la cobertura de backend, solo con driver y a un fichero fuera del repo (`--coverage-clover`).
- **Sin suite completa ni directorios en backend** — si no podía derivar un filtro, la skill lanzaba la suite entera. En grupodesa-backend eso es peligroso: `phpunit.xml` fija `APP_ENV=testing` sin `force`, así que manda el shell, y un directorio con `RefreshDatabase` bajo `APP_ENV=local` hizo `migrate:fresh` contra producción (31-07-2026). Ahora se ejecuta siempre con `APP_ENV=testing`, solo sobre ficheros de test concretos, y si no hay ninguno, `Tests: sin test asociado al diff`. En websites, sin test asociado se ejecuta la suite unitaria entera, que usa jsdom y MSW, para que el Paso 7 tenga cobertura. Los tests que según el `CLAUDE.md` necesitan la BD real no se ejecutan desde la revisión.
- **Tests que fallan** — la única corrección permitida era tocar el test, lo que empujaba a hacer pasar una regresión, y la pregunta (s/n) llegaba antes del informe. Ahora cada fallo se diagnostica como regresión (incidencia Crítica, con la corrección propuesta en el código) o como test desactualizado. No se toca nada durante la revisión, y las correcciones van a un bloque «Acciones propuestas» al final del informe, donde el dev elige cuáles aplicar.
- **Paso 7** —
  - un borrador que no converge se borra del árbol y va al informe con su error: ya no se dejan tests rojos con `// FIXME` ni se stagean;
  - `git add` solo toca los tests que ha creado la skill y los que no tenían cambios del dev, para no stagear hunks ajenos;
  - los tests generados no pueden usar `RefreshDatabase` ni `DatabaseMigrations`;
  - en websites, si la fuente es una rama, los huecos se sacan con el `scripts/diff-coverage.mjs` del proyecto, el mismo gate que CI (comprobado en el `main` de desa-websites en GitHub; algún clon local es anterior y no lo tiene);
  - el test nuevo va junto a sus vecinos de `tests/unit/`, en vez de «espejando `src/`», que no coincide con la estructura real.

### Changed

- La tabla de valores de la línea `Tests` añade `sin test asociado al diff`, `· C tests existentes corregidos` y `· R requieren BD real, no ejecutados`, y la de Cobertura, `no evaluada (…)` cuando el Paso 6 no deja seguir.
- `allowed-tools` de `/desa:review` preaprueba también `bash ${CLAUDE_PLUGIN_ROOT}/scripts/test-context.sh`, que solo lee. Los runners siguen pidiendo permiso a propósito.

### Notes

- Es el bloque 3 de la auditoría. Hoy ningún backend tiene driver de cobertura, así que ahí el Paso 7 no se ejecuta: el informe lo dirá como `Cobertura del diff: no disponible (sin xdebug ni pcov)`.

## [1.12.0] — 2026-09-28

### Fixed

- **Detección de la fuente y del tipo en `/desa:review` y `/desa:plan`** — la cadena `git diff --staged --name-only || git diff --name-only || git diff HEAD~1 --name-only` nunca pasaba de la primera orden, porque `git diff --staged` sale con 0 aunque no haya nada. Con cambios sin stagear, un diff de `apps/mobile/` se revisaba con los criterios de frontend y sin los de mobile. La detección vive ahora en un script compartido, `plugins/desa/scripts/diff-context.sh`, con 109 pruebas en `tests/diff-context.test.sh`. El script:
  - devuelve una orden `DIFF` lista para ejecutar desde cualquier directorio del repo, con la ruta anclada a la raíz (`:(top)`) y entrecomillada, así que funciona con rutas como `(auth)`, `[id]` o `[locale]` de Expo Router y Next.js, con espacios y con comillas;
  - lee el estado con un único `git status --porcelain -z` sin locks opcionales, así que no reescribe el índice;
  - si git o gh fallan, la ruta no existe o el clon es superficial, sale con `ERROR`, en vez de decir que no hay cambios.
- **`/desa:plan` en proyectos `websites`** — el Paso 1 no conocía ese tipo y en desa-websites terminaba en `unknown`, lo que cortaba la cadena triage → plan. Ahora detecta el tipo por el repositorio y no por el diff, que al planificar es de otro trabajo. Además:
  - carga los criterios por el encabezado de sección, no por rangos `#N` copiados a mano;
  - busca helpers también en `src/hooks`, `src/lib` y `src/api/services`;
  - tiene ejemplos de websites en la Iteración 2;
  - lee review.md con `${CLAUDE_PLUGIN_ROOT}`, que apunta a la versión instalada.
- **Formato de salida de `/desa:review`** — la cabecera no contemplaba websites, frontend + mobile ni la fuente «fichero», y no tenía sitio para tests ni cobertura. Los valores posibles de Tests y Cobertura del diff van ahora en una tabla del Paso 8. Cuando no había runner se omitía «silenciosamente», así que «tests en verde» y «no se ejecutó nada» se confundían. Ahora la cabecera lleva siempre Proyecto, Fuente, «N de M» ficheros, Tests y Cobertura del diff, con el motivo cuando algo no se hizo. Un runner que no ejecuta ningún test no cuenta como verde.
- **Tests en modo PR** — con `/desa:review 42`, los Pasos 6 y 7 corrían sobre el working tree local, que normalmente es otra rama. Ahora solo se ejecutan si `HEAD` es el commit de la PR y el árbol está limpio.
- **Flags en `$ARGUMENTS`** — `/desa:review --verbose` o `42 -v` no encajaban en ninguna rama del Paso 2. Ahora los flags se separan antes de clasificar.
- `#97` (`i18next.t()` a nivel de módulo en websites, gemelo de `#69`) entra en la lista de Críticos, y un criterio de websites que repite uno del monorepo tiene su misma severidad.

### Changed

- **Fuentes de `/desa:review` sin argumentos**: staged; si no hay, unstaged **más los ficheros sin trackear**, que se leen enteros si son código; con el árbol limpio fuera de una rama de integración, **la rama frente a su base**; si no, el último commit. La base es la de merge-base más cercana entre `origin/HEAD`, main, master, develop y dev, así que una rama sacada de `develop` se compara con `develop` y no con `main`, y un `origin/HEAD` que apunta a una rama borrada no la tumba. Con HEAD separado por delante de la base también se revisa la rama. Los ficheros sin trackear de `.claude/`, `.idea/`, `.expo/`, `.vscode/` y `.cursor/` no cuentan. Antes, un fichero nuevo sin `git add` no se revisaba y, con el árbol limpio en una rama de varios commits, solo se revisaba el último. Si se revisa lo staged y queda algo fuera, la skill lo avisa.
- En el monorepo, los ficheros de `apps/mobile/` son mobile y el resto (`apps/web/`, `packages/`) frontend. Un diff puede tener los dos tipos. `/desa:plan` aplica la misma regla a la tarea.
- Los stubs con `echo` de los tests de frontend y mobile pasan a la línea `Tests: sin runner para este stack`.
- `/desa:triage` da la invocación de `/desa:plan` lista para pegar, con el premio y lo descartado.
- `allowed-tools` de review y plan preaprueba el script (`Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh:*)`), que es de solo lectura. En el README, la política de `allowed-tools` recoge esa excepción y la sección de `/desa:review` describe las fuentes nuevas.

### Notes

- Es el bloque 2 de la auditoría `docs/auditorias/2026-09-28-skills-opus-5-5.md`. El script trabaja desde la raíz de git, así que funciona desde cualquier subdirectorio del repo, y es compatible con el bash 3.2 de macOS.

## [1.11.0] — 2026-09-28

### Fixed

- **Escapado PHP en `/desa:translations`** — la regla escapaba `"` y `\` pero no `$`, y no fijaba el orden. Aplicada al pie de la letra (`"` antes que `\`), duplica la barra de `\"` y el fichero deja de parsear. Ahora el orden es `\` → `\\`, `"` → `\"`, `$` → `\$`, en claves y valores, con una función `php_str()` de referencia que también usa el paso 9 de crear o actualizar. Para reescribir un fichero, sus valores actuales se cargan con PHP, no del texto fuente, para no escaparlos dos veces. La plantilla de paginación pasa de `python3 -c "…"` a un heredoc `python3 - <<'PY'`, porque dentro de comillas dobles bash destroza `php_str()` sin dar error. Con la regla antigua, un `$currency` en un valor tumbaba el namespace entero (Laravel convierte el warning en excepción) y `{${expr}}` ejecutaba código al cargar el fichero. Hoy no hay ningún `$` en los valores reales y los ficheros actuales están bien escapados: regenerarlos con `php_str()` da bytes idénticos.
- **Visibilidad en `/desa:wiki`** — el formato de petición fijaba `teams: []`, `roles: []` e `is_published: true` sin distinguir entre crear y actualizar, y decía que `[]` hacía la página pública. En el backend, `roles` es la lista de roles que pueden verla: con `roles: []` solo la ve super-admin. `teams: []` solo la abre a todos los equipos. Por tanto, una actualización borraba los equipos y roles de la página (dejaba de verla quien no fuera super-admin) y publicaba los borradores, y una página creada con el ejemplo tampoco la veían los empleados. Ahora:
  - al actualizar, se lee con `?include=teams,roles` y se conservan `document_id`, `is_published`, `teams` y `roles`;
  - al crear, `teams` y `roles` se copian del padre;
  - si la página o el padre tienen `roles` vacíos (solo los ve super-admin) o han perdido sus equipos (borrados), no se copia esa visibilidad en silencio: se avisa y se pregunta;
  - la verificación comprueba que `teams`, `roles` y `fields.is_public` no han cambiado al actualizar, y que `roles` no ha quedado vacío al crear;
  - se avisa de que el GET no devuelve `searchable_tags` y hay que reescribirlo al actualizar;
  - se retira `status` de la lista de includes, porque en los documentos devuelve 500.
- **Paginación en `/desa:wiki`** — la skill decía que los GET devuelven 25 resultados por página, pero el backend devuelve 5. Con eso, un documento que existía en la página 2 de la búsqueda se tomaba por inexistente y se creaba un duplicado. Las búsquedas y los listados de hijos llevan ahora `perPage=100` y se mira `meta.has_more_pages`.

### Security

- **`allowed-tools` sin ejecución arbitraria en cinco skills** (magic-factorial conserva el suyo; ver Notes). `allowed-tools` preaprueba herramientas, no las restringe, durante el turno en que se invoca la skill, y el modelo puede invocar las skills del plugin por su cuenta.
  - `/desa:review`: sale `git:*` sin sustituto. Claude Code ya aprueba por su cuenta `git diff/log/show/status` con flags seguros, y un prefijo como `Bash(git log:*)` admitiría `--output=<fichero>`, que escribe ficheros arbitrarios. `gh:*` pasa a `gh pr diff:*`, porque Claude Code no aprueba solo ningún comando `gh` y `gh pr diff` no tiene flags que escriban ficheros. El `git add` del Paso 7 pasa a pedir permiso; los runners de tests ya lo pedían.
  - `/desa:plan`: salen `git:*` y `Write` (en plan mode el fichero del plan no lo necesita).
  - `/desa:triage`: salen `php:*`, `curl:*`, `python3:*`, `grep:*` y `git:*`. Como en auto mode no hay aviso de permiso, antes de cada medición la skill escribe el comando y el entorno, y espera confirmación si no es local o si toca una base de datos.
  - `/desa:translations`: salen `curl:*` y `python3:*`; como en `/desa:wiki`, cada llamada a la API pide permiso en modo manual.
  - `/desa:update`: `claude:*`, que aprobaba también lanzar un Claude anidado sin permisos, `claude mcp add` o `claude plugin install`, pasa a los dos comandos exactos que usa.
- **El modelo ya no puede invocar `/desa:update`** (`disable-model-invocation: true`): solo se ejecuta cuando el dev escribe `/desa:update`.

### Changed

- `Task` → `Agent` en el `allowed-tools` de `/desa:plan` y `/desa:triage`. Es el nombre actual de la herramienta de subagentes; `Task` seguía funcionando como alias.
- README: nueva sección «Mantenimiento: `allowed-tools`» con la política anterior.

### Notes

- Es el bloque 1 de la auditoría `docs/auditorias/2026-09-28-skills-opus-5-5.md`. `/desa:magic-factorial` queda fuera de este bloque, sin cambios: conserva `Bash(curl:*)`, `Bash(python3:*)`, `Write` y `Edit` en `allowed-tools`, y el modelo puede invocarla.
- En modo manual habrá más avisos de permiso en `/desa:review` (el `git add` del Paso 7), `/desa:triage` (mediciones) y `/desa:translations` (cada llamada a la API). Es intencionado. En auto mode, Claude Code ya descartaba `php:*` y `python3:*` de las skills, pero `curl:*`, `git:*`, `gh:*` y `claude:*` sí se aplicaban sin pasar por el clasificador; ahora esos comandos pasan por él.
- Pendiente para el bloque 4: el test automático de `php_str()`, que irá con el script empaquetado de translations.

## [1.10.0] — 2026-09-16

### Added

- **Nueva skill `/desa:triage`** — primera skill de una sesión, anterior a `/desa:plan`. Convierte una petición en una decisión acotada: tamaño del premio, comprobación descalificante, presupuesto declarado y regla de paro. Existe porque el fallo caro no es analizar mal, es analizar mucho lo que no lo merecía. Lleva **15 criterios numerados `[T-1]`-`[T-15]`**, todos derivados de fallos reales medidos, citables como los `#N` de `/desa:review`.
- **Presupuesto declarado con topes duros** en `/desa:triage` — tres niveles (directo 0 agentes / acotado ≤3 / fan-out ≤8 con veto del usuario) y una línea visible antes de gastar. El tope es **total, no por rama** `[T-5]`: un `slice(0, 6)` sobre 4 ramas son 24 agentes.
- **Salida de emergencia para tareas triviales** `[T-1]` — el Paso 1 clasifica la petición en implementación de alcance claro (triage de 3 líneas y a `/desa:plan`), síntoma (disciplina de medición) o decisión (sólo la comprobación descalificante). Sin eso, la skill se convertiría en la ceremonia que pretende evitar.
- **Disciplina de medición** `[T-9]`-`[T-12]` — prohibido presentar una resta como medición, comprobar que se mide la capa correcta (`php -i` informa del SAPI de CLI, no del de FPM), A/B en el mismo proceso con control en la misma ventana, y tres hipótesis refutadas en la misma capa como señal de cambiar de capa.
- **Separación obligatoria entre medido y razonado** `[T-13]` y prueba del camino infeliz antes de proponer `[T-14]` — sin filtros, sin includes, con cero filas y con el principal más restringido.

## [1.9.1] — 2026-06-05

### Changed

- **Fase 7 de `/desa:review` ahora es diff-aware**: la generación de tests faltantes se dispara cuando hay **líneas nuevas/modificadas del diff sin cubrir**, en lugar de depender de un umbral de cobertura global del proyecto. Esto alinea la skill con el modelo de **patch coverage** de `desa-websites` (gate por diff, sin umbral global): un dev recibe propuestas de test para cualquier fichero unit-testeable que toque, sin backfill del legacy.

## [1.9.0] — 2026-05-28

### Added

- **Nueva skill `/desa:magic-factorial`** — gestiona fichajes (attendance shifts) de Factorial a través de su API GraphQL interna, autenticada con las cookies de sesión del navegador. Permite crear los días que faltan, reescribir fichajes incorrectos y cuadrar a 0 el balance mensual. Detecta jornadas reducidas y festivos a partir de `expectedMinutes`, usa siempre `+00:00` por un fallo de zona horaria de la API, fuerza el recálculo con un «touch pass» después de crear y no toca los periodos cerrados.

### Notes

- Entrada añadida después: la 1.9.0 no tenía entrada en el CHANGELOG. El mensaje del commit (`0fce63a`) dice «1.6.0 → 1.7.0», pero el cambio real de `plugin.json` fue de 1.8.0 a 1.9.0.

## [1.8.0] — 2026-05-11

### Added

- **Project type `websites`** in `/desa:review` — la skill detecta proyectos Next.js single-app (presencia de `next.config.js/mjs/ts`, sin `apps/web` ni `packages/core`). El primer proyecto que lo usa es `desa-websites`.
- **21 criterios nuevos para `websites` (86-106)** en `review.md` — heredados aplicables del monorepo + específicos del stack Next.js single-app: `LocaleLink`/`localePath`, MUI imports directos, Server Components por defecto, fetch via `api.js` wrapper, ISR via constantes `REVALIDATE`, MSW intercepta fetch en tests, `globalThis.session` reset automático.
- **Paso 6 — "Ejecutar tests"** en `/desa:review` — tras la revisión estática, la skill ejecuta los tests del proyecto filtrados por el diff. Soportado en `backend` (Pest) y `websites` (Vitest + opcional Playwright). Stubs informativos para `frontend` (monorepo) y `mobile`, pendientes hasta que el equipo defina sus runners.
- **Paso 7 — "Generar tests faltantes"** en `/desa:review` — si tras Paso 6 la cobertura sobre los ficheros del diff está bajo el umbral, la skill genera tests siguiendo el patrón existente, itera hasta 3 veces, y stagea sin commitear.
- **`.gitignore`** en la raíz del repo — ignora ruidos del sistema (`.DS_Store`, `.idea/`) y notas personales (`.claude/BRIEFING.md`, `.claude/RESUMEN_CAMBIOS.md`).

### Changed

- El antiguo **Paso 6 "Formato de salida" pasa a ser Paso 8** (sin cambios en su contenido; solo renumerado para dejar sitio a las Fases 6 y 7 nuevas).
- **Las "Reglas estrictas" del final del fichero `review.md`** aclaran ahora que aplican al Paso 5 (revisión estática). Cada nuevo Paso 6 y 7 tiene sus propias reglas estrictas inline.
- **Clarificación de incondicionalidad** en Paso 6 y Paso 7: ambas fases se ejecutan tras Paso 5 independientemente de las incidencias que éste haya reportado, porque son **fuentes de información complementarias** (estilo + tests + cobertura). El dev consolida todo en el reporte final.

### Notes

- Cambios **aditivos**: la detección actual de `backend`/`frontend`/`mobile` no cambia; solo se añade la rama `websites`. Las Fases 1-5 actuales del flujo de revisión no se tocan.
- **Origen**: Bloque D del plan de seguimiento de `desa-websites` (ver `desa-websites/docs/superpowers/plans/2026-05-10-post-testing-followup.md` y el decision brief asociado).
- **Plan de implementación**: `docs/superpowers/plans/2026-05-11-extend-review-skill-websites-and-test-phases.md`.
- **Validación**: Task 7 (validación manual de Paso 7) se cerró con una nota documentada en el plan — el escenario artificial usado para forzar el gap llevó a la skill a sugerir eliminar el dead code en lugar de generar tests, comportamiento defensivo correcto. En PRs reales con código real y gaps reales, Paso 7 dispara automáticamente sin pedir confirmación.
