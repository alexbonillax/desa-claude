# Criterios websites (Next.js single-app)

Criterios `#N` de `/desa:review` para websites (Next.js single-app, p. ej. desa-websites). También los usa `/desa:plan`.

Los números son estables porque los citan los informes, los planes y las PRs de otros repos: no se renumeran nunca, los nuevos van al final de su fichero con el siguiente número libre (hoy, #107) y los retirados se quedan marcados como «(retirado)».

`(= #N)` marca un criterio gemelo de uno del monorepo: tiene su misma severidad, y si se cambia uno hay que cambiar el otro. `(≈ #N)` marca el mismo tema con matices propios de este stack.

86. (= #34) **Semicolons obligatorios** — En toda sentencia
87. (= #35) **className con llaves** — `className={'clase'}`, no `className="clase"`
88. (≈ #37) **Evitar sx prop** — Preferir clases Tailwind o estilos en SCSS. Solo usar `sx` cuando se necesita acceder a `theme` o props de MUI
89. (= #39) **Typography con variant** — Nunca estilos inline (`sx={{fontSize, fontWeight}}`)
90. (= #41) **Props string sin llaves** — `variant="contained"`, no `variant={"contained"}`
91. (= #43) **No if/else inline** — Siempre con llaves y saltos de línea
92. (= #44) **No abreviaturas de una letra** — En `.map()`, `.filter()`, `.find()` usar nombres descriptivos (`item`, `order`), no `x`, `e`, `i`
93. (= #46) **Hooks al inicio agrupados** — Hooks agrupados por categoría al inicio del componente. Early return después de hooks
94. (= #53) **Props destructuradas en firma** — Destructurar props en los parámetros de la función con defaults inline: `const Component = ({label, icon, className = 'py-2'})`. No usar `props.xxx`
95. (= #55) **import \* as XService** — Preferir importar servicios como namespace: `import * as SitesService from '@/api/services/SitesService'`. Llamar como `SitesService.get()`
96. (= #66) **`key` prop con ID de entidad** — En `.map()` sobre listas de entidades, usar siempre el `id` único como `key`. Nunca el índice del array
97. (= #69) **i18next.t() nunca a nivel de módulo** — Llamar siempre dentro de componente/hook (useMemo, render). Fuera del componente falla en producción (funciona en dev por HMR)
98. **LocaleLink obligatorio en Client Components, `localePath(locale, path)` en Server Components** — Nunca usar `<Link>` de Next.js sin prefijo de locale. Los enlaces internos deben preservar el locale activo (ES/FR/PT)
99. **MUI imports directos** — `import Button from '@mui/material/Button'`, no `import { Button } from '@mui/material'`. La excepción es `useTheme`, que debe importarse desde `@mui/material` (no desde `@mui/material/styles`)
100. **Server Components por defecto** — Solo usar `'use client'` cuando sea estrictamente necesario (estado, eventos del DOM, hooks de React que requieren cliente). Si no, dejar el componente como Server Component
101. **API devuelve `.data`** — Siempre desestructurar el resultado de las llamadas a servicios: `(await SitesService.xxx()).data`. La API retorna `null` en errores; verificar antes de acceder a propiedades anidadas
102. **`fetch` siempre vía wrapper `api.js`** — Nunca llamar a `fetch()` directamente desde componentes o hooks. Usar `api.get()` / `api.post()` de `src/api/api.js`, que añade Accept-Language, gestiona ISR `revalidate` y maneja errores uniformemente
103. **ISR revalidate via constantes `REVALIDATE`** — En las llamadas a servicios, pasar uno de los valores de `REVALIDATE` (`SITE: 300`, `CATEGORIES: 300`, `COLLECTIONS: 60`, `POST: 5`). Nunca hardcodear segundos. Si necesitas otro valor, añadirlo a `REVALIDATE` y reutilizar
104. **Server Components async no se testean en unit** — Si la lógica de un Server Component crece, **factorizarla a hooks o utilidades** que sí sean testables con Vitest. Los Server Components async se cubren con E2E (Playwright), no con Vitest
105. **MSW intercepta `fetch` en tests** — Los tests unit con MSW activo NO deben mockear `fetch` directamente. Usar fixtures de `tests/fixtures/api/` y, si falta una, crear una nueva fixture explícita en lugar de inline mock dentro del test
106. **`globalThis.session` reset automático en tests** — `tests/setup.js` lo resetea en cada `beforeEach`. No resetearlo manualmente en los tests. Si un test necesita un locale concreto, llamar `setSession('locale', 'fr')` al inicio del test, no recrear el objeto entero
