---
description: Revisar código aplicando los estándares del equipo antes de commit o PR
argument-hint: [ruta de archivo, número de PR (#42), vacío para cambios locales, --verbose]
allowed-tools: Bash(git:*), Bash(gh:*), Read, Grep, Glob
---

# Review — Revisión de código con estándares Grupo Desa

Revisa cambios de código aplicando las convenciones del equipo. Detecta automáticamente el tipo de proyecto: backend (Laravel/PHP con artisan), frontend (React/JS monorepo con `apps/web` o `packages/core`), websites (Next.js single-app con `next.config.*`) o mobile (React Native bajo `apps/mobile/`).

## Paso 1: Detectar tipo de proyecto

Desde el directorio de trabajo actual:

```bash
DIFF_FILES=$(git diff --staged --name-only 2>/dev/null || git diff --name-only 2>/dev/null || git diff HEAD~1 --name-only 2>/dev/null)
if [ -f artisan ] && [ -f composer.json ]; then echo "backend";
elif [ -d apps/mobile ] && echo "$DIFF_FILES" | grep -q "apps/mobile/"; then echo "mobile";
elif [ -d apps/web ] || [ -d packages/core ]; then echo "frontend";
elif [ -f next.config.js ] || [ -f next.config.mjs ] || [ -f next.config.ts ]; then echo "websites";
else echo "unknown"; fi
```

Si es `unknown`, informar al usuario y terminar.

Si el diff toca tanto `apps/web/` como `apps/mobile/`, aplicar criterios de ambos (frontend + mobile).

## Paso 2: Obtener los cambios a revisar

Según `$ARGUMENTS`:

- **Si empieza por `#` o es solo dígitos** (ej. `42`, `#42`): Es un PR. Obtener cambios con `gh pr diff {N}`.
- **Si es una ruta de archivo existente**: Limitar el diff a ese archivo usando `git diff --staged -- {ruta}`, con fallback a `git diff -- {ruta}` y luego `git diff HEAD~1 -- {ruta}`.
- **Si está vacío**: Buscar cambios en este orden:
  1. `git diff --staged` — cambios preparados para commit
  2. `git diff` — cambios no staged
  3. `git diff HEAD~1` — último commit

Si no hay cambios en ninguna fuente, informar al usuario y terminar.

Si hay más de 20 ficheros modificados, avisar al usuario y sugerir revisar por fichero o directorio.

Indicar al usuario qué fuente se está revisando (staged, unstaged, último commit o PR #N).

## Paso 3: Leer CLAUDE.md

Leer el fichero `CLAUDE.md` de la raíz del proyecto actual. Si contiene reglas no cubiertas por los criterios de este prompt, aplicarlas también.

Leer también el `MEMORY.md` del proyecto si existe (`~/.claude/projects/{project-path}/memory/MEMORY.md`). Si contiene trampas o convenciones adicionales, aplicarlas.

## Paso 4: Contexto de patrones existentes

Solo cuando una incidencia potencial requiera verificación contra el código existente (criterio #1), leer un fichero del mismo directorio o dominio que sirva de referencia. No leer ficheros preventivamente — solo bajo demanda para confirmar o descartar una sospecha.

**Excepción**: Si el diff toca un Service o un archivo que pasa `include` a la API, buscar proactivamente patrones `include` con punto anidado (ej. `indicator.process`) — es un error recurrente [#74].

## Paso 5: Revisar los cambios

Analizar cada fichero modificado. Para cada posible incidencia, asignar internamente un nivel de confianza (0-100). **Solo reportar incidencias con confianza >= 75.**

**Severidad**: Crítico para seguridad, corrupción de datos o bugs silenciosos (criterios #6, #13, #22, #25, #27, #30, #33, #49, #69, #74). Importante para violaciones de patrón estructural que afectan a corrección o mantenibilidad. Menor para estilo, naming y convenciones.

Si `$ARGUMENTS` contiene `--verbose` o `-v`, añadir al final del reporte una sección con las incidencias descartadas por confianza < 75 (ver formato en Paso 6).

### Criterios compartidos (ambos proyectos)

1. **Adherencia a patrones preexistentes** — El código nuevo DEBE seguir los patrones del proyecto. Si hay duda, leer un fichero de referencia del mismo dominio para comparar
2. **Escalabilidad y mantenibilidad** — Acoplamiento excesivo, lógica duplicada, abstracciones prematuras o ausentes
3. **Legibilidad** — Nombres claros, flujo comprensible, sin complejidad innecesaria
4. **Sin comentarios** — Ni explicativos ni TODOs. Código autodocumentado
5. **Causas raíz** — Detectar fixes temporales, workarounds o parches sobre código problemático
6. **Seguridad** — SQL injection, XSS, autenticación/autorización, secretos hardcodeados, inputs no validados
7. **Complejidad innecesaria** — Nesting >3 niveles sin early return, ternarios anidados (`a ? b ? c : d : e`), funciones >50 líneas que deberían dividirse
8. **Código redundante** — Bloques duplicados o lógica repetida que debería extraerse a función/componente compartido
9. **Over-engineering** — Abstracciones sin uso real, wrappers triviales, configurabilidad innecesaria, soluciones "clever" difíciles de leer (one-liners densos, destructuring excesivo)

### Criterios backend (Laravel/PHP)

10. **Estructura por dominio** — `app/Models/{Domain}/`, `app/Services/{Domain}/`, `app/Http/Resources/{Domain}/`, `app/Http/Requests/{Domain}/`
11. **Patrón CRUD completo** — Entidades nuevas deben tener Model, Request, Service y Resource. El Model extiende `Entity` (no `Model` directamente). Si tiene campo `code`, generarlo con `$this->uniqueCode()`. Si tiene `searchable_tags`, actualizarlo tras save con `formatSearchableTags()`
12. **Relaciones polimórficas** — BelongsToMany via `model_has_relations` requiere: `->where('model_has_relations.first_model_type', self::class)`, `->where('model_has_relations.second_model_type', Target::class)`, `->withPivot('properties')` y `->wherePivotNull('deleted_at')`
13. **Roles whitelist** — Siempre `hasRole('employee|customer')`, nunca `!hasRole('...')`. Nuevos roles no deben ver datos sensibles por defecto
14. **Filtrado dual** — Service controla eager loading (`Auth::hasRole`), Resource controla serialización (`$this->hasRole`). El backend calcula precios/totales para todos los roles; solo el Resource los oculta
15. **Naming** — snake_case en respuestas JSON (`cost_centers`), camelCase en relaciones PHP (`costCenters`)
16. **Sin migraciones** — No debe haber ficheros nuevos en `database/migrations/`
17. **Rutas** — Prefix una sola vez, agrupadas por dominio, middleware al nivel más alto aplicable
18. **Validación de arrays** — `'field' => 'present|array'` + `'field.*' => 'required|numeric|exists:table,id'`. Campos escalares bajo `fields.*`, relaciones como arrays de IDs en claves top-level
19. **Include pattern** — Carga condicional via `?include=` con `in_array()` en Service
20. **Resource pattern** — Estructura siempre `{ id, fields: {escalares}, relacion1: {}, relacion2: [] }`. Relaciones cargadas condicionalmente con `$this->relationLoaded()`. Todo Resource debe llamar `$this->addEntityRelations($result)` antes de retornar
21. **Excepciones con HTTP status** — `throw new Exception(Response::HTTP_CONFLICT)`. El status code es el mensaje; nunca lanzar excepciones con strings de texto libre
22. **Transacciones explícitas** — Toda escritura: `DB::beginTransaction()` al inicio del try, `DB::commit()` al final, `DB::rollBack()` + `return $this->exceptionResponse($exception)` en el catch. Sin transacción sin try-catch
23. **`event()` y `broadcast()` después de commit()** — Ambos deben ir DESPUÉS de `DB::commit()`, nunca antes ni dentro del catch. `broadcast()->toOthers()` para push WebSocket; `event()` para listeners internos
24. **GetRequest para listados** — Preferir `GetRequest` que centraliza parsing de `include`, `filter`, `sort`, `perPage`. No reinventar el parsing en controllers nuevos
25. **Auth facade** — Usar siempre `App\Models\Shared\Auth`. Detectar usos de `auth()->user()`, `Auth::user()` de `Illuminate\Support\Facades\Auth` o `request()->user()` — todos son anti-patrones en este proyecto
26. **Controller ultra-thin** — Controllers solo instancian el Service en el constructor y delegan. Flagear: acceso directo a modelos o BD, condiciones de negocio, validación manual, cualquier lógica que no sea instanciar + delegar
27. **`entityQuery()` al inicio de `query()`** — Todo método `query()` en un Service debe llamar `$query = $this->entityQuery($query, $include, $filter)` como primera operación tras crear el Builder. Si falta, los filtros e includes compartidos de `Entitable` no se aplican
28. **Audit trail en save()** — En creación (`!$entity->exists`): asignar `creator_type = get_class(Auth::user())` y `creator_id = Auth::id()`. En edición: `updater_type` y `updater_id`. Nunca hardcodear el class string — usar `get_class(Auth::user())` o `Auth::type()`
29. **Guardia de estado en save() y delete()** — Si la entidad tiene `status_id`: verificar `if ($entity->exists && !$entity->isEditable()) throw new Exception(Response::HTTP_CONFLICT)` antes de modificar; `if (!$entity->isDeletable()) throw new Exception(Response::HTTP_CONFLICT)` antes de eliminar
30. **`withTrashed()` en relaciones a soft-deletable** — Cualquier `morphTo()` o `belongsTo()` que apunte a una entidad con `SoftDeletes` debe encadenarse con `->withTrashed()`. No solo `creator`, `updater`, `deleter` — también `model()`, `orderable()`, y cualquier otra relación polimórfica a entidades eliminables
31. **Convenciones de respuesta HTTP** — GET single: `new EntityResource(...)` sin wrapper `response()`. GET paginado: `EntityResource::paginate(...)`. POST/PUT: `response(new EntityResource($entity), $entity->wasRecentlyCreated ? 201 : 200)`. DELETE: `response(null, 200)`. Operación asíncrona (job/export): `response(null, 201)`
32. **Naming de Events** — `{Entity}ChangedEvent` para crear/actualizar, `{Entity}DeletedEvent` para eliminar. Ubicación: `app/Events/{Domain}/`. Flagear nombres que no sigan la convención o que estén fuera del directorio correcto
33. **GlobalScopes — whitelist obligatoria** — Toda restricción dentro de un `addGlobalScope` que filtre por rol debe usar `hasRole('employee|customer')` (whitelist), nunca `!hasRole('...')`. Con negación, cualquier rol nuevo bypasea la restricción por defecto y accede a datos que no debería ver

### Criterios frontend (React/JS)

34. **Semicolons obligatorios** — En toda sentencia
35. **className con llaves** — `className={'clase'}`, no `className="clase"`
36. **Espaciado en items** — No `gap`/`spacing` en contenedores. Usar `mx-1`, `px-2` en hijos
37. **Evitar sx prop** — Preferir clases CSS
38. **No w-full** — Usar `width="100%"` como prop de MUI
39. **Typography con variant** — Nunca estilos inline (`sx={{fontSize, fontWeight}}`)
40. **Botones sin Typography** — Texto directo como children del Button
41. **Props string sin llaves** — `variant="contained"`, no `variant={"contained"}`
42. **No pasar valores por defecto** — Omitir parámetros que coincidan con el default de la función
43. **No if/else inline** — Siempre con llaves y saltos de línea
44. **No abreviaturas de una letra** — En `.map()`, `.filter()`, `.find()` usar nombres descriptivos (`item`, `order`), no `x`, `e`, `i`
45. **function para features, arrow para shared** — Declaraciones de función para componentes feature, arrow functions para utilidades/shared
46. **Hooks al inicio agrupados** — Hooks agrupados por categoría al inicio del componente. Early return después de hooks
47. **Helpers a nivel de archivo** — Funciones auxiliares encima del componente, no dentro
48. **i18next.t() directo** — No usar hook `useTranslation()`
49. **FontAwesome** — Solo `fasr` (sharp regular) y `fass` (sharp solid). Nunca `fal`. Si el diff introduce `fal`, reportar como **Crítico** (el icono no se renderiza en runtime)
50. **ActionTypography para códigos copiables** — Nunca Typography plano para códigos de pedidos, facturas, clientes
51. **Separar useEffects** — Un useEffect por side effect. No mezclar múltiples efectos
52. **overflow-x: clip** — Nunca `hidden` (rompe position: sticky)
53. **Props destructuradas en firma** — Destructurar props en los parámetros de la función con defaults inline: `const Component = ({label, icon, className = 'py-2'})`. No usar `props.xxx`
54. **memo() en componentes de tabla/lista** — Componentes `*TableBody` y filas de tabla/lista SIEMPRE envueltos en `memo()`: `export default memo(ComponentName)`
55. **import * as XService** — Preferir importar servicios como namespace: `import * as OrdersService from '...'`. Llamar como `OrdersService.list()`
56. **Parámetros de servicio en orden** — Funciones de servicio API siempre en orden: `(id, filter, page, perPage, sort, include)`
57. **&& para render condicional** — Preferir `{condition && <Component/>}` para una rama. Ternario solo cuando hay dos ramas reales con JSX
58. **useCustomNavigate obligatorio** — En la app web, usar siempre `useCustomNavigate` (de `hooks/Navigation/`), nunca `useNavigate` de react-router-dom directamente. El wrapper añade automáticamente el prefijo `/portal` en modo portal. Anti-patrón real detectado en `GoalsTableBody` y `ClusterProductsTableBody`
59. **useCallback en componentes memo()** — Los handlers definidos dentro de componentes envueltos con `memo()` deben usar `useCallback`. Sin esto, cada render del padre pasa nuevas instancias de funciones como props, invalidando la memoización completamente. Patrón confirmado en todos los `*TableBody` correctos del proyecto
60. **useTable para vistas de listado** — Las vistas con paginación usan `useTable({service, initialFilter, initialSort, persistedFilterCode})`. No gestionar `loading`, `filter`, `page`, `perPage`, `sort`, `content` con useState individuales. Junto a `useFilter` para los grupos de filtros visuales
61. **useDisplayColumn para columnas opcionales** — Tablas con columnas ocultables por el usuario usan `useDisplayColumn(columns)` y `displayColumn('field_id')`. No implementar esta lógica de visibilidad manualmente
62. **Componentes especializados en celdas de tabla** — En `*TableBody`, usar siempre los pipes y chips del proyecto: `DateTimeFormat` para fechas, `TextNumericFormat` para números, `EntityStatusChip` para estados, `ActionTypography` con prop `search` para códigos copiables, `SearchableTypography` para texto buscable. Nunca formatear fechas o números con métodos nativos de JS en JSX
63. **@grupodesa/core para lógica compartida** — Hooks y servicios API viven en el paquete `@grupodesa/core`. No duplicar en `apps/web/` lógica que ya existe en core. Importar siempre desde `@grupodesa/core/src/...`. Nunca usar rutas relativas que crucen packages (`../../packages/core`)
64. **hasRole segundo parámetro `false` para modo portal** — Para detectar exclusivamente el modo portal (sin incluir super-admin): `hasRole('customer', false)`. Con el parámetro omitido, super-admin también cumple la condición, lo que puede revelar UI restringida a admins
65. **Mobile: useTheme() para estilos, no StyleSheet.create** — En mobile, todos los estilos van via `useTheme()`. Acceder como `theme.pressable.primary`, `theme.text.hint`, `theme.view.screen`. Nunca `StyleSheet.create()` ni estilos inline arbitrarios. Overrides puntuales con array: `style={[theme.textInput.text, {marginBottom: 8}]}`
66. **`key` prop con ID de entidad** — En `.map()` sobre listas de entidades, usar siempre el `id` único como `key`. Nunca el índice del array (`index`). Con índices, React no puede reconciliar correctamente al reordenar o filtrar, causando bugs visuales y pérdida de estado local del componente
67. **`SimpleMenuButton` — `openMenu` como `null | id`** — En `*TableBody`, el estado `openMenu` debe ser `null | entityId`, nunca `boolean`. Con `useState(false)`, al abrir cualquier menú de fila todos los botones de la tabla reciben `Mui-focused`. Patrón correcto: `useState(null)` + `openMenu={openMenu === entity.id}` + `setOpenMenu={(open) => setOpenMenu(open ? entity.id : null)}`
68. **`handleClose` en Dialog solo cierra** — `handleClose` debe únicamente llamar `setOpen(false)`. Todo reset de estado (`setValue(null)`, `setActiveStep(0)`, etc.) debe ir en `handleClosed` vinculado a `TransitionProps={{ onExited: handleClosed }}`. Resetear estado en `handleClose` lo hace durante la animación de salida, causando espasmos visuales (cambio de tamaño, layout roto)
69. **i18next.t() nunca a nivel de módulo** — Llamar siempre dentro de componente/hook (useMemo, render). Fuera del componente falla en producción (funciona en dev por HMR)
70. **No editar archivos de traducción directamente** — Los archivos `packages/i18n/src/locales/` no se tocan a mano. Usar `/desa:translations` para gestionar terms vía API
71. **Bordes siempre con clases** — `border border-color-150`, nunca `sx={{border: '1px solid...'}}`. No cambiar grosor del border para estados activos/selected
72. **Clases condicionales con parte común** — Usar template literal con prefijo compartido: `` `background-color-${current ? 'accent-50' : '0'}` ``
73. **Elementos ocultos para medición** — `position: fixed; top: -9999`, nunca `visibility: hidden`
74. **API include siempre plano** — Nunca anidar con punto (`indicator.process`). Solo nombres de relación separados por comas. Error recurrente en Services
75. **TextNumericFormat obligatorio para números** — Nunca `Math.round`, `toFixed` ni template literals para formatear números en JSX
76. **PageLoading en diálogos** — Nunca cargar datos antes de abrir el dialog. Nunca CircularProgress en el título. PageLoading siempre dentro de `<DialogContent>`
77. **CustomFieldsForm disabled=true por defecto** — En diálogos de edición, pasar `disabled={false}` explícitamente
78. **SimpleTabs top en portal** — Sin ActionBar, pasar `top={'var(--h-menu)'}` explícitamente
79. **TableCell align="center" solo en header** — En body, centrar con `<Stack alignItems="center">` + Typography `align="center"`
80. **ExpandIcon para chevrons animados** — No implementar rotación manual, usar `<ExpandIcon expanded={open}/>`
81. **ClickableTooltip necesita ref en hijo** — Si el hijo es componente custom, envolver en `<span>`

### Criterios mobile (React Native)

82. **Reutilizar core antes de reimplementar** — Comprobar `packages/core/src/hooks/` antes de crear lógica nueva en mobile
83. **Screens sin lógica de componentes** — `app/` solo contiene screens (routing). Lógica en `components/features/`
84. **Nombres de theme = componente RN** — `pressable` no `button`, `textInput` no `input`
85. **Textos anidados en theme** — `theme.pressable.primary.text`, no `theme.pressable.primaryText`

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

## Paso 6: Ejecutar tests (solo si el proyecto tiene tests configurados)

Tras la revisión estática (Pasos 1-5), si el proyecto tiene infraestructura de tests, ejecutarlos filtrados por el diff actual para verificar que los cambios no rompen nada y que la cobertura sigue siendo aceptable.

> **⚠️ Paso 6 es incondicional respecto a Paso 5.** Aunque Paso 5 haya reportado incidencias importantes o críticas sobre los cambios (código muerto, over-engineering, etc.), Paso 6 SE EJECUTA igual si hay tests configurados. La razón es que Paso 5, Paso 6 y Paso 7 son **fuentes de información complementarias**: estilo/diseño + ejecución de tests + cobertura. El dev consolida las tres en el reporte final y decide. No omitir Paso 6 porque los cambios "parezcan mejorables" — siempre es informativo conocer si rompen tests o bajan cobertura.

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

- **Nunca** modificar el código fuente del proyecto en esta fase. Solo cambios sobre tests pre-existentes que estén fallando.
- **Nunca** generar tests nuevos aquí — eso es Paso 7.
- **Nunca** continuar a Paso 7 si Paso 6 falla y el dev no autoriza correcciones.
- Si el bucle de 3 iter no converge, devolver control al dev sin más intentos.

## Paso 7: Generar tests faltantes (solo si Paso 6 pasó y la cobertura es insuficiente)

Solo se ejecuta esta fase si:

1. Paso 6 pasó verde (todos los tests existentes en verde)
2. El reporte de cobertura muestra **líneas nuevas/modificadas del diff sin cubrir** en alguno de los ficheros del diff (independiente de cualquier umbral global del proyecto; en `desa-websites` el gate es de patch coverage por diff, no global)

Si la cobertura ya cumple, **omitir Paso 7 silenciosamente** y continuar a Paso 8.

> **⚠️ Paso 7 también es incondicional respecto a Paso 5.** Si Paso 6 pasó verde y hay gap de cobertura, Paso 7 SE EJECUTA aunque Paso 5 haya tachado los cambios como código muerto / over-engineering. La razón es la misma que con Paso 6: el dev necesita la información completa para decidir. Generar tests sobre código que quizá se va a borrar no es desperdicio — el dev verá el reporte completo y decidirá si borra el código o conserva los tests. Caso especial: si el dev finalmente decide borrar el código fuente, también borrará los tests generados — eso es trabajo trivial comparado con la pérdida de información si Paso 7 se hubiera saltado.

### Identificación de gaps

Del reporte de cobertura (generado en Paso 6 con `--coverage`), extraer:

- Ficheros modificados con líneas nuevas/modificadas sin cubrir (gap de patch coverage)
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
- **Nunca** generar tests para Server Components async en websites (limitación documentada del runtime — ver F-005 en `desa-websites/docs/superpowers/findings.md`)
- **Nunca** modificar código de producción para hacer pasar un test generado. Si un test no se puede escribir sin tocar el fuente, abortar ese gap y reportarlo al dev
- **Usar fixtures de `tests/fixtures/api/` en websites** y factories existentes en backend. NUNCA inline JSON gigante dentro de los tests
- **Estilo de assertions** debe coincidir con tests existentes del mismo dominio (no introducir `chai`/`should` si el proyecto usa `expect` de vitest, etc.)

## Paso 8: Formato de salida

```
## Revisión de código

**Proyecto**: {backend|frontend|mobile}
**Fuente**: {staged|unstaged|último commit|PR #N}
**Ficheros revisados**: {N}

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

**Resumen**: X críticos · Y importantes · Z menores
```

Si modo verbose (`--verbose` o `-v`), añadir al final:

```
### Descartadas (confianza < 75)

- **fichero:línea** — Descripción (confianza: N) [#N]
```

Omitir secciones de severidad vacías. Si no hay incidencias:

```
## Revisión de código

**Proyecto**: {backend|frontend|mobile}
**Fuente**: {staged|unstaged|último commit|PR #N}
**Ficheros revisados**: {N}

Sin incidencias. Los cambios cumplen con los estándares del equipo.
```

## Reglas estrictas

> Las siguientes reglas aplican al Paso 5 (revisión estática). Para reglas específicas del Paso 6 (ejecutar tests) y Paso 7 (generar tests), ver las "Reglas estrictas" al final de cada uno de esos pasos.

- **Nunca** sugerir añadir comentarios al código
- **Nunca** sugerir TypeScript. El frontend es JavaScript
- **Nunca** sugerir crear migraciones Laravel. No existen en este proyecto
- **Nunca** reportar incidencias preexistentes (que ya estaban antes de los cambios)
- **Nunca** reportar lo que un linter o formateador ya detectaría (imports no usados, formato)
- **Nunca** sugerir redefinir relaciones ya provistas por `Entitable`: `creator`, `updater`, `deleter`, `status`, `uploads`, `alerts`, `comments`, `audits`, `customFieldValues` — ya existen en todos los modelos de dominio
- **Nunca** reportar hardcoded class strings preexistentes — solo flagear los introducidos en el diff (`'App\\Models\\...'` en lugar de `Model::class`)
- Si la confianza es < 75, omitir la incidencia silenciosamente
- Ser conciso: una línea de descripción + una de sugerencia por incidencia
- Siempre referenciar fichero y número de línea
- No mencionar ficheros sin incidencias
- Referenciar el número de criterio entre corchetes [#N] para trazabilidad
