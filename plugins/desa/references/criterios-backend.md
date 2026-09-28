# Criterios backend (Laravel/PHP)

Criterios `#N` de `/desa:review` para backend (Laravel/PHP). También los usa `/desa:plan`.

Los números son estables porque los citan los informes, los planes y las PRs de otros repos: no se renumeran nunca, los nuevos van al final de su fichero con el siguiente número libre (hoy, #107) y los retirados se quedan marcados como «(retirado)».

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
