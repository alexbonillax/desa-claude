---
description: Planificar una tarea con exploración, review-awareness y 3 iteraciones de mejora antes de implementar
argument-hint: [descripción de la tarea]
allowed-tools: Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh:*), Read, Grep, Glob, Agent
---

# Plan — Planificación con estándares Grupo Desa

Convierte un prompt de tarea en un plan ejecutable y pulido, aplicando los criterios de `/desa:review` *antes* de implementar y priorizando la reutilización de código existente.

Si `$ARGUMENTS` está vacío, pedir al usuario la descripción de la tarea y terminar.

## Paso 1: Detectar tipo de proyecto

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh --repo
```

- `REPO=backend` → backend.
- `REPO=websites` → websites.
- `REPO=monorepo` → frontend, mobile o los dos según la tarea (`APPS` dice qué apps existen). `apps/mobile/` es mobile y el resto (`apps/web/`, `packages/`) frontend, igual que en `/desa:review`: una tarea de mobile que añade un hook en `packages/core` lleva las dos secciones. Si `$ARGUMENTS` no lo deja claro, cargar las dos en el Paso 2 y quedarse con las que correspondan al redactar el borrador, cuando la exploración lo aclare.
- `REPO=unknown` o `ERROR` → informar al usuario y terminar.

El tipo sale del repositorio y de la tarea, no del diff: al planificar, los cambios de la tarea aún no existen y lo que haya en el árbol es otro trabajo.

## Paso 2: Cargar contexto fijo

Leer en paralelo:

- `CLAUDE.md` del proyecto (si existe).
- `~/.claude/projects/{project-path}/memory/MEMORY.md` (si existe) — aplicar cualquier feedback o convención relevante.
- `${CLAUDE_PLUGIN_ROOT}/commands/review.md` — la sección «Criterios compartidos» siempre, más la del tipo detectado, por su encabezado:
  - backend → «Criterios backend (Laravel/PHP)»
  - frontend → «Criterios frontend (React/JS)»
  - mobile → «Criterios mobile (React Native)», más #65, que está en la sección de frontend
  - websites → «Criterios websites (Next.js single-app)»

## Paso 3: Explorar (paralelo, adaptativo)

Decidir número de Explore agents según `$ARGUMENTS`:

- **Tarea trivial** (rename, path específico, cambio de una línea) → **0 agents**. Usar Read/Grep directos.
- **Tarea media** (un endpoint, un componente) → **1 Explore agent**.
- **Tarea amplia o de scope incierto** → **hasta 3 Explore agents en paralelo** (un solo mensaje, múltiples tool calls), cada uno con foco distinto:
  1. **Patrones existentes en el dominio**: archivos del mismo dominio o similar que sirvan de referencia.
  2. **Helpers/hooks/servicios reutilizables**: grep en `packages/core/src/hooks`, `app/Services`, `app/Models`, `app/Http/Resources` (en websites, `src/hooks`, `src/lib`, `src/api/services`) para encontrar código que evite reimplementar.
  3. **Referencias de test / casos límite**: tests existentes de código similar para entender qué edge cases validar.

Cada agent debe devolver **rutas exactas con números de línea**, no descripciones vagas.

## Paso 4: Draft inicial del plan

Producir internamente un borrador que contenga:

- **Reuse inventory**: lista de funciones/hooks/componentes/servicios existentes que se van a reusar, con `file_path:line`.
  - Si la lista está vacía en una tarea no trivial, reintentar la búsqueda antes de seguir. La causa #1 de mala planificación es reinventar lo que ya existe.
- **Archivos a modificar**: rutas exactas.
- **Archivos a crear**: solo si son imprescindibles; justificar por qué no se puede reusar algo existente.
- **Cambios clave por archivo**: 1–3 líneas por archivo, sin pseudocódigo extenso.

## Paso 5: 3 iteraciones de mejora (focos predefinidos)

Cada iteración revisa el borrador completo con un foco distinto. Ajustar el plan tras cada pasada.

### Iteración 1 — Edge cases y correctness

Preguntar explícitamente para cada cambio:

- ¿Qué pasa con estado vacío / nulo?
- ¿Errores esperados y su manejo?
- ¿Permisos y roles afectados?
- ¿Concurrencia / race conditions?
- ¿Entidades con soft-delete involucradas?
- ¿Transacciones completas con try/catch?
- ¿Datos existentes que puedan romper al aplicar el cambio?

### Iteración 2 — Compliance con review.md

Para cada archivo planificado, comprobar explícitamente las reglas relevantes cargadas en Paso 2. Ejemplos típicos según tipo:

**Backend**: whitelist de roles (#13, #33), `entityQuery()` al inicio de `query()` (#27), transacción + try/catch (#22), `event()`/`broadcast()` después de `commit()` (#23), `withTrashed()` en morphTo/belongsTo a soft-deletable (#30), Resource con `addEntityRelations` (#20), controller ultra-thin (#26), audit trail en save (#28), guardia de estado en save/delete (#29), convenciones HTTP (#31), naming de Events (#32).

**Frontend**: `useCustomNavigate` no `useNavigate` (#58), `memo()` + `useCallback` en `*TableBody` y filas (#54, #59), `useTable`/`useFilter` para listados (#60), `i18next.t()` nunca a nivel módulo (#69), no `fal` (solo `fasr`/`fass`) (#49), `ActionTypography` para códigos copiables (#50), API `include` siempre plano (#74), `TextNumericFormat` para números (#75), `import * as XService` (#55), `useDisplayColumn` para columnas opcionales (#61), `hasRole(..., false)` para portal exclusivo (#64).

**Mobile**: `useTheme()` no `StyleSheet.create` (#65), reuso de `packages/core` antes de reimplementar (#82), screens sin lógica de componentes (#83), naming de theme = componente RN (#84, #85).

**Websites**: `LocaleLink` en Client Components y `localePath()` en Server Components (#98), imports directos de MUI (#99), Server Components por defecto (#100), desestructurar `.data` y comprobar `null` (#101), `fetch` solo vía `api.js` (#102), ISR con las constantes `REVALIDATE` (#103), lógica testable fuera de los Server Components async (#104), `i18next.t()` nunca a nivel módulo (#97).

Si el borrador viola alguna regla, corregirlo antes de la siguiente pasada.

### Iteración 3 — Simplificación

Preguntas obligatorias:

- ¿Hay alguna abstracción nueva propuesta que realmente no hace falta?
- ¿Se puede borrar código en vez de añadir?
- ¿Se puede reusar *más* de lo inventariado en el Paso 4?
- ¿Algún paso del plan es especulativo / for-future-use? Eliminarlo.
- ¿Sobra configurabilidad, wrappers triviales o soluciones "clever"? (#9)

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

## Verificación
- Cómo probar end-to-end (comandos, rutas UI, tests a correr)
- Edge cases específicos a validar manualmente

## Reglas aplicadas
Lista de los #N de review.md más relevantes que el plan ya respeta (trazabilidad).
```

## Paso 7: Salir con ExitPlanMode

Llamar a `ExitPlanMode` para que el usuario apruebe antes de implementar.

## Reglas estrictas

- **Nunca implementar** en la misma invocación. El comando termina con ExitPlanMode.
- **Nunca proponer código nuevo** sin antes haber hecho la búsqueda de reuso (Paso 3) y listado Reuse inventory (Paso 4).
- **Nunca escribir pseudocódigo largo** en el plan; referenciar archivos y líneas.
- **Siempre** referenciar los `#N` de `review.md` que aplican, para trazabilidad.
- **Nunca** duplicar criterios de `review.md` en el plan file — solo listar los `#N`.
- Si `$ARGUMENTS` está vacío, pedir la descripción de la tarea y terminar sin planificar.
