---
description: Planificar una tarea antes de implementarla. Usar cuando la tarea ya está acotada (p. ej. tras /desa:triage) y hay que decidir qué tocar. Explora el código, inventaría lo reutilizable, aplica los criterios de /desa:review y termina con un plan que el usuario aprueba en plan mode
argument-hint: [descripción de la tarea]
allowed-tools: Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh:*), Read, Grep, Glob, Agent
---

# Plan — Planificación con estándares Grupo Desa

Convierte una tarea en un plan ejecutable que el usuario aprueba antes de implementar, aplicando los criterios de `/desa:review` *antes* de escribir código y priorizando la reutilización de lo que ya existe.

Si `$ARGUMENTS` está vacío, pedir al usuario la descripción de la tarea y terminar.

**Plan mode.** El plan se aprueba con `ExitPlanMode`, y el fichero del plan solo tiene ruta asignada en plan mode. Si el system reminder no indica plan mode, llamar a `EnterPlanMode` antes del Paso 3. Si no está disponible o el usuario prefiere no usarlo, entregar el plan en el chat sin escribir ficheros, y terminar ahí.

**Si viene de `/desa:triage`**, lo que el triage dejó cerrado no se vuelve a explorar: su comprobación descalificante ya está respondida y lo descartado sigue descartado. Llevar al Context del plan su «Medido» y su regla de paro, si vienen en la invocación o siguen en el contexto; si no, dejarlos fuera y decirlo, sin reconstruirlos. Si la petición es un síntoma o una decisión y no hay triage previo, sugerir `/desa:triage` en una línea y seguir.

## Paso 1: Detectar tipo de proyecto

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh --repo
```

- `REPO=backend` → backend.
- `REPO=websites` → websites.
- `REPO=monorepo` → frontend, mobile o los dos según la tarea (`APPS` dice qué apps existen). `apps/mobile/` es mobile y el resto (`apps/web/`, `packages/`) frontend, igual que en `/desa:review`: una tarea de mobile que añade un hook en `packages/core` lleva los dos ficheros de criterios, el de frontend y el de mobile. Si `$ARGUMENTS` no lo deja claro, cargar los dos en el Paso 2 y quedarse con los que correspondan al redactar el borrador, cuando la exploración lo aclare.
- `REPO=unknown` o `ERROR` → informar al usuario y terminar.

El tipo sale del repositorio y de la tarea, no del diff: al planificar, los cambios de la tarea aún no existen y lo que haya en el árbol es otro trabajo.

## Paso 2: Cargar contexto fijo

- `CLAUDE.md` del proyecto e índice de memoria: si ya están en contexto, aplicarlos sin releerlos. Si no, porque la sesión se abrió en otro directorio o la memoria automática está desactivada, leer el `CLAUDE.md` del proyecto y `~/.claude/projects/{project-path}/memory/MEMORY.md`. Leer además las notas de memoria cuyo título sea del dominio de la tarea.
- Los criterios de `/desa:review` del tipo detectado, en paralelo desde `${CLAUDE_PLUGIN_ROOT}/references/`: `criterios-compartidos.md` siempre, más `criterios-backend.md`, `criterios-frontend.md`, `criterios-mobile.md` o `criterios-websites.md`.

## Paso 3: Explorar (paralelo, adaptativo)

Decidir número de Explore agents según `$ARGUMENTS`:

- **Tarea trivial** (rename, path específico, cambio de una línea) → **0 agents**. Usar Read/Grep directos.
- **Tarea media** (un endpoint, un componente) → **1 Explore agent**.
- **Tarea amplia o de scope incierto** → **hasta 3 Explore agents en paralelo** (un solo mensaje, múltiples tool calls), cada uno con foco distinto:
  1. **Patrones existentes en el dominio**: archivos del mismo dominio o similar que sirvan de referencia.
  2. **Helpers/hooks/servicios reutilizables**: grep en `packages/core/src/hooks`, `app/Services`, `app/Models`, `app/Http/Resources` (en websites, `src/hooks`, `src/lib`, `src/api/services`) para encontrar código que evite reimplementar.
  3. **Referencias de test / casos límite**: tests existentes de código similar para entender qué edge cases validar.

Cada agent debe devolver **rutas exactas con números de línea**, no descripciones vagas.

## Paso 4: Borrador del plan

Redactar un borrador, que todavía no se enseña al usuario, con:

- **Reuse inventory**: lista de funciones/hooks/componentes/servicios existentes que se van a reusar, con `file_path:line`.
  - Si la lista está vacía en una tarea no trivial, reintentar la búsqueda antes de seguir. La causa #1 de mala planificación es reinventar lo que ya existe.
- **Archivos a modificar**: rutas exactas.
- **Archivos a crear**: solo si son imprescindibles; justificar por qué no se puede reusar algo existente.
- **Cambios clave por archivo**: 1–3 líneas por archivo, sin pseudocódigo extenso.
- **Supuestos sin comprobar**: lo que el plan da por cierto sin haberlo visto en el código (p. ej. «el Service ya filtra por rol»), y qué lo confirmaría.

Al redactar cada cambio, tener en cuenta:

- **Caminos infelices** que apliquen a ese cambio: estado vacío o nulo, errores esperados, permisos y roles, concurrencia, datos existentes que puedan romper al aplicarlo. En backend, además, entidades con soft-delete y transacciones completas con try/catch. En el plan se anotan solo los que apliquen.
- **Simplificación**: nada de abstracciones que no hagan falta, wrappers triviales, configurabilidad sobrante, soluciones «clever» ni pasos «para el futuro» (#9). Si se puede borrar código en vez de añadir, o reusar más de lo inventariado, hacerlo.

## Paso 5: Comprobar contra los criterios de review

Para cada archivo planificado, comprobar las reglas cargadas en el Paso 2 que le apliquen. Ejemplos típicos según tipo:

**Backend**: whitelist de roles (#13, #33), `entityQuery()` al inicio de `query()` (#27), transacción + try/catch (#22), `event()`/`broadcast()` después de `commit()` (#23), `withTrashed()` en morphTo/belongsTo a soft-deletable (#30), Resource con `addEntityRelations` (#20), controller ultra-thin (#26), audit trail en save (#28), guardia de estado en save/delete (#29), convenciones HTTP (#31), naming de Events (#32).

**Frontend**: `useCustomNavigate` no `useNavigate` (#58), `memo()` + `useCallback` en `*TableBody` y filas (#54, #59), `useTable`/`useFilter` para listados (#60), `i18next.t()` nunca a nivel módulo (#69), no `fal` (solo `fasr`/`fass`) (#49), `ActionTypography` para códigos copiables (#50), API `include` siempre plano (#74), `TextNumericFormat` para números (#75), `import * as XService` (#55), `useDisplayColumn` para columnas opcionales (#61), `hasRole(..., false)` para portal exclusivo (#64).

**Mobile**: `useTheme()` no `StyleSheet.create` (#65), reuso de `packages/core` antes de reimplementar (#82), screens sin lógica de componentes (#83), naming de theme = componente RN (#84, #85).

**Websites**: `LocaleLink` en Client Components y `localePath()` en Server Components (#98), imports directos de MUI (#99), Server Components por defecto (#100), desestructurar `.data` y comprobar `null` (#101), `fetch` solo vía `api.js` (#102), ISR con las constantes `REVALIDATE` (#103), lógica testable fuera de los Server Components async (#104), `i18next.t()` nunca a nivel módulo (#97).

Si el borrador viola alguna, corregirlo.

## Paso 6: Escribir plan file

Escribir el plan consolidado en la ruta que el sistema de plan mode haya asignado (el entorno la indica en el system reminder, p.ej. `/Users/.../.claude/plans/{name}.md`). Estructura:

```markdown
# Plan — {resumen corto de la tarea}

## Context
{por qué se hace esta tarea, qué problema resuelve, resultado esperado}

## Reuse inventory
- `file_path:line` — qué función/hook/componente/servicio y cómo se usa

## Archivos a modificar
- `path/exact.ext` — qué cambia (1-3 líneas)

## Archivos a crear (solo si imprescindible)
- `path/exact.ext` — justificación de por qué no existe ya algo reusable

## Cambios clave
{descripción del approach, sin pseudocódigo extenso}

## Supuestos sin comprobar
- {supuesto} — qué lo confirmaría

## Verificación
- Cómo probar end-to-end (comandos, rutas UI, tests a correr)
- Edge cases específicos a validar manualmente

## Reglas aplicadas
Lista de los #N de los criterios de `/desa:review` (`references/criterios-*.md`) más relevantes que el plan ya respeta (trazabilidad).
```

## Paso 7: Salir con ExitPlanMode

Llamar a `ExitPlanMode` para que el usuario apruebe antes de implementar.

## Límites

- **Nunca implementar** en la misma invocación. El valor del plan está en que el usuario lo apruebe en `ExitPlanMode` antes de tocar código.
- **Nunca proponer código nuevo** sin antes haber hecho la búsqueda de reuso (Paso 3) y listado Reuse inventory (Paso 4).
- **Nunca escribir pseudocódigo largo** en el plan: referenciar archivos y líneas, para que se pueda revisar de un vistazo.
- **Siempre** referenciar los `#N` de review que aplican, sin copiar el texto de los criterios.
