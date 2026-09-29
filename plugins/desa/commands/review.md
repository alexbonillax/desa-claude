---
description: Revisar código aplicando los estándares del equipo antes de commit o PR. Usar cuando se pide revisar los cambios locales, un fichero o una PR (#N). Además ejecuta los tests del diff y puede generar y dejar en staging los que falten, sin commit
argument-hint: [ruta de archivo, número de PR (#42), vacío para cambios locales, --verbose]
allowed-tools: Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh:*), Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/test-context.sh), Bash(gh pr diff:*), Read, Grep, Glob
---

# Review — Revisión de código con estándares Grupo Desa

Revisa cambios de código aplicando las convenciones del equipo. Detecta automáticamente el tipo de proyecto: backend (Laravel/PHP con artisan), frontend (React/JS monorepo con `apps/web` o `packages/core`), websites (Next.js single-app con `next.config.*`) o mobile (React Native bajo `apps/mobile/`). Un mismo diff puede tener varios tipos, p. ej. frontend + mobile.

## Flujo, severidad y límites

Pasos: 1) fuente y tipo con `diff-context.sh` y lectura de los criterios; 2) diff; 3) CLAUDE.md y memoria; 4) patrones existentes, bajo demanda; 5) revisión; 6) tests del diff; 7) tests que faltan; 8) informe, con el formato del Paso 8. Si tras una compactación falta parte de estas instrucciones, por ejemplo el formato del Paso 8, releer `${CLAUDE_PLUGIN_ROOT}/commands/review.md` antes de seguir. Y si ya no está el texto de los criterios, volver a leer los `criterios-*.md` de `TIPOS` (Paso 1): la lista de severidad solo tiene los números.

**Informe** (detalle en el Paso 8): cabecera con Proyecto, Fuente, Ficheros revisados, Tests y Cobertura del diff, siempre, aunque sea para decir por qué no se hizo algo; incidencias por severidad; «Fallos ajenos al diff», si los hay; Resumen, con las descartadas; «Descartadas», con `--verbose`; y «Acciones propuestas», al final.

**Severidad**: Crítico para seguridad, corrupción de datos o bugs silenciosos (criterios #6, #13, #22, #25, #27, #30, #33, #49, #69, #74, #97). Importante para violaciones de patrón estructural que afectan a corrección o mantenibilidad. Menor para estilo, naming y convenciones. Un criterio de websites que repite uno del monorepo tiene su misma severidad.

**Límites de los Pasos 6 y 7** (cada paso tiene además los suyos): tests de backend solo con `ENTORNO_TEST=aislado`, con `APP_ENV=testing` y con ficheros concretos, nunca un directorio ni la suite entera, y con `CONEXIONES_REALES` solo si el dev lo pide; el código fuente del proyecto no se toca; ningún test generado usa `RefreshDatabase` ni `DatabaseMigrations`; **NUNCA** `git commit` ni `git push`.

**Límites de la revisión**:

- **Nunca** sugerir añadir comentarios al código.
- **Nunca** sugerir TypeScript: el frontend es JavaScript.
- **Nunca** sugerir migraciones de Laravel: los backends no las usan.
- **Nunca** sugerir redefinir las relaciones que ya da `Entitable` en todos los modelos de dominio: `creator`, `updater`, `deleter`, `status`, `uploads`, `alerts`, `comments`, `audits`, `customFieldValues`.
- **Nunca** reportar incidencias que ya estaban antes de los cambios, tampoco los class strings hardcodeados (`'App\\Models\\...'` en vez de `Model::class`): solo lo que introduce el diff.
- **Nunca** reportar lo que no tiene criterio propio y ya detectaría un linter o formateador (imports no usados, espaciado, comillas). Los criterios numerados, como #34 o #86, se aplican siempre, aunque el proyecto tenga linter.
- Cada incidencia, en una línea de descripción y otra de sugerencia, con `fichero:línea` y su criterio entre corchetes, `[#N]`. Los ficheros sin incidencias no se mencionan.

## Paso 1: Fuente y tipo de proyecto

Separar de `$ARGUMENTS` los flags (`--verbose`, `-v`) y, con lo que quede, ejecutar:

- `#N` o solo dígitos (PR): `bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh --pr N`
- una ruta: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh --path 'RUTA'`, con la ruta entre comillas simples. Con varias rutas, una ejecución por ruta.
- nada: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh`

El script elige la fuente en este orden: staged; si no hay, unstaged más los ficheros sin trackear; con el árbol limpio fuera de una rama de integración (main, master, develop, dev), la rama frente a su base, que es la de merge-base más cercana; si no, el último commit. Imprime:

- `REPO`, `RAIZ` (la raíz del repo) y, con `--path`, `ALCANCE`;
- `FUENTE` y `DIFF`, la orden que da el diff de esa fuente, lista para ejecutar tal cual desde cualquier directorio del repo, y `DIFF_U0`, el mismo diff sin contexto (Paso 7);
- con `FUENTE=staged`, `STAGED_LIMPIO` (`no` si algún fichero staged tiene además cambios sin stagear);
- `TIPOS`, `FICHEROS` y `SIN_TRACKEAR`;
- `EXCLUIDOS`: ficheros sin trackear de `.claude/`, `.idea/`, `.expo/`, `.vscode/` o `.cursor/`, que no se revisan;
- en modo PR, `PR_EN_WORKTREE` y, si la base de la PR que da GitHub está en local, `PR_BASE`;
- un `AVISO` si queda algo fuera de la revisión;
- tras `FICHEROS:`, la lista de ficheros con rutas relativas a `RAIZ` (`?? ` delante de los sin trackear).

Si sale `ERROR` (ruta que no existe o fuera del repo, fallo de git o de gh, clon superficial) o `REPO=unknown`, informar al usuario con el mensaje y terminar. Si `FICHEROS=0`, informar de que no hay cambios y terminar.

Leer en paralelo los criterios de `${CLAUDE_PLUGIN_ROOT}/references/`: `criterios-compartidos.md` siempre y, por cada tipo de `TIPOS`, `criterios-backend.md`, `criterios-frontend.md`, `criterios-mobile.md` o `criterios-websites.md`. En el monorepo, los ficheros de `apps/mobile/` son mobile y el resto (`apps/web/`, `packages/`), frontend.

## Paso 2: Obtener los cambios a revisar

Obtener el diff ejecutando `DIFF` tal cual. Los ficheros sin trackear no salen en el diff: leer enteros los que sean código. Los que no lo sean (notas `.md`, `package-lock.json`, ficheros generados) no se revisan y se listan en «sin revisar» de la cabecera del Paso 8.

Con más de 20 ficheros, revisarlos todos igualmente y avisar al empezar de que, para más detalle, conviene revisar por directorio (`/desa:review ruta`). Cualquier fichero que no se llegue a revisar va en «sin revisar» de la cabecera del Paso 8.

Indicar al usuario qué fuente se está revisando y, si hay `AVISO`, repetirlo.

## Paso 3: CLAUDE.md y memoria del proyecto

Si contienen reglas no cubiertas por los criterios, aplicarlas también. El `CLAUDE.md` del proyecto y el índice de su memoria suelen estar ya en contexto: aplicarlos sin releerlos. Si no lo están, porque la sesión se abrió en otro directorio o la memoria automática está desactivada, leer el `CLAUDE.md` de la raíz y `~/.claude/projects/{project-path}/memory/MEMORY.md`. Leer además los `CLAUDE.md` de los subdirectorios que toca el diff (en un monorepo, las reglas de `apps/web/` o `apps/mobile/` suelen estar ahí), porque el diff se obtiene con Bash y Claude Code no los carga solo.

## Paso 4: Contexto de patrones existentes

Solo cuando una incidencia potencial requiera verificación contra el código existente (criterio #1), leer un fichero del mismo directorio o dominio que sirva de referencia. No leer ficheros preventivamente — solo bajo demanda para confirmar o descartar una sospecha.

**Excepción**: Si el diff toca un Service o un archivo que pasa `include` a la API, buscar proactivamente patrones `include` con punto anidado (ej. `indicator.process`) — es un error recurrente [#74].

## Paso 5: Revisar los cambios

Analizar cada fichero modificado. Para cada posible incidencia, anotar la evidencia (la línea del diff y, en los criterios de patrón como #1, el fichero de referencia leído que lo demuestra) y una confianza de 0 a 100. **Solo se reportan las incidencias con evidencia y confianza >= 75.**

Las que no tienen evidencia o no llegan a 75 quedan fuera del informe, pero no se ocultan: se cuentan en el Resumen y, con `--verbose` o `-v`, se listan en «Descartadas» (formato en el Paso 8). La severidad y los límites están al principio de este fichero.

## Paso 6: Ejecutar tests (solo si el proyecto tiene tests configurados)

Tras la revisión estática (Pasos 1-5), si el proyecto tiene infraestructura de tests, ejecutarlos filtrados por el diff actual para verificar que los cambios no rompen nada y que la cobertura sigue siendo aceptable.

El Paso 6 se ejecuta aunque el Paso 5 haya encontrado incidencias, incluso críticas: revisión, tests y cobertura son informaciones complementarias y el dev necesita las tres para decidir. (Antes se saltaba cuando el Paso 5 marcaba código muerto.)

**Cuándo no se ejecuta** este paso ni el 7, porque los tests correrían sobre otro código:

- modo PR con `PR_EN_WORKTREE=no`, es decir, cuando el working tree no es el commit de la PR. Anotar `Tests: omitidos (la PR #N no está en el working tree)` y no hacer checkout por cuenta propia. `PR_EN_WORKTREE=si` también vale en el merge commit que deja el checkout de GitHub Actions, si el clon tiene al menos 2 commits de profundidad (con el `fetch-depth: 1` por defecto sale `no`, con un `AVISO`);
- `FUENTE=staged` con `STAGED_LIMPIO=no`: los ficheros revisados tienen además cambios sin stagear, y los tests verían el working tree. Anotar `Tests: omitidos (hay cambios sin stagear en ficheros del diff)`.

### Detección del runner de tests

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/test-context.sh
```

Imprime:

- `RAIZ` (todas las órdenes de los Pasos 6 y 7 se ejecutan desde ahí: `cd {RAIZ} && …`) y `STACK`;
- `RUNNER` (`pest`, `phpunit`, `vitest`, `no-instalado` o `ninguno`), que sale de lo que está instalado, no de que exista `phpunit.xml`;
- `COBERTURA` (`xdebug`, `pcov`, `v8`, `istanbul` o `ninguna`), solo si el driver está activo;
- `PLAYWRIGHT`, `E2E_SMOKE` (specs en `tests/e2e/smoke`) y `DIFF_COVERAGE` (si el proyecto tiene `scripts/diff-coverage.mjs`);
- en backend, `ENTORNO_TEST` y, si las hay, `CONEXIONES_REALES`: conexiones de `config/database.php` con un servidor escrito en el propio fichero (en grupodesa-backend, `spyro_transfer`, `gdapps` y `snowflake-admin`, que son de producción). `ENTORNO_TEST` solo mira la conexión por defecto, y Laravel usa estas tal cual también en tests.

- `RUNNER=ninguno` → anotar `Tests: sin runner configurado` (en el monorepo, `sin runner para este stack`) y continuar al Paso 7. No es error.
- `RUNNER=no-instalado` → anotar `Tests: no ejecutables (runner configurado pero no instalado)` y omitir el Paso 7.

### Ejecución por project type

#### project_type = backend (PHPUnit o Pest)

**Solo con `ENTORNO_TEST=aislado`.** `test-context.sh` calcula la BD que vería Laravel con `APP_ENV=testing` en este mismo entorno: la configuración cacheada, las variables del proceso, `phpunit.xml`, `.env.testing` y `.env`. Solo cuenta como aislado un sqlite de tests, fijado en `phpunit.xml` o `.env.testing` y en memoria o en un fichero fijado ahí. En otro caso, la BD suele ser la real, en algún proyecto la de producción, o la de desarrollo del dev, y un test con `RefreshDatabase` hace `migrate:fresh` sobre ella: en grupodesa-backend ya pasó con un directorio lanzado bajo `APP_ENV=local` (31-07-2026). Con `no-aislado` o `desconocido`, no ejecutar ningún test: anotar `Tests: no ejecutables (entorno de tests no aislado: {motivo de ENTORNO_TEST})` y omitir el Paso 7.

**Con `CONEXIONES_REALES`, los tests no se ejecutan solos.** Basta un test que llegue, aunque sea de rebote, a un `DB::connection('spyro_transfer')->insert(...)` para escribir en producción, y desde la revisión no se puede saber qué llamadas hace cada test. Anotar `Tests: no ejecutados (conexiones a servidores reales en config/database.php: {CONEXIONES_REALES})`, omitir el Paso 7 y ofrecer en «Acciones propuestas» ejecutarlos igualmente, con la orden exacta y la lista de tests. Solo si el dev elige esa acción, ejecutarlos como se describe abajo y seguir con el Paso 7.

Con entorno aislado, siempre con `APP_ENV=testing` delante y siempre con ficheros de test concretos, nunca un directorio ni la suite completa.

1. Derivar los ficheros de test del diff con Glob: para `app/Services/Foo/BarService.php`, los `tests/Feature/Foo/Bar*Test.php` y `tests/Unit/Foo/Bar*Test.php` que existan; un fichero de test del diff cuenta por sí mismo. Si no sale ninguno, no ejecutar nada y anotar `Tests: sin test asociado al diff`. Con `FUENTE=staged`, si alguno de esos tests tiene cambios sin stagear (`git -C {RAIZ} status --porcelain -- {fichero}` con algo en la segunda columna), no ejecutar ninguno y anotar `Tests: omitidos (el test {fichero} tiene cambios sin stagear)`: se ejecutaría una versión del test que no va en el commit.
2. Si el `CLAUDE.md` del proyecto dice que un test necesita otro `APP_ENV` o la BD real (en grupodesa-backend, los feature tests de precios y pedidos), no ejecutarlo desde la revisión: contarlo como «requiere BD real, no ejecutado».
3. Escribir la orden exacta y ejecutarla en una sola llamada, con una ejecución del runner por fichero de test:
    ```bash
    cd {RAIZ} && for t in tests/Feature/Foo/BarServiceTest.php tests/Unit/Foo/BarTest.php; do APP_ENV=testing ./vendor/bin/{RUNNER} "$t"; echo "EXIT=$? $t"; done
    ```
    Un fichero por ejecución porque PHPUnit 9 y 10 solo ejecutan el primero que se les pasa e ignoran el resto sin avisar: con varios, el verde sería falso. Nunca pasar rutas en `--filter`: compara nombres de test, no rutas, y con una ruta no ejecuta nada y sale con 0.
    Si `COBERTURA` es `xdebug` o `pcov`, esta otra orden sustituye a la anterior. Deja un informe por fichero de test en un directorio nuevo, fuera del repo (con pcov, sin `XDEBUG_MODE=coverage`):
    ```bash
    COV=$(mktemp -d) && cd {RAIZ} && i=0 && for t in {ficheros}; do i=$((i + 1)); XDEBUG_MODE=coverage APP_ENV=testing ./vendor/bin/{RUNNER} --coverage-clover "$COV/$i.xml" "$t"; echo "EXIT=$? $t"; done; echo "COV=$COV"
    ```
    Si falta algún informe tras la ejecución o la salida trae «No filter is configured», «Incorrect filter configuration» o «has to be set», el runner no ha generado informe: anotar `Cobertura del diff: no disponible (el runner no generó informe: {aviso})`. PHPUnit 11 ignora el `<coverage><include>` antiguo de `phpunit.xml` y pide `<source>`. Con `COBERTURA=ninguna`, anotar `Cobertura del diff: no disponible (sin xdebug ni pcov)`: el Paso 7 no se ejecuta.
4. El resultado de cada fichero es su línea `EXIT=`, no el código de salida de la llamada, que es el del último `echo`. Contar pasados, saltados y fallidos sumando los de todos los ficheros. Con `APP_ENV=testing`, los tests que necesitan MySQL se saltan por su guard: cuentan como saltados, no como pasados.

#### project_type = websites (Vitest + opcional Playwright)

1. Ejecutar la suite unitaria entera, como hace CI. En websites es segura (jsdom y MSW, sin BD ni red real) y así la cobertura coincide con la de CI:
    ```bash
    cd {RAIZ} && npx vitest run --coverage
    ```
    Sin `COBERTURA` (`ninguna`), ejecutar sin `--coverage` y anotar `Cobertura del diff: no disponible (sin @vitest/coverage-v8)`.
2. Si `PLAYWRIGHT=si` y hay specs de `tests/e2e/smoke/` relacionadas con el diff, ejecutar también `npx playwright test [specs]`. Si `E2E_SMOKE=0`, omitir Playwright y añadirlo a la línea de Tests (` · E2E: sin specs`).

#### project_type = frontend (monorepo) y mobile

El equipo aún no ha definido el runner de tests del monorepo ni el de mobile (probable Jest). Anotar `Tests: sin runner para este stack` y continuar al Paso 7.

### Interpretación del resultado

- **Todos los tests pasan** (en backend, todas las líneas `EXIT=0`) → Anotar para la línea `Tests` del Paso 8: `N pasados · M saltados · K fallidos`, con la orden usada. Si el runner no ha ejecutado ningún test («No tests executed!», 0 tests), no es verde: anotar `Tests: 0 ejecutados` y el motivo. Continuar al Paso 7.
- **Algún test falla** → Anotar `fichero:test:error` y, por cada test que falla, diagnosticar antes de proponer nada:
    - **Regresión**: el cambio rompe un comportamiento que el test protege. Es una incidencia **Crítica** del informe, y la acción propuesta es corregir el código fuente, no el test.
    - **Test desactualizado**: el cambio de comportamiento es intencionado (lo dicen el diff, el mensaje del commit o el usuario). La acción propuesta es actualizar el test.
    - **Fallo ajeno al diff**: el test no cubre código del diff y el error apunta a otra causa (datos, red, un deadlock, un test inestable). Va al apartado «Fallos ajenos al diff» del Paso 8, sin acción propuesta, y no cuenta como rojo para el Paso 7.

    No tocar nada durante la revisión. Las correcciones van al bloque «Acciones propuestas» del Paso 8, al final del informe completo, y el fallo se queda en el informe aunque después se corrija. Si el dev elige alguna acción, aplicarla y volver a ejecutar los tests afectados (máximo 3 iteraciones); si vuelve a verde, seguir con el Paso 7 y actualizar el informe. Si tras 3 iteraciones sigue fallando, devolver el control al dev sin más cambios.
- **Tests no ejecutables** (error de configuración, no error de test) → Anotar `Tests: no ejecutables ({motivo})` y omitir el Paso 7, sin intentar arreglar la configuración.

### Límites de esta fase

- **Nunca** modificar el código fuente del proyecto en esta fase. Una regresión se reporta como Crítica con la corrección propuesta. Solo se aplica si el dev la elige en «Acciones propuestas», al final del informe.
- **Nunca** generar tests nuevos aquí — eso es Paso 7.
- **Nunca** continuar al Paso 7 mientras haya una regresión o un test desactualizado sin resolver. Los fallos ajenos al diff no bloquean.
- **Nunca** ejecutar tests de backend sin `ENTORNO_TEST=aislado`, ni un directorio, una suite completa o un `APP_ENV` distinto de `testing`. Con `CONEXIONES_REALES`, solo si el dev lo elige en «Acciones propuestas».

## Paso 7: Generar tests faltantes (solo si Paso 6 pasó y la cobertura es insuficiente)

Solo se ejecuta esta fase si:

1. El Paso 6 acabó en verde: todos los tests ejecutados pasan, salvo los fallos ajenos al diff
2. El reporte de cobertura muestra **líneas nuevas/modificadas del diff sin cubrir** en alguno de los ficheros del diff (independiente de cualquier umbral global del proyecto; en `desa-websites` el gate es de patch coverage por diff, no global)

Si no hay líneas del diff sin cubrir, anotar `Cobertura del diff: sin líneas sin cubrir` y continuar al Paso 8. Si el Paso 6 no dio cobertura (sin runner, sin driver o tests omitidos), anotar `Cobertura del diff: no disponible ({motivo})`. Si el Paso 6 acabó en rojo (una regresión o un test desactualizado sin resolver), con tests no ejecutables o con 0 tests ejecutados, anotar `Cobertura del diff: no evaluada ({motivo})`.

El Paso 7 tampoco depende del Paso 5: se ejecuta aunque el Paso 5 haya tachado los cambios de código muerto u over-engineering, porque el dev decide con el informe completo si borra el código o se queda los tests. En la validación de la 1.8.0, la revisión propuso borrar el código en vez de generar los tests, y la regla existe para que el Paso 7 no se lo salte.

### Identificación de gaps

- **websites con `DIFF_COVERAGE=si` y una base** (`FUENTE=rama:{base}...HEAD`, o modo PR con `PR_BASE`): usar el script del propio proyecto, que CI aplica sobre el mismo lcov de la suite entera (80 % de las líneas nuevas):
    ```bash
    cd {RAIZ} && DIFF_COVERAGE_BASE={base o PR_BASE} node scripts/diff-coverage.mjs
    ```
    Lista, por fichero, las líneas nuevas sin cubrir. Sale con 1 cuando no llega al 80 %: no es un error del script. Mide todo `src/`, así que con `ALCANCE` hay que quedarse solo con los ficheros de esa ruta. Solo mira cambios commiteados: no sirve con `FUENTE=staged` o `unstaged`.
- **En el resto de casos**, cruzar el informe de cobertura del Paso 6 (`coverage/lcov.info` en websites, los informes del directorio `COV` en backend) con las líneas añadidas que da `DIFF_U0`, ejecutado tal cual. En backend hay un informe por fichero de test, y cada uno marca con `count="0"` las líneas que solo ejecutan los demás: una línea está cubierta si algún informe le da `count` mayor que 0. Los ficheros sin trackear (`?? ` en la lista del Paso 1) no salen en `DIFF_U0`: todas sus líneas cuentan como añadidas. En modo PR sin `PR_BASE`, `DIFF_U0` viene vacío: sacar las líneas añadidas de los `@@` del diff del Paso 2 (`gh pr diff N`), que es el que ve GitHub.

De ahí salen los ficheros con líneas nuevas o modificadas sin cubrir, y las funciones y ramas concretas que faltan.

### Generación de tests (bucle máx. 3 iteraciones)

Para cada gap detectado:

1. **Leer el código sin cubrir** del fichero fuente
2. **Leer un test existente del mismo dominio** como referencia de estilo y patrones (estructura `describe()/it()`, uso de fixtures, mocks). En backend, seguir los moldes que dé el `CLAUDE.md` del proyecto (en grupodesa-backend, el unitario sin BD de `tests/Unit/Shared/RegionTest` con la conexión bloqueada)
3. **Generar el test** siguiendo ese patrón. Si el fichero fuente ya tiene test, añadir el caso ahí. Si no, crear uno nuevo junto a los tests vecinos del mismo directorio:
    - backend: `tests/Unit/{Domain}/` o `tests/Feature/{Domain}/`
    - websites: el directorio de `tests/unit/` donde están los tests de ficheros vecinos (p. ej. `tests/unit/hooks/` para `src/hooks/`)
4. **Ejecutar el test recién generado** con el mismo runner y las mismas reglas del Paso 6:
    - backend: `cd {RAIZ} && APP_ENV=testing ./vendor/bin/{RUNNER} tests/ruta/NuevoTest.php`, un fichero por ejecución
    - websites: `cd {RAIZ} && npx vitest run tests/unit/ruta/nuevo.test.{js,jsx}`
5. **Si pasa** → siguiente gap
6. **Si falla** → leer error, corregir el test (nunca el código fuente), reintentar
7. **Si tras 3 iter sigue fallando** → borrar el borrador del árbol y llevarlo al informe con el último error. No dejar en el repo tests rojos ni comentarios `FIXME`

### Tras procesar todos los gaps

- `git add` solo de los ficheros de test que ha creado la skill, y de los que ha modificado si antes no tenían cambios del dev (comprobarlo con `git -C {RAIZ} status --porcelain -- {fichero}` antes de tocarlos). Si un test ya tenía cambios del dev, dejarlo sin stagear y listarlo: un `git add` metería también hunks que el dev no quería
- **NUNCA** `git commit` ni `git push`
- Anotar para la línea `Cobertura del diff` del Paso 8: líneas sin cubrir, tests generados y gaps que no han convergido

### Límites de esta fase

- **Nunca** generar tests sobre código que ya tenía fallos antes de los cambios del dev
- **Nunca** mockear `fetch` directamente si MSW (websites) o Mocks/Factories (backend) ya están en juego. Usar fixtures existentes o crear nuevas explícitamente
- **Nunca** generar tests para Server Components async en websites (limitación documentada del runtime — ver F-005 en `desa-websites/docs/superpowers/findings.md`)
- **Nunca** modificar código de producción para hacer pasar un test generado. Si un test no se puede escribir sin tocar el fuente, abortar ese gap y reportarlo al dev
- **Usar fixtures de `tests/fixtures/api/` en websites** y factories existentes en backend. Nada de JSON enorme escrito dentro de los tests
- **Estilo de assertions** debe coincidir con tests existentes del mismo dominio (no introducir `chai`/`should` si el proyecto usa `expect` de vitest, etc.)
- **Nunca** usar `RefreshDatabase` ni `DatabaseMigrations` en un test generado: lanzan `migrate:fresh` sobre la BD que haya configurada, y en algún proyecto esa BD es la de producción
- **Nunca** generar un test que llegue a una de `CONEXIONES_REALES` (`DB::connection('…')` o un modelo con esa `$connection`). Si el código sin cubrir la usa, ese hueco no se cubre y se informa

## Paso 8: Formato de salida

```
## Revisión de código

**Proyecto**: {TIPOS: backend | frontend | mobile | websites | frontend + mobile}
**Fuente**: {staged | unstaged | rama frente a {base} | último commit | PR #N}{, limitado a {ruta}}
**Ficheros revisados**: {N} de {FICHEROS}{ (K sin trackear, leídos enteros)}{ · sin revisar: …}
**Tests**: {valor de la tabla de abajo}
**Cobertura del diff**: {valor de la tabla de abajo}
{**Aviso**: {AVISO del Paso 1}, solo si lo hubo}

---

### Crítico (bugs, seguridad)

- **fichero:línea** — Descripción del problema [#N]
  → Sugerencia de corrección

### Importante (violaciones de patrón)

- **fichero:línea** — Descripción del problema [#N]
  → Sugerencia de corrección

### Menor (estilo, convenciones)

- **fichero:línea** — Descripción del problema [#N]
  → Sugerencia de corrección

---

**Resumen**: X críticos · Y importantes · Z menores{ · D descartadas}
```

Si el Paso 6 encontró fallos ajenos al diff, van entre las incidencias y el Resumen:

```
### Fallos ajenos al diff

- `Test::test_z` — {error} ({por qué no tiene que ver con el diff})
```

El informe termina siempre en este orden: incidencias, «Fallos ajenos al diff», Resumen, «Descartadas» (con `--verbose`) y «Acciones propuestas». Las acciones van en cualquiera de las dos plantillas, también en la de «Sin incidencias», y la pregunta es lo último del informe. Si el Paso 6 dejó correcciones pendientes (tests en rojo), el bloque es:

```
### Acciones propuestas

1. **Regresión** en `fichero:línea` (rompe `Test::test_x`) → corregir el código: {cambio}
2. **Test desactualizado** `Test::test_y` por el cambio intencionado de {…} → actualizar el test: {cambio}

¿Aplico alguna? Indica los números.
```

Con `CONEXIONES_REALES`, la acción para ejecutar los tests es:

```
N. **Ejecutar los tests del diff** aunque `config/database.php` tenga conexiones a servidores reales ({CONEXIONES_REALES}): `{orden del Paso 6}`. Solo si ninguno de estos tests llega a esas conexiones: {tests}
```

Si modo verbose (`--verbose` o `-v`), añadir antes de «Acciones propuestas»:

```
### Descartadas (sin evidencia o confianza < 75)

- **fichero:línea** — Descripción (confianza: N; evidencia: {la que hay o «ninguna»}) [#N]
```

Valores de las líneas `Tests` y `Cobertura del diff`:

| Línea | Valor | Cuándo |
|---|---|---|
| Tests | `N pasados · M saltados · K fallidos` | se ejecutaron tests; añadir ` · F ajenos al diff` si algún fallido lo es, ` · C tests existentes corregidos` si el bucle del Paso 6 los modificó, ` · R requieren BD real, no ejecutados` si hubo alguno y ` · E2E: sin specs` si aplica |
| Tests | `0 ejecutados ({motivo})` | el runner no ejecutó ninguno: no es verde |
| Tests | `sin runner configurado` | no hay runner (Paso 6) |
| Tests | `sin runner para este stack` | monorepo y mobile |
| Tests | `sin test asociado al diff` | no hay ningún test de los ficheros del diff |
| Tests | `R requieren BD real, no ejecutados` | todos los tests del diff necesitan la BD real |
| Tests | `no ejecutables (entorno de tests no aislado: {motivo})` | backend con `ENTORNO_TEST` distinto de `aislado` |
| Tests | `no ejecutados (conexiones a servidores reales en config/database.php: {nombres})` | backend aislado con `CONEXIONES_REALES`, mientras el dev no elija ejecutarlos |
| Tests | `omitidos (hay cambios sin stagear en ficheros del diff)` | `FUENTE=staged` con `STAGED_LIMPIO=no` |
| Tests | `omitidos (el test {fichero} tiene cambios sin stagear)` | `FUENTE=staged` y un test derivado del diff con cambios sin stagear |
| Tests | `no ejecutables ({motivo})` | error de configuración, no de test |
| Tests | `omitidos (la PR #N no está en el working tree)` | modo PR con `PR_EN_WORKTREE=no` |
| Cobertura del diff | `sin líneas sin cubrir` | el Paso 7 no encontró huecos |
| Cobertura del diff | `K líneas sin cubrir → T tests generados, G sin converger` | el Paso 7 se ejecutó |
| Cobertura del diff | `no evaluada ({tests en rojo · no ejecutables · 0 ejecutados})` | el Paso 7 no se ejecutó por el resultado del Paso 6 |
| Cobertura del diff | `no disponible ({motivo})` | sin runner, sin driver de cobertura, tests omitidos o no ejecutados por conexiones reales, sin test asociado, solo tests de BD real o el runner no generó informe |

Omitir secciones de severidad vacías. Las líneas de cabecera no se omiten: si algo no se ha hecho, la línea dice por qué, para que «tests en verde» y «no se ejecutó nada» no se confundan. Si no hay incidencias:

```
## Revisión de código

**Proyecto**: {TIPOS}
**Fuente**: {…}
**Ficheros revisados**: {N} de {FICHEROS}{ (K sin trackear, leídos enteros)}{ · sin revisar: …}
**Tests**: {…}
**Cobertura del diff**: {…}
{**Aviso**: {AVISO del Paso 1}, solo si lo hubo}

Sin incidencias. Los cambios cumplen con los estándares del equipo.
{**Resumen**: 0 incidencias · D descartadas, solo si D > 0; con `--verbose`, sigue «Descartadas»}
```
