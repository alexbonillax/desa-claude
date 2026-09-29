# Criterios frontend (React/JS)

Criterios `#N` de `/desa:review` para el monorepo web (`apps/web/` y `packages/`). También los usa `/desa:plan`.

Los números son estables porque los citan los informes, los planes y las PRs de otros repos: no se renumeran nunca, los nuevos van al final de su fichero con el siguiente número libre (hoy, #107) y los retirados se quedan marcados como «(retirado)».

#65 (estilos de mobile con `useTheme()`) está en `criterios-mobile.md`.

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
