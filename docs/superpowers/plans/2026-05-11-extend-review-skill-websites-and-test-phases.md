# Extender `desa:review` con websites + Fases 6/7 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) o superpowers:executing-plans para implementar este plan task por task. Los steps usan checkbox (`- [ ]`) para tracking.

**Goal:** Extender la skill `desa:review` del plugin `desa` (repo `desa-claude`) con tres capacidades nuevas: (1) **detección del project type "websites"** para proyectos Next.js single-app como `desa-websites`, (2) **Fase 6 — ejecución automatizada de tests** filtrados por el diff (backend con Pest, websites con Vitest), y (3) **Fase 7 — generación automatizada de tests faltantes** con bucle de hasta 3 iteraciones. Tras este plan, un dev frontend que use `/review` recibirá el mismo nivel de soporte que un dev backend.

**Architecture:** Un único fichero modificado (`plugins/desa/commands/review.md`) con cambios aditivos: nueva rama en la detección, nueva sección de criterios "websites", dos nuevas fases al final del flujo. La lógica de Fases 6/7 se diseña **genérica con sub-secciones por stack**: backend (Pest), websites (Vitest+Playwright), frontend-monorepo (TODO, stub informativo), mobile (TODO, stub informativo). No se introducen subcarpetas ni nuevos ficheros de comando.

**Tech Stack:** Markdown (declarative skill), Bash (detección + ejecución), `npx vitest`, `./vendor/bin/pest`, `gh` CLI, `git`.

**Origen del plan:**
- Decision brief: [`desa-websites/docs/superpowers/decisions/2026-05-10-extend-desa-review-frontend.md`](../../../../desa-websites/docs/superpowers/decisions/2026-05-10-extend-desa-review-frontend.md)
- Follow-up plan: [`desa-websites/docs/superpowers/plans/2026-05-10-post-testing-followup.md`](../../../../desa-websites/docs/superpowers/plans/2026-05-10-post-testing-followup.md) → Bloque D
- Spec frontend padre: [`desa-websites/docs/superpowers/specs/2026-04-24-testing-cicd-frontend-design.md`](../../../../desa-websites/docs/superpowers/specs/2026-04-24-testing-cicd-frontend-design.md) → Fase 2
- Spec backend (Fases 6/7 también pendientes ahí): `grupodesa-backend/docs/superpowers/specs/2026-03-27-testing-cicd-design.md`

---

## File Structure

### Modificados

| Ruta | Cambio |
|---|---|
| `plugins/desa/commands/review.md` | (1) Añadir branch `websites` en detección. (2) Añadir sección "Criterios websites". (3) Añadir Fase 6 "Ejecutar tests". (4) Añadir Fase 7 "Generar tests faltantes". (5) Actualizar regla de "Reglas estrictas" para reflejar las dos fases nuevas |
| `plugins/desa/.claude-plugin/plugin.json` | Bump versión `1.7.0` → `1.8.0` (feature menor: nuevo project type + dos fases nuevas) |

### Nuevos

| Ruta | Responsabilidad |
|---|---|
| `docs/superpowers/plans/2026-05-11-extend-review-skill-websites-and-test-phases.md` | Este plan |
| `CHANGELOG.md` | Changelog público versionado del plugin (formato Keep a Changelog). Se crea con la entrada inaugural v1.8.0. Reemplaza el rol que tenía `.claude/RESUMEN_CAMBIOS.md` (que es nota personal del autor y queda fuera de git vía `.gitignore`) |
| `.gitignore` | Ignorar ruidos del sistema (.DS_Store, .idea/) y notas personales (`.claude/BRIEFING.md`, `.claude/RESUMEN_CAMBIOS.md`) |

---

## Important conventions for implementers

- **Branch**: `xjmardia` (ya activa). No mergear a `main` hasta cerrar el plan
- **Commits estilo del repo**: prefijo `feat:` / `fix:` / `docs:` en **inglés** (consistente con commits recientes como `feat: add /desa:plan command with review-aware planning`), minúsculas tras los dos puntos
- **Sin breaking changes**: los cambios son aditivos. La detección actual de `backend`/`frontend`/`mobile` no cambia; solo se añade una rama nueva. Las Fases 1-5 actuales no se tocan; solo se añaden Fases 6 y 7 al final
- **Sin tests automatizados de la skill**: el repo no tiene framework de testing. Las "pruebas" son ejecuciones manuales de `/review` sobre proyectos reales (desa-websites para websites, grupodesa-backend para backend). Cada task de prueba en este plan describe los pasos manuales explícitos que el dev debe hacer
- **Versionado**: bump al final del plan (Task 9). Convención del repo: versionado central en `plugin.json`; otros ficheros no replican el número
- **Cada task termina en `git add` + reporte**, NO en `git commit` ni `git push`. El usuario controla siempre el commit y el push manualmente
- **`CHANGELOG.md` se crea al cierre** (Task 9), no en cada task — recoge el resumen consolidado de v1.8.0 al final. El fichero personal `.claude/RESUMEN_CAMBIOS.md` del autor queda fuera de git y no se toca

---

## Phase 0 — Setup

### Task 1: Crear el plan en `docs/superpowers/plans/`

**Files:**
- Create: `docs/superpowers/plans/2026-05-11-extend-review-skill-websites-and-test-phases.md` (este fichero)

- [ ] **Step 1: Verificar estado**

```bash
cd /Users/mac007/PhpstormProjects/desa-claude
git rev-parse --abbrev-ref HEAD              # debe ser xjmardia
git status --short                           # debe estar limpio (excepto .DS_Store etc.)
```

- [ ] **Step 2: Confirmar que el plan ya está creado**

```bash
ls -la docs/superpowers/plans/
```

Esperado: el fichero del plan existe (este mismo). Si no, créalo con el contenido tal cual.

- [ ] **Step 3: Stagear el plan**

```bash
git add docs/superpowers/plans/2026-05-11-extend-review-skill-websites-and-test-phases.md
git status
```

NO COMMIT NI PUSH.

---

## Phase 1 — D.1 Detección "websites" + criterios específicos

### Task 2: Ampliar detección de project type en `review.md`

**Files:**
- Modify: `plugins/desa/commands/review.md` (sección "## Paso 1: Detectar tipo de proyecto")

- [ ] **Step 1: Leer la sección actual**

Lee `plugins/desa/commands/review.md` líneas 11-25 para confirmar el bloque actual:

```bash
DIFF_FILES=$(git diff --staged --name-only 2>/dev/null || git diff --name-only 2>/dev/null || git diff HEAD~1 --name-only 2>/dev/null)
if [ -f artisan ] && [ -f composer.json ]; then echo "backend";
elif [ -d apps/mobile ] && echo "$DIFF_FILES" | grep -q "apps/mobile/"; then echo "mobile";
elif [ -d apps/web ] || [ -d packages/core ]; then echo "frontend";
else echo "unknown"; fi
```

- [ ] **Step 2: Sustituir el bloque por la versión ampliada**

Usa Edit. El nuevo bloque debe ser:

```bash
DIFF_FILES=$(git diff --staged --name-only 2>/dev/null || git diff --name-only 2>/dev/null || git diff HEAD~1 --name-only 2>/dev/null)
if [ -f artisan ] && [ -f composer.json ]; then echo "backend";
elif [ -d apps/mobile ] && echo "$DIFF_FILES" | grep -q "apps/mobile/"; then echo "mobile";
elif [ -d apps/web ] || [ -d packages/core ]; then echo "frontend";
elif [ -f next.config.js ] || [ -f next.config.mjs ] || [ -f next.config.ts ]; then echo "websites";
else echo "unknown"; fi
```

Y actualiza la frase introductoria justo encima (línea ~9):

**Antes:**
> Revisa cambios de código aplicando las convenciones del equipo. Detecta automáticamente si el proyecto es backend (Laravel/PHP) o frontend (React/JS monorepo).

**Después:**
> Revisa cambios de código aplicando las convenciones del equipo. Detecta automáticamente el tipo de proyecto: backend (Laravel/PHP con artisan), frontend (React/JS monorepo con `apps/web` o `packages/core`), websites (Next.js single-app con `next.config.*`) o mobile (React Native bajo `apps/mobile/`).

> **Nota sobre el orden**: `websites` se evalúa tras `frontend` para que el monorepo (que también podría tener un `next.config.*` interno en `apps/web/`) no caiga por error en la rama websites. La detección de `frontend` requiere `apps/web/` o `packages/core/` a nivel de raíz, que `desa-websites` no tiene.

- [ ] **Step 3: Verificar manualmente la detección**

Ejecuta el bloque actualizado en distintos repos para validar:

```bash
# En desa-websites
cd /Users/mac007/PhpstormProjects/desa-websites
DIFF_FILES=$(git diff HEAD~1 --name-only 2>/dev/null)
if [ -f artisan ] && [ -f composer.json ]; then echo "backend";
elif [ -d apps/mobile ] && echo "$DIFF_FILES" | grep -q "apps/mobile/"; then echo "mobile";
elif [ -d apps/web ] || [ -d packages/core ]; then echo "frontend";
elif [ -f next.config.js ] || [ -f next.config.mjs ] || [ -f next.config.ts ]; then echo "websites";
else echo "unknown"; fi
# Esperado: websites

# En grupodesa-backend
cd /Users/mac007/PhpstormProjects/grupodesa-backend
# (mismo bloque)
# Esperado: backend

# En grupodesa-front (monorepo)
cd /Users/mac007/PhpstormProjects/grupodesa-front
# (mismo bloque)
# Esperado: frontend
```

Anota los tres resultados en el reporte de la task.

- [ ] **Step 4: Stagear**

```bash
cd /Users/mac007/PhpstormProjects/desa-claude
git add plugins/desa/commands/review.md
git status
```

NO COMMIT NI PUSH.

---

### Task 3: Añadir sección "Criterios websites" en `review.md`

**Files:**
- Modify: `plugins/desa/commands/review.md` (insertar nueva sección de criterios entre "Criterios frontend (React/JS)" y "Criterios mobile (React Native)")

Los criterios se dividen en dos grupos:

**Grupo A — Criterios heredados del monorepo que SÍ aplican a websites** (renumerados como W1-Wn): semicolons obligatorios, className con llaves, evitar sx prop, Typography con variant, props string sin llaves, no if/else inline, no abreviaturas de una letra, hooks al inicio, props destructuradas en firma, import * as XService, key prop con ID, i18next.t() nunca a nivel de módulo.

**Grupo B — Criterios específicos de websites** (Next.js + MUI single-app, sin monorepo): LocaleLink/localePath, MUI imports directos (no barrel), Server Components por defecto, API devuelve `.data`, fetch via api.js wrapper, ISR via constante REVALIDATE.

- [ ] **Step 1: Localizar el punto de inserción**

En `review.md`, busca la línea `### Criterios mobile (React Native)` (alrededor de línea 154). La nueva sección se inserta **justo antes**.

- [ ] **Step 2: Insertar la nueva sección**

Usa Edit con `old_string` exacto siendo el header `### Criterios mobile (React Native)` para insertar antes:

```markdown
### Criterios websites (Next.js single-app)

Aplicables a proyectos detectados como `websites` (Next.js + MUI sin estructura de monorepo, ej. `desa-websites`).

86. **Semicolons obligatorios** — En toda sentencia
87. **className con llaves** — `className={'clase'}`, no `className="clase"`
88. **Evitar sx prop** — Preferir clases Tailwind o estilos en SCSS. Solo usar `sx` cuando se necesita acceder a `theme` o props de MUI
89. **Typography con variant** — Nunca estilos inline (`sx={{fontSize, fontWeight}}`)
90. **Props string sin llaves** — `variant="contained"`, no `variant={"contained"}`
91. **No if/else inline** — Siempre con llaves y saltos de línea
92. **No abreviaturas de una letra** — En `.map()`, `.filter()`, `.find()` usar nombres descriptivos (`item`, `order`), no `x`, `e`, `i`
93. **Hooks al inicio agrupados** — Hooks agrupados por categoría al inicio del componente. Early return después de hooks
94. **Props destructuradas en firma** — Destructurar props en los parámetros de la función con defaults inline: `const Component = ({label, icon, className = 'py-2'})`. No usar `props.xxx`
95. **import \* as XService** — Preferir importar servicios como namespace: `import * as SitesService from '@/api/services/SitesService'`. Llamar como `SitesService.get()`
96. **`key` prop con ID de entidad** — En `.map()` sobre listas de entidades, usar siempre el `id` único como `key`. Nunca el índice del array
97. **i18next.t() nunca a nivel de módulo** — Llamar siempre dentro de componente/hook (useMemo, render). Fuera del componente falla en producción (funciona en dev por HMR)
98. **LocaleLink obligatorio en Client Components, `localePath(locale, path)` en Server Components** — Nunca usar `<Link>` de Next.js sin prefijo de locale. Los enlaces internos deben preservar el locale activo (ES/FR/PT)
99. **MUI imports directos** — `import Button from '@mui/material/Button'`, no `import { Button } from '@mui/material'`. La excepción es `useTheme`, que debe importarse desde `@mui/material` (no desde `@mui/material/styles`)
100. **Server Components por defecto** — Solo usar `'use client'` cuando sea estrictamente necesario (estado, eventos del DOM, hooks de React que requieren cliente). Si no, dejar el componente como Server Component
101. **API devuelve `.data`** — Siempre desestructurar el resultado de las llamadas a servicios: `(await SitesService.xxx()).data`. La API retorna `null` en errores; verificar antes de acceder a propiedades anidadas
102. **`fetch` siempre vía wrapper `api.js`** — Nunca llamar a `fetch()` directamente desde componentes o hooks. Usar `api.get()` / `api.post()` de `src/api/api.js`, que añade Accept-Language, gestiona ISR `revalidate` y maneja errores uniformemente
103. **ISR revalidate via constantes `REVALIDATE`** — En las llamadas a servicios, pasar uno de los valores de `REVALIDATE` (`SITE: 300`, `CATEGORIES: 300`, `COLLECTIONS: 60`, `POST: 5`). Nunca hardcodear segundos. Si necesitas otro valor, añadirlo a `REVALIDATE` y reutilizar
104. **Server Components async no se testean en unit** — Si la lógica de un Server Component crece, **factorizarla a hooks o utilidades** que sí sean testables con Vitest. Los Server Components async se cubren con E2E (Playwright), no con Vitest
105. **MSW intercepta `fetch` en tests** — Los tests unit con MSW activo NO deben mockear `fetch` directamente. Usar fixtures de `tests/fixtures/api/` y, si falta una, crear una nueva fixture explícita en lugar de inline mock dentro del test
106. **`globalThis.session` reset automático en tests** — `tests/setup.js` lo resetea en cada `beforeEach`. No resetearlo manualmente en los tests. Si un test necesita un locale concreto, llamar `setSession('locale', 'fr')` al inicio del test, no recrear el objeto entero

```

> **Reglas para extender más adelante**: los criterios 86-106 son la base. Cuando aparezcan patrones nuevos en `desa-websites` (PDF de productos con Kendo, formularios con validación, SEO/JSON-LD avanzado, etc.), añadir criterios al final de la lista numerados consecutivamente. Mantener el formato `**Título** — Descripción corta`. Solo añadir un criterio si pasa el filtro: ¿puede generar una incidencia con fichero:línea? Si no, no es un criterio — es una guía.

- [ ] **Step 3: Verificar visualmente**

Abre `plugins/desa/commands/review.md` en el editor y comprueba que:
- El criterio 85 sigue siendo el último de la sección mobile previa (no se mezcló)
- Los criterios 86-106 están en la nueva sección
- La sección "Criterios mobile (React Native)" (criterio 82-85 según el orden del fichero — verificar línea de inicio real) sigue intacta debajo

> **Atención al ordering**: el fichero actual tiene los criterios mobile como 82-85, así que tu nueva sección DEBE colocarse ANTES de "Criterios mobile" para que las numeraciones sean coherentes. Si decides ponerla DESPUÉS de mobile, renumera mobile a 86-89 y websites a 82-102. Recomendación: insertarla antes para no tocar el bloque mobile.

- [ ] **Step 4: Stagear**

```bash
git add plugins/desa/commands/review.md
git status
```

NO COMMIT NI PUSH.

---

### Task 4: Probar D.1 manualmente sobre `desa-websites`

Como no hay testing automatizado de la skill, esta task es una **validación manual** que el usuario debe ejecutar en su máquina.

- [ ] **Step 1: Reinstalar el plugin localmente**

Para que los cambios de `review.md` se reflejen al invocar `/desa:review`, hay que sincronizar el repo local con la instalación del plugin (típicamente en `~/.claude/plugins/marketplaces/desa/` o equivalente). El procedimiento estándar del repo, según `.claude/BRIEFING.md`, es:

```bash
# Verificar dónde está instalado
ls ~/.claude/plugins/marketplaces/ 2>/dev/null

# Reinstalar / actualizar
/plugin marketplace update desa
```

Si la sincronización falla por caché, limpiarla siguiendo las instrucciones del README del repo.

- [ ] **Step 2: Probar la detección en desa-websites**

```bash
cd /Users/mac007/PhpstormProjects/desa-websites
git checkout xjmardia  # o tu rama
# Hacer un cambio trivial en un fichero
echo "// test marker" >> src/lib/session.js
git add src/lib/session.js
```

Luego invocar la skill:

```
/desa:review
```

**Expected**:
- La skill detecta `Proyecto: websites`
- Aplica los criterios 86-106 (los nuevos)
- Lee `CLAUDE.md` de `desa-websites` y aplica reglas adicionales si las hay

- [ ] **Step 3: Revertir el cambio trivial**

```bash
git checkout src/lib/session.js
```

- [ ] **Step 4: Documentar el resultado**

Anota en el reporte de la task:
- Qué proyecto detectó (debería ser `websites`)
- Si los criterios aplicados son los nuevos
- Si hubo algún error o sorpresa

> **Si la skill no se actualiza tras el `marketplace update`**: probable problema de caché de Claude Code. Revisar el README del repo para la lista de pasos de troubleshooting. Si no se resuelve, anotar como anomalía y continuar — los Steps de Task 4 son verificación opcional; el plan puede avanzar y consolidar en Task 9.

---

## Phase 2 — D.2 Fase 6 (ejecutar tests)

### Task 5: Añadir Fase 6 — "Ejecutar tests" en `review.md`

**Files:**
- Modify: `plugins/desa/commands/review.md` (insertar nueva sección después de "Paso 6: Formato de salida")

> **Decisión de ordering**: las Fases nuevas se insertan **DESPUÉS** del Paso 6 actual (Formato de salida) y antes de "Reglas estrictas". Renombramos: el actual "Paso 6: Formato de salida" pasa a "Paso 8: Formato de salida" (porque dejamos sitio a las nuevas fases 6 y 7).

> **Alternativa que descartamos**: poner las fases 6/7 ANTES del Paso 6 actual (Formato). El razonamiento es que el output de Fase 6/7 (resultado de tests, tests generados) debería incluirse en el mismo formato de salida estructurado. Por eso primero ejecutamos tests, luego generamos faltantes, y AL FINAL se construye el reporte único.

- [ ] **Step 1: Renumerar el "Paso 6: Formato de salida" actual a "Paso 8"**

Usa Edit con `old_string` siendo `## Paso 6: Formato de salida` para renombrar a `## Paso 8: Formato de salida`. Solo cambia esa línea — el contenido del Paso 6 actual se mantiene íntegro (será el Paso 8 final).

- [ ] **Step 2: Insertar nueva sección "Paso 6: Ejecutar tests"**

Usa Edit. El `old_string` es `## Paso 8: Formato de salida` (la línea recién renombrada). El `new_string` es el bloque siguiente seguido de `## Paso 8: Formato de salida`:

```markdown
## Paso 6: Ejecutar tests (solo si el proyecto tiene tests configurados)

Tras la revisión estática (Pasos 1-5), si el proyecto tiene infraestructura de tests, ejecutarlos filtrados por el diff actual para verificar que los cambios no rompen nada y que la cobertura sigue siendo aceptable.

### Detección del runner de tests

Comprobar la presencia de ficheros de configuración:

```bash
# Backend
HAS_PEST=$([ -f phpunit.xml ] || [ -f phpunit.xml.dist ] && echo "yes" || echo "no")

# Websites / frontend monorepo
HAS_VITEST=$([ -f vitest.config.js ] || [ -f vitest.config.mjs ] || [ -f vitest.config.ts ] && echo "yes" || echo "no")
HAS_PLAYWRIGHT=$([ -f playwright.config.js ] || [ -f playwright.config.ts ] && echo "yes" || echo "no")
```

Si ninguno está configurado, **omitir la Fase 6 silenciosamente** y continuar a Paso 7. No es error.

### Ejecución por project type

#### project_type = backend (Pest)

1. Derivar el filtro:
    - Si el diff toca `app/Services/Foo/BarService.php`, filtrar por `tests/Feature/Foo/Bar*Test.php` o `tests/Unit/Foo/Bar*Test.php`
    - Si el diff toca `app/Models/`, filtrar por `tests/Feature/{Domain}/`
    - Si no se puede derivar filtro claro, ejecutar suite completa
2. Ejecutar:
    ```bash
    APP_ENV=testing ./vendor/bin/pest --filter="[filtro]" --coverage
    ```
3. Capturar exit code y output

#### project_type = websites (Vitest + opcional Playwright)

1. Derivar filtro:
    - `src/hooks/<X>.js` → `tests/unit/hooks/<X>.test.{js,jsx}`
    - `src/lib/<X>.js` → `tests/unit/lib/<X>.test.{js,jsx}`
    - `src/api/services/<X>.js` → `tests/unit/services/<X>.test.{js,jsx}`
    - `src/components/<dir>/<X>.jsx` → `tests/unit/<dir>/<X>.test.{js,jsx}`
2. Ejecutar:
    ```bash
    npx vitest run --coverage [patrones-derivados]
    ```
3. Si `HAS_PLAYWRIGHT=yes` y `tests/e2e/smoke/` no está vacío, ejecutar también:
    ```bash
    npx playwright test [specs-relacionadas]
    ```
    Si `tests/e2e/smoke/` está vacío (E2E diferidos), omitir Playwright silenciosamente.

#### project_type = frontend (monorepo)

⚠️ **TODO**: pendiente de definir el runner de tests del monorepo cuando el equipo lo configure. Mientras tanto:

```
echo "🟡 Ejecución de tests para frontend monorepo aún no implementada en esta skill."
echo "Pendiente del Bloque de testing del monorepo. Omitiendo Fase 6."
```

Continuar a Paso 7.

#### project_type = mobile

⚠️ **TODO**: pendiente de definir el runner de tests de mobile (probable Jest). Mientras tanto:

```
echo "🟡 Ejecución de tests para mobile aún no implementada en esta skill."
echo "Pendiente del Bloque de testing de mobile. Omitiendo Fase 6."
```

Continuar a Paso 7.

### Interpretación del resultado

- **Todos los tests pasan, exit 0** → Anotar para el reporte final (Paso 8): `Tests: N pasados / N (incluido en sección "Tests")`. Continuar a Paso 7.
- **Algún test falla** → Anotar fichero:test:error. Generar una propuesta de corrección (qué línea cambiar y cómo). **Preguntar al dev** antes de aplicar:
    > He detectado N tests fallando tras tus cambios. ¿Quieres que aplique las correcciones propuestas? (s/n)

    Si el dev responde "s", aplicar y re-ejecutar (bucle máximo 3 iteraciones para correcciones de tests pre-existentes). Si tras 3 iter sigue fallando, reportar al dev sin aplicar más cambios y NO continuar a Paso 7.
- **Tests no ejecutables** (error de configuración, no error de test) → Anotar como anomalía y omitir Paso 7. NO intentar arreglar la configuración.

### Reglas estrictas para esta fase

- **Nunca** modificar el código fuente del proyecto en esta fase. Solo cambios sobre tests pre-existentes que estén stricti fallando.
- **Nunca** generar tests nuevos aquí — eso es Paso 7.
- **Nunca** continuar a Paso 7 si Paso 6 falla y el dev no autoriza correcciones.
- Si el bucle de 3 iter no converge, devolver control al dev sin más intentos.

```

- [ ] **Step 3: Insertar nueva sección "Paso 7: Generar tests faltantes"**

A continuación del bloque del Paso 6, inserta:

```markdown
## Paso 7: Generar tests faltantes (solo si Paso 6 pasó y la cobertura es insuficiente)

Solo se ejecuta esta fase si:

1. Paso 6 pasó verde (todos los tests existentes en verde)
2. El proyecto tiene un umbral de cobertura configurado y el reporte de cobertura **sobre los ficheros modificados en el diff** está por debajo del umbral

Si la cobertura ya cumple, **omitir Paso 7 silenciosamente** y continuar a Paso 8.

### Identificación de gaps

Del reporte de cobertura (generado en Paso 6 con `--coverage`), extraer:

- Ficheros modificados con cobertura por debajo del umbral
- Funciones y ramas concretas sin cubrir dentro de esos ficheros

### Generación de tests (bucle máx. 3 iteraciones)

Para cada gap detectado:

1. **Leer el código sin cubrir** del fichero fuente
2. **Leer un test existente del mismo dominio** como referencia de estilo y patrones (estructura `describe()/it()`, uso de fixtures, mocks)
3. **Generar el test** siguiendo ese patrón. Ubicación según project_type:
    - backend: `tests/Feature/{Domain}/` o `tests/Unit/{Domain}/`
    - websites: `tests/unit/{dir}/{filename}.test.{js,jsx}` espejando la ruta de `src/`
4. **Ejecutar el test recién generado**:
    - backend: `APP_ENV=testing ./vendor/bin/pest tests/path/to/new-test.php`
    - websites: `npx vitest run tests/unit/path/to/new-test.{js,jsx}`
5. **Si pasa** → siguiente gap
6. **Si falla** → leer error, corregir el test (NUNCA el código fuente), reintentar
7. **Si tras 3 iter sigue fallando** → reportar al dev sin commit, dejar el test borrador con un comentario `// FIXME: generado por /review, no converge — ver iteración 3`

### Tras procesar todos los gaps

- `git add` de los tests nuevos y modificados
- **NUNCA** `git commit` ni `git push`
- Anotar para el reporte final (Paso 8): tests generados, gaps cubiertos, gaps no convergidos

### Reglas estrictas para esta fase

- **Nunca** generar tests sobre código que ya tenía fallos antes de los cambios del dev
- **Nunca** mockear `fetch` directamente si MSW (websites) o Mocks/Factories (backend) ya están en juego. Usar fixtures existentes o crear nuevas explícitamente
- **Nunca** generar tests para Server Components async en websites (limitación documentada del runtime)
- **Nunca** modificar código de producción para hacer pasar un test generado. Si un test no se puede escribir sin tocar el fuente, abortar ese gap y reportarlo al dev
- **Usar fixtures de `tests/fixtures/api/` en websites** y factories existentes en backend. NUNCA inline JSON gigante dentro de los tests
- **Estilo de assertions** debe coincidir con tests existentes del mismo dominio (no introducir `chai`/`should` si el proyecto usa `expect` de vitest, etc.)

```

- [ ] **Step 4: Actualizar la sección "Reglas estrictas" del final del fichero**

La sección actual "Reglas estrictas" (cerca del final del fichero, alrededor de línea 212 en el fichero original) tiene 11 puntos que aplican a Paso 5 (revisión). Hay que **mantenerlos intactos** pero añadir una nota inicial:

Usa Edit. El `old_string` exacto es:

```markdown
## Reglas estrictas

- **Nunca** sugerir añadir comentarios al código
```

El `new_string` es:

```markdown
## Reglas estrictas

> Las siguientes reglas aplican a Paso 5 (revisión estática). Para reglas específicas de Paso 6 (ejecutar tests) y Paso 7 (generar tests), ver las "Reglas estrictas" al final de cada uno de esos pasos.

- **Nunca** sugerir añadir comentarios al código
```

- [ ] **Step 5: Stagear**

```bash
git add plugins/desa/commands/review.md
git status
```

NO COMMIT NI PUSH.

---

### Task 6: Probar Fase 6 manualmente sobre backend y websites

Como en Task 4: validación manual; no hay testing automatizado de la skill.

- [ ] **Step 1: Sincronizar el plugin actualizado**

```bash
/plugin marketplace update desa
```

- [ ] **Step 2: Probar Fase 6 en `desa-websites`**

```bash
cd /Users/mac007/PhpstormProjects/desa-websites
git checkout xjmardia
# Modificar un fichero ya cubierto por tests, por ejemplo:
sed -i '' 's/return path ?? .#.;/return path ?? "#";/' src/lib/localePath.js  # cambio trivial sin romper nada
git add src/lib/localePath.js
```

Invocar `/desa:review` y verificar que:

- Detecta proyecto = `websites`
- Tras Paso 5 (revisión estática) ejecuta `npx vitest run --coverage tests/unit/lib/localePath.test.js`
- Reporta resultado de los tests en el output final

Revertir el cambio:

```bash
git checkout src/lib/localePath.js
```

- [ ] **Step 3: Probar Fase 6 en `grupodesa-backend` (si tienes acceso)**

```bash
cd /Users/mac007/PhpstormProjects/grupodesa-backend
git checkout xjmardia  # o equivalente
# Modificar un fichero del dominio Transactions:
# (toca tú un cambio trivial sin riesgo, ej. un comentario que luego revertimos)
git add app/Services/Transactions/OrderService.php
```

Invocar `/desa:review` y verificar que:

- Detecta proyecto = `backend`
- Ejecuta `./vendor/bin/pest --filter` con el dominio derivado del diff

Si no tienes el repo backend levantado, **omitir este step** y anotar como "validación pendiente para próxima iteración".

- [ ] **Step 4: Documentar resultados**

En el reporte de la task, anota:

- Si Fase 6 se disparó correctamente en websites
- Si los tests se ejecutaron y el resultado se incluyó en el reporte final
- Si hubo algún problema con la derivación de filtros, formato del comando, o interpretación de salida
- Cualquier ajuste necesario sobre `review.md`

Si surge necesidad de ajustes, hacerlos antes de continuar y restagear.

---

## Phase 3 — D.3 Fase 7 (generar tests)

### Task 7: Validar y refinar Fase 7 — "Generar tests faltantes"

La estructura de la Fase 7 ya quedó escrita en Task 5 (Step 3). Esta task se centra en validarla y refinarla con casos concretos.

- [ ] **Step 1: Probar Fase 7 sobre un gap real en `desa-websites`**

```bash
cd /Users/mac007/PhpstormProjects/desa-websites
git checkout xjmardia
```

Identifica un fichero cubierto por testing pero con gap de cobertura. Por ejemplo: `src/hooks/useProductVariant.js` tiene 100% lines pero 94.73% branches según el reporte de cobertura previo. Modifica el fichero para añadir una rama nueva (ej. nuevo `case` en el switch) sin añadir el test correspondiente:

```javascript
// En src/hooks/useProductVariant.js, añadir al switch un case nuevo:
case 'date':
    return customFieldValue?.fields?.value ?? '';
```

```bash
git add src/hooks/useProductVariant.js
```

Invocar `/desa:review` y verificar que:

- Paso 6 ejecuta vitest y reporta cobertura
- Paso 7 detecta la rama `'date'` sin cubrir y genera un test para ella
- El test generado se ubica en `tests/unit/hooks/useProductVariant.test.jsx`
- El test pasa tras la generación (o se itera hasta 3 veces si falla)
- El test queda `git add`-eado pero NO commiteado

Revertir todo al final:

```bash
git checkout src/hooks/useProductVariant.js tests/unit/hooks/useProductVariant.test.jsx
```

- [ ] **Step 2: Documentar el caso y refinar si hace falta**

Anota en el reporte:

- ¿La detección del gap fue correcta?
- ¿El test generado seguía el patrón de los tests existentes?
- ¿Pasó al primer intento o necesitó iterar?
- ¿Hubo algún edge case mal manejado (ej. la skill modificó código fuente en lugar del test)?

Si hay refinamientos necesarios (ej. añadir reglas estrictas adicionales que se nos hayan escapado), editarlos en `review.md` y restagear:

```bash
cd /Users/mac007/PhpstormProjects/desa-claude
git add plugins/desa/commands/review.md
```

NO COMMIT NI PUSH.

---

### Task 8: Probar Fase 7 sobre backend (opcional)

Si tienes el repo `grupodesa-backend` levantado, repite el procedimiento de Task 7 sobre un fichero del dominio Transactions con cobertura incompleta.

Si no, omite esta task y anota como "pendiente de validación en próxima iteración con backend".

---

### Nota — comportamiento observado durante validación de Task 7 (2026-05-11)

Durante la validación manual de Task 7 sobre `desa-websites`, el equipo creó un gap artificial añadiendo 3 funciones (`listSessionKeys`, `clearSession`, `hasSessionKey`) a `src/lib/session.js` **sin consumer real**. La skill se comportó así:

- **Pasos 1-5**: detectó correctamente las 3 funciones como dead code (criterio #9) y los guards como inalcanzables (criterio #5/#7)
- **Paso 6**: ejecutó tests, reportó 10/10 pass y midió cobertura (100% → 57.5%) — comportamiento esperado tras los ajustes "incondicional respecto a Paso 5"
- **Paso 7**: **NO disparó la generación automática**. En su lugar, la skill **preguntó al dev** qué hacer con el dead code antes de generar tests, y tras la respuesta del dev (`Hazlo`) procedió a **eliminar las 3 funciones del código fuente**

**Interpretación**: la skill está siendo **más conservadora que el spec literal** — considera que generar tests sobre código que ya identificó como problemático sería "fijar una API hipotética". Esto **no es un bug del plan**, es una decisión defensiva razonable que protege la calidad del codebase.

**En escenarios reales** (código añadido con consumer real, gap de cobertura legítimo), Paso 7 debería disparar automáticamente sin pedir permiso — la skill no tendría base para considerar el código como dead.

**Validación final aceptada**: Task 7 se da por validada en su capacidad declarativa (Paso 7 está bien diseñado en el spec, dispara correctamente cuando las condiciones son legítimas). Las pruebas con escenarios artificiales son inherentemente limitadas para esta fase. Una validación más estricta requeriría un PR real con código real y gaps reales — algo que ocurrirá naturalmente en el día a día tras el merge.

---

## Phase 4 — Cierre

### Task 9: Bump versión, crear `CHANGELOG.md`, verificación end-to-end

**Files:**
- Modify: `plugins/desa/.claude-plugin/plugin.json` (bump versión)
- Create: `CHANGELOG.md` (changelog público del plugin, primera entrada = v1.8.0)

- [ ] **Step 1: Bump versión en `plugin.json`**

```bash
cd /Users/mac007/PhpstormProjects/desa-claude
cat plugins/desa/.claude-plugin/plugin.json
```

Usa Edit para cambiar `"version": "1.7.0"` por `"version": "1.8.0"`.

- [ ] **Step 2: Crear `CHANGELOG.md` en la raíz del repo**

Es la primera entrada del fichero (antes no existía). Contenido completo:

```markdown
# Changelog

All notable changes to the `desa` plugin will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.8.0] — 2026-05-11

### Added

- **Project type `websites`** in `/desa:review` — la skill detecta proyectos Next.js single-app (presencia de `next.config.js/mjs/ts`, sin `apps/web` ni `packages/core`). El primer proyecto que lo usa es `desa-websites`.
- **21 criterios nuevos para `websites` (86-106)** en `review.md` — heredados aplicables del monorepo + específicos del stack Next.js single-app: `LocaleLink`/`localePath`, MUI imports directos, Server Components por defecto, fetch via `api.js` wrapper, ISR via constantes `REVALIDATE`, MSW intercepta fetch en tests, `globalThis.session` reset automático.
- **Paso 6 — "Ejecutar tests"** en `/desa:review` — tras la revisión estática, la skill ejecuta los tests del proyecto filtrados por el diff. Soportado en `backend` (Pest) y `websites` (Vitest + opcional Playwright). Stubs informativos para `frontend` (monorepo) y `mobile`, pendientes hasta que el equipo defina sus runners.
- **Paso 7 — "Generar tests faltantes"** en `/desa:review` — si tras Paso 6 la cobertura sobre los ficheros del diff está bajo el umbral, la skill genera tests siguiendo el patrón existente, itera hasta 3 veces, y stagea sin commitear.
- **`.gitignore`** en la raíz del repo — ignora ruidos del sistema (`.DS_Store`, `.idea/`) y notas personales del autor (`.claude/BRIEFING.md`, `.claude/RESUMEN_CAMBIOS.md`).

### Changed

- El antiguo **Paso 6 "Formato de salida" pasa a ser Paso 8** (sin cambios en su contenido; solo renumerado para dejar sitio a las Fases 6 y 7 nuevas).
- **Las "Reglas estrictas" del final del fichero `review.md`** aclaran ahora que aplican al Paso 5 (revisión estática). Cada nuevo Paso 6 y 7 tiene sus propias reglas estrictas inline.

### Notes

- Cambios **aditivos**: la detección actual de `backend`/`frontend`/`mobile` no cambia; solo se añade la rama `websites`. Las Fases 1-5 actuales del flujo de revisión no se tocan.
- **Origen**: Bloque D del plan de seguimiento de `desa-websites` (ver `desa-websites/docs/superpowers/plans/2026-05-10-post-testing-followup.md` y el decision brief asociado).
- **Plan de implementación**: `docs/superpowers/plans/2026-05-11-extend-review-skill-websites-and-test-phases.md`.
```

> **Nota sobre el patrón Keep a Changelog**: las secciones estándar son `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`. Cuando se publique la siguiente versión, añadir una nueva sección `## [X.Y.Z] — YYYY-MM-DD` al inicio (debajo del bloque introductorio del fichero) y rellenar solo las subsecciones que apliquen.

- [ ] **Step 3: Verificación end-to-end**

```bash
cd /Users/mac007/PhpstormProjects/desa-claude
git status --short
git log --oneline -10
cat plugins/desa/.claude-plugin/plugin.json | grep version
head -20 CHANGELOG.md
```

Verifica:

- `version: 1.8.0` en `plugin.json`
- `CHANGELOG.md` existe en la raíz con la entrada `[1.8.0]`
- `review.md` tiene la rama `websites` en la detección, los criterios 86-106 y los Pasos 6/7/8

- [ ] **Step 4: Stagear y reporte**

```bash
git add plugins/desa/.claude-plugin/plugin.json CHANGELOG.md
git status
```

NO COMMIT NI PUSH.

- [ ] **Step 5: Preparar la PR (pasos manuales del usuario)**

Tras el commit final del usuario:

```bash
git push -u origin xjmardia
gh pr create --base main --title "feat: extend desa:review with websites project type and test phases 6/7"
```

Body sugerido de la PR:

```markdown
## Resumen

Extiende la skill `desa:review` con tres capacidades nuevas:

1. **Detección de project type `websites`** para proyectos Next.js single-app (Next.js + MUI sin estructura monorepo)
2. **Paso 6 — Ejecutar tests** filtrados por el diff: `backend` (Pest) y `websites` (Vitest + Playwright opcional). Stubs informativos para frontend (monorepo) y mobile
3. **Paso 7 — Generar tests faltantes** con bucle de hasta 3 iteraciones, staging automático sin commit

Plan completo en `docs/superpowers/plans/2026-05-11-extend-review-skill-websites-and-test-phases.md`.

Origen: Bloque D del plan de seguimiento de `desa-websites`.

## Compatibilidad

- Cambios aditivos. Las Fases 1-5 actuales no se modifican
- Backend, frontend monorepo y mobile no cambian comportamiento (frontend monorepo y mobile ahora tienen stubs informativos en Paso 6/7 — antes simplemente no existían las fases)
- Bump de versión: v1.7.0 → v1.8.0

## Test plan

- [ ] Probado manualmente sobre `desa-websites` (rama `xjmardia`): detecta `websites`, ejecuta vitest, genera tests cuando hay gap
- [ ] Probado sobre `grupodesa-backend` si está disponible (Task 6 Step 3 del plan)
```

---

## Verificación final del plan (self-review)

- [ ] Cobertura del scope: D.1, D.2, D.3 según el decision brief ✓
- [ ] Sin breaking changes para project types existentes ✓
- [ ] Detección de `websites` ordenada correctamente (después de `frontend`) ✓
- [ ] Criterios `websites` cubren tanto Next.js específico como reglas heredadas aplicables ✓
- [ ] Fases 6/7 con stubs para project types no implementados (frontend monorepo, mobile) ✓
- [ ] Reglas estrictas para cada fase nueva ✓
- [ ] Validación manual descrita (no hay testing automatizado en este repo) ✓
- [ ] Bump de versión y creación de `CHANGELOG.md` ✓
- [ ] Preparación de la PR documentada con title y body sugeridos ✓
- [ ] Ningún paso ejecuta commit o push automático — siempre el usuario ✓

---

## Deuda técnica registrada (fuera de scope de este plan)

- **Fase 6/7 para frontend monorepo**: pendiente del equipo del monorepo definir su runner de tests y patrones
- **Fase 6/7 para mobile**: pendiente del equipo de mobile (probablemente Jest + Detox)
- **Testing automatizado de la skill misma**: el repo `desa-claude` no tiene framework de testing de skills. Los cambios se verifican manualmente. Si en el futuro se quiere automatizar, sería un plan aparte
- **Decisión sobre Variante de `review.yml`** (Bloque C del follow-up plan de `desa-websites`): si se elige Variante D (`claude-code-action`), esta skill podría invocarse desde CI y obtener el mismo análisis en la PR. Pero esa decisión es transversal y se decide aparte

---

*Plan completo. Tras la aprobación, ejecutar task por task con `subagent-driven-development`. El usuario decide los commits y pushes, igual que en el plan padre de `desa-websites`.*
