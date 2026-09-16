# Changelog

All notable changes to the `desa` plugin will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
