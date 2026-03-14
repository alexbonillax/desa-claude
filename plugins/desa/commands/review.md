---
description: Revisar código aplicando los estándares del equipo antes de commit o PR
argument-hint: [ruta de archivo, número de PR (#42), o vacío para cambios locales]
allowed-tools: Bash(git:*), Bash(gh:*)
---

# Review — Revisión de código con estándares Grupo Desa

Revisa cambios de código aplicando las convenciones del equipo. Detecta automáticamente si el proyecto es backend (Laravel/PHP) o frontend (React/JS monorepo).

## Paso 1: Detectar tipo de proyecto

Desde el directorio de trabajo actual:

```bash
if [ -f artisan ] && [ -f composer.json ]; then echo "backend"; elif [ -d apps/web ] || [ -d apps/mobile ] || [ -d packages/core ]; then echo "frontend"; else echo "unknown"; fi
```

Si es `unknown`, informar al usuario y terminar.

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

## Paso 4: Contexto de patrones existentes

Solo cuando una incidencia potencial requiera verificación contra el código existente (criterio #1), leer un fichero del mismo directorio o dominio que sirva de referencia. No leer ficheros preventivamente — solo bajo demanda para confirmar o descartar una sospecha.

## Paso 5: Revisar los cambios

Analizar cada fichero modificado. Para cada posible incidencia, asignar internamente un nivel de confianza (0-100). **Solo reportar incidencias con confianza >= 75.**

**Severidad**: Crítico para seguridad, corrupción de datos o bugs silenciosos (criterios #6, #13, #22, #25, #27, #30, #33). Importante para violaciones de patrón estructural que afectan a corrección o mantenibilidad. Menor para estilo, naming y convenciones.

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
49. **FontAwesome** — Solo `fasr` (sharp regular) y `fass` (sharp solid). Nunca `fal`
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

## Paso 6: Formato de salida

```
## Revisión de código

**Proyecto**: {backend|frontend}
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

Omitir secciones de severidad vacías. Si no hay incidencias:

```
## Revisión de código

**Proyecto**: {backend|frontend}
**Fuente**: {staged|unstaged|último commit|PR #N}
**Ficheros revisados**: {N}

Sin incidencias. Los cambios cumplen con los estándares del equipo.
```

## Reglas estrictas

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
