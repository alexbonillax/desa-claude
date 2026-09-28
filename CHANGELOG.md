# Changelog

All notable changes to the `desa` plugin will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
