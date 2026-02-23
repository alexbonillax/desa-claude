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

### Criterios compartidos (ambos proyectos)

1. **Adherencia a patrones preexistentes** — El código nuevo DEBE seguir los patrones del proyecto. Si hay duda, leer un fichero de referencia del mismo dominio para comparar
2. **Escalabilidad y mantenibilidad** — Acoplamiento excesivo, lógica duplicada, abstracciones prematuras o ausentes
3. **Legibilidad** — Nombres claros, flujo comprensible, sin complejidad innecesaria
4. **Sin comentarios** — Ni explicativos ni TODOs. Código autodocumentado
5. **Causas raíz** — Detectar fixes temporales, workarounds o parches sobre código problemático
6. **Seguridad** — SQL injection, XSS, autenticación/autorización, secretos hardcodeados, inputs no validados

### Criterios backend (Laravel/PHP)

7. **Estructura por dominio** — `app/Models/{Domain}/`, `app/Services/{Domain}/`, `app/Http/Resources/{Domain}/`, `app/Http/Requests/{Domain}/`
8. **Patrón CRUD completo** — Entidades nuevas deben tener Model, Request, Service y Resource
9. **Relaciones polimórficas** — Via `model_has_relations` con `wherePivotNull('deleted_at')`
10. **Roles whitelist** — Siempre `hasRole('employee|customer')`, nunca `!hasRole('...')`
11. **Filtrado dual** — Service controla eager loading (`Auth::hasRole`), Resource controla serialización (`$this->hasRole`)
12. **Naming** — snake_case en respuestas JSON, camelCase en relaciones PHP
13. **Sin migraciones** — No debe haber ficheros nuevos en `database/migrations/`
14. **Rutas** — Prefix una sola vez, agrupadas por dominio, middleware al nivel más alto aplicable
15. **Validación de arrays** — `'field' => 'present|array'` + `'field.*' => 'required|numeric|exists:table,id'`
16. **Include pattern** — Carga condicional via `?include=` con `in_array()` en Service
17. **Resource pattern** — Campos condicionales via `$this->relationLoaded()` en Resource
18. **Services devuelven response()** — `return response(new XResource($model), Response::HTTP_CREATED)`, nunca el modelo directamente
19. **Excepciones con HTTP status** — `throw new Exception(Response::HTTP_CONFLICT)`. El status code es el mensaje de la excepción, capturado por `exceptionResponse()`
20. **Transacciones explícitas** — Toda escritura en `DB::beginTransaction()` / `commit()` / `rollBack()` dentro de try-catch
21. **broadcast() después de commit()** — Eventos broadcast SIEMPRE después de `DB::commit()`, nunca dentro del try antes del commit
22. **withTrashed() en BelongsTo** — Relaciones BelongsTo deben incluir `->withTrashed()` si el modelo relacionado usa soft deletes
23. **GetRequest para listados** — Usar `GetRequest` que centraliza parsing de `include`, `filter`, `sort`, `perPage`. No reinventar el parsing
24. **Traits para estado** — Métodos de estado (`isEditable()`, `isDeletable()`) via trait `Entitable`, no directamente en el modelo

### Criterios frontend (React/JS)

25. **Semicolons obligatorios** — En toda sentencia
26. **className con llaves** — `className={'clase'}`, no `className="clase"`
27. **Espaciado en items** — No `gap`/`spacing` en contenedores. Usar `mx-1`, `px-2` en hijos
28. **Evitar sx prop** — Preferir clases CSS
29. **No w-full** — Usar `width="100%"` como prop de MUI
30. **Typography con variant** — Nunca estilos inline (`sx={{fontSize, fontWeight}}`)
31. **Botones sin Typography** — Texto directo como children del Button
32. **Props string sin llaves** — `variant="contained"`, no `variant={"contained"}`
33. **No pasar valores por defecto** — Omitir parámetros que coincidan con el default de la función
34. **No if/else inline** — Siempre con llaves y saltos de línea
35. **No abreviaturas de una letra** — En `.map()`, `.filter()`, `.find()` usar nombres descriptivos (`item`, `order`), no `x`, `e`, `i`
36. **function para features, arrow para shared** — Declaraciones de función para componentes feature, arrow functions para utilidades/shared
37. **Hooks al inicio agrupados** — Hooks agrupados por categoría al inicio del componente. Early return después de hooks
38. **Helpers a nivel de archivo** — Funciones auxiliares encima del componente, no dentro
39. **i18next.t() directo** — No usar hook `useTranslation()`
40. **FontAwesome** — Solo `fasr` (sharp regular) y `fass` (sharp solid). Nunca `fal`
41. **ActionTypography para códigos copiables** — Nunca Typography plano para códigos de pedidos, facturas, clientes
42. **Separar useEffects** — Un useEffect por side effect. No mezclar múltiples efectos
43. **overflow-x: clip** — Nunca `hidden` (rompe position: sticky)
44. **Props destructuradas en firma** — Destructurar props en los parámetros de la función con defaults inline: `const Component = ({label, icon, className = 'py-2'})`
45. **useCallback para handlers** — Todo event handler y función derivada debe usar `useCallback` con dependencias explícitas
46. **memo() en componentes de tabla/lista** — Componentes de filas de tabla y items de lista envueltos en `memo()` para evitar re-renders
47. **import * as XService** — Servicios importados como namespace: `import * as OrdersService from '...'`. Llamar como `OrdersService.list()`
48. **Parámetros de servicio en orden** — Funciones de servicio API siempre en orden: `(id, filter, page, perPage, sort, include)`
49. **&& para una rama, ternario para dos** — `{condition && <Component/>}` para una rama. Ternario solo cuando hay dos ramas con JSX
50. **Callbacks al padre para save** — Componentes hijos llaman `handleOnSave` del padre. El hijo no gestiona estado de persistencia

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
- Si la confianza es < 75, omitir la incidencia silenciosamente
- Ser conciso: una línea de descripción + una de sugerencia por incidencia
- Siempre referenciar fichero y número de línea
- No mencionar ficheros sin incidencias
- Referenciar el número de criterio entre corchetes [#N] para trazabilidad
