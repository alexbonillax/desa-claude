# Trello: tablero Desarrollo Interno

La usan:
- el hook del plugin, que en cada sesión de un repo de Grupo Desa pide seguir «Sesión»;
- `/desa:plan`, que anota la tarjeta en el plan;
- `/desa:trello-planning`.

Es la única fuente de los IDs del tablero, las reglas del kanban, el procedimiento de sesión, la escala de complejidad y las plantillas: si algo cambia en el tablero, se cambia aquí.

## Tablero

- **Desarrollo Interno**, espacio de trabajo **Desa**: https://trello.com/b/OomXKfpS/desarrollo-interno
- Board: `ari:cloud:trello::board/workspace/5be2ea37b491941a347d29fe/62b1608b9241c8343231c893`

| Lista | ARI |
|---|---|
| Backlog | `ari:cloud:trello::list/workspace/5be2ea37b491941a347d29fe/62c28773025dc026d874eb14` |
| Week To Do | `ari:cloud:trello::list/workspace/5be2ea37b491941a347d29fe/63183c9412bd6e046413408a` |
| Doing | `ari:cloud:trello::list/workspace/5be2ea37b491941a347d29fe/62b1608b9241c8343231c89b` |
| To Validate | `ari:cloud:trello::list/workspace/5be2ea37b491941a347d29fe/62c2876fd8b4f36e2b521eb2` |
| Done | `ari:cloud:trello::list/workspace/5be2ea37b491941a347d29fe/62b1608b9241c8343231c89c` |

**Validador**: Alex, `alexbonillax`, `ari:cloud:trello::user/5be2e941a19fa536ab013a79`. Es el único que pasa tarjetas de To Validate a Done.

Si un ARI deja de funcionar (lista renombrada o recreada), buscar la lista por nombre con `trelloReadList` `list_by_board` y avisar de que esta referencia está desactualizada.

## Herramientas

Son las del conector de Trello de claude.ai. El prefijo cambia de una cuenta a otra (`mcp__<id>__trelloReadCard`), así que se nombran por el sufijo y se cargan con ToolSearch, consulta `+trello`, `max_results` 15.

Si ToolSearch no devuelve ninguna, el conector no está. Decirlo una vez («conecta Trello en claude.ai, Ajustes > Conectores, con la cuenta que tiene acceso al tablero») y seguir con el trabajo sin Trello.

| Para | Herramienta y acción |
|---|---|
| Quién soy | `trelloReadMember` `get_me` |
| Tarjetas abiertas por lista | `trelloReadCard` `list_by_board` con `limit` 10 (sin `checklists`: vienen vacíos aunque los haya) |
| Una tarjeta, con comentarios | `trelloReadCard` `get` (admite la URL) |
| Checklists de una tarjeta | `trelloReadChecklist` `list_by_card` (pide el ARI de la tarjeta) |
| Buscar por texto | `trelloSearch` `search_cards` con `boardIds` del tablero; `is:archived` para las archivadas |
| Etiquetas del tablero | `trelloReadBoard` `list_labels` con `limit` 100 |
| Crear, mover, comentar, etiquetar | `trelloWriteCard` `create`, `move`, `update`, `add_comment`, `attach_label`, `detach_label` |
| Checklists e ítems | `trelloWriteChecklist` `create`, `add_item`, `update_item` (`checked`) |

Trampas del conector:

- Las escrituras piden el ARI (`id`), nunca la URL: leer antes la tarjeta con `get`.
- **No puede asignar personas a una tarjeta ni crear etiquetas.**
  - **El responsable lo pone una regla de Butler del tablero** (Automatización › Reglas): `when a card is added to list "Doing" by anyone, add member {username} to the card`. Así queda asignado quien crea una tarjeta en Doing o quien la pasa a Doing, sea una sesión o una persona.
  - Butler va unos segundos por detrás. Después de crear o mover una tarjeta a Doing, releerla con `get`: si el usuario sigue sin estar en `members`, la regla no está o ha fallado. Decirlo y dar el enlace para que se la asigne.
  - Precedente: #2213 (octubre de 2026) se creó desde una sesión, se cerró y llegó a Done sin responsable.
  - Las etiquetas de complejidad las crea Alex a mano (ver «Complejidad»).
- Las fechas vienen en UTC. Al enseñarlas, pasarlas a Europe/Madrid.
- **Trello limita las peticiones** y devuelve un 429 con `retry-after` si llegan demasiadas seguidas.
  - Las escrituras van de una en una, nunca en paralelo. Las lecturas sí pueden ir en paralelo.
  - Con un 429, esperar hasta la hora del `retry-after` (unos segundos) y reintentar esa escritura una vez.
  - Si vuelve a fallar, anotarla como error y seguir con la siguiente.
  - Precedente: en la primera pasada de `/desa:trello-planning` (octubre de 2026) se lanzaron 12 escrituras en paralelo y dos devolvieron un 429.

## Reglas del kanban

Backlog → Week To Do → Doing → To Validate → Done. **Una tarjeta nunca retrocede.**

- **Week To Do es lo priorizado.** Priorizar es de Alex: nunca se mueve nada a Week To Do, nunca se archiva y nunca se borra.
- **Al empezar a trabajar** una tarjeta, si está en Backlog o Week To Do pasa a Doing. Si está en To Validate, se queda ahí aunque se retoque.
- **Límite WIP de 3**: si quien trabaja ya tiene 3 tarjetas en Doing, avisar con sus nombres y preguntar antes de mover la cuarta. No bloquea.
- **Al terminar**:
  - cualquiera salvo el validador deja la tarjeta en To Validate;
  - el validador elige entre To Validate y Done, con una propuesta: Done si ya es evidente que está validado en la sesión (lo comprobó en el navegador o con los tests que cubren el cambio, lo dio por bueno, o está en `main`), y To Validate si no.
- **Si al validar algo no está bien**, la tarjeta se queda en To Validate con un comentario de qué falta.
- **Done no se reabre**: el trabajo nuevo sobre algo terminado va en una tarjeta nueva que enlaza a la anterior.
- **Ítem de checklist**: al terminar se marca el ítem, y la tarjeta solo se mueve cuando no quedan ítems abiertos.
- **Pasos pendientes en producción** (SQL a mano, `artisan`, cambios en vistas de Snowflake, variables de entorno, backfills):
  - van en un checklist **«Pendiente en producción»** de la tarjeta, nunca solo en un comentario;
  - antes de proponer Done, mirar si ese checklist tiene ítems abiertos y decirlo.
- **«Bloqueado»** (etiqueta del tablero) lleva siempre el motivo escrito en un comentario.
- **«Requiere más contexto»** (ver su sección) espera a que Alex añada contexto: no entra en Doing sin preguntar.

## Sesión

Cada sesión de trabajo en un proyecto de Grupo Desa va contra una tarjeta, o un ítem de checklist, de este tablero. **Nadie invoca nada**:
- el hook del plugin pide «Vincular» al empezar la sesión y «Cerrar» tras cada commit;
- `/desa:plan` hace la parte de «Vincular» al planificar.

Existe porque el tablero dejó de reflejar el trabajo real: en octubre de 2026 la adaptación a compras seguía en Backlog con el trabajo a medias en el código, y dos tarjetas pasaron a Done con un `ALTER TABLE` y una vista de Snowflake pendientes que solo constaban en un comentario.

Una pregunta, una revisión o una exploración que no cambia nada no se vincula ni crea tarjetas. Si el usuario pregunta en qué tarjeta está la sesión, se responde con la línea del vínculo (paso 8).

### Vincular

Antes de la primera edición de una petición de trabajo. Si la sesión ya está vinculada y el trabajo es el mismo, no se hace nada.

1. **Herramientas**: cargarlas como dice «Herramientas». Sin conector, avisar una vez y seguir sin Trello.
2. **Quién trabaja**: `trelloReadMember` `get_me`. Si es `alexbonillax`, al cerrar actúa como validador.
3. **Qué se va a hacer**: la petición del usuario, más lo que dice el repo. El nombre del repo, `git status --short` (los ficheros sin commitear dicen el dominio) y `git log --oneline -5`.
4. **Candidatas**, de barato a caro:
   - `trelloReadCard` `list_by_board` (todas las listas abiertas, unas 40 tarjetas);
   - `trelloSearch` `search_cards` con dos o tres palabras clave del trabajo y `boardIds` del tablero, y con `is:archived` si parece algo ya hecho;
   - `trelloReadChecklist` `list_by_card` de las tres a cinco tarjetas más cercanas y de las tarjetas paraguas de Doing y Week To Do (nombres como «Mejoras …» o «Fase N»): un ítem abierto puede ser exactamente el trabajo.
5. **Decidir**:
   - **Una coincidencia clara**, tarjeta o ítem: vincular y decirlo.
   - **Varias plausibles**: AskUserQuestion con dos o tres candidatas (nombre, lista y número) y «Tarjeta nueva».
   - **Coincide con una tarjeta en Done o archivada**: no se reabre. Tarjeta nueva, con el enlace a la anterior en la descripción.
   - **Nada**: crear y avisar en el mismo mensaje, sin preguntar antes.
     - Si el trabajo encaja claramente en una tarjeta paraguas, un ítem en su checklist (`trelloWriteChecklist` `add_item`).
     - Si no, una tarjeta en Doing (`trelloWriteCard` `create`, `listId` de Doing, `pos` `top`), con el nombre según «Textos» y una descripción de dos a cuatro líneas: el objetivo y lo que se sabe. El responsable lo pone la regla de Butler: comprobarlo como dice «Trampas del conector».
6. **Mover hacia delante**: si la tarjeta (o la tarjeta paraguas del ítem) está en Backlog o Week To Do, pasa a Doing.
   - Si la tarjeta tiene «Requiere más contexto», avisar y preguntar antes de moverla.
   - Antes, contar las tarjetas de Doing que tienen al usuario en `members`. Con tres o más, AskUserQuestion con sus nombres: «Tienes 3 en Doing. ¿Muevo esta igualmente?», con las opciones «Mover a Doing» y «Dejarla donde está».
   - Si no, `trelloWriteCard` `move` a Doing y decirlo. La regla de Butler asigna a quien la mueve; comprobarlo como al crear.
   - En Doing o To Validate no se mueve.
7. **Complejidad**: si la tarjeta no tiene etiqueta `C1 ·` … `C5 ·` ni «Requiere más contexto», ponérsela (`trelloWriteCard` `attach_label`, con el ARI de `list_labels`). Si ya tiene una, no se toca.
   - Se clasifica con la escala de «Complejidad», por el tiempo que va a costar a partir de lo que se sabe del trabajo.
   - Con `/desa:plan`, sale de los archivos y cambios del plan, no de su perfil.
   - Precedente: en octubre de 2026 las tarjetas creadas desde `/desa:plan` llegaban sin complejidad, que solo ponía `/desa:trello-planning` en Week To Do.
8. **Dejar el vínculo a la vista**, en una línea que se pueda encontrar tras una compactación:

   ```
   Trello: «{nombre}» (#{número}, {lista}) → ítem «{ítem}» · https://trello.com/c/{shortLink}
   ```

   - El número es el del slug de la URL (`/c/X9po4R28/2208-…` → 2208).
   - Si existe la herramienta que pone título a la sesión (en la app de escritorio, `set_session_title`), ponerle `#{número} {nombre}`, recortado a 60 caracteres.
   - Mientras dure el vínculo, los commits llevan la línea de «Commits».

**Cambio de tarea**: si la sesión está vinculada y el usuario pide otro trabajo, proponer «Cerrar» la tarjeta actual antes de vincular la nueva. Si no quiere cerrarla, vincular la nueva y decir que la anterior se queda como está.

### Cerrar

Tras el commit que termina el trabajo, o cuando el usuario lo da por terminado. Si la sesión no estaba vinculada, primero «Vincular» con lo hecho.

1. **Releer** la tarjeta (`get`) y sus checklists: puede haber cambiado de lista mientras tanto.
2. **Reunir lo hecho**, solo con lo visto en la sesión:
   - los commits de la sesión, la rama y los repos tocados;
   - lo que queda sin commitear (`git status --short`). Si queda algo, decirlo, y no proponer Done;
   - la verificación: tests que cubren el cambio, comprobación en el navegador, el usuario lo dio por bueno, o «sin verificar»;
   - los pasos pendientes en producción: SQL o comandos que se dijeron en la sesión para ejecutar a mano, migraciones nuevas, cambios en vistas de Snowflake o DBT, variables de entorno, backfills. Solo lo que esté claro.
3. **Destino**:

   | Dónde está | Quien no valida | El validador |
   |---|---|---|
   | Ítem de checklist | se marca; la tarjeta solo se mueve si no quedan ítems abiertos, y entonces como una tarjeta | igual |
   | Doing | To Validate | Done si ya está validado en la sesión; si no, To Validate |
   | To Validate | se queda | Done si ya está validado; si no, se queda |
   | Done | nada | nada |

   Si el checklist «Pendiente en producción» tiene ítems abiertos, contando los nuevos, decirlo en la propuesta y no recomendar Done.
4. **Vista previa y un sí**: enseñar el comentario de cierre (formato de «Textos»), los ítems de «Pendiente en producción» y el movimiento. Después, AskUserQuestion con la recomendación primero:
   - validador: «Done», «To Validate» y «Solo comentar», en el orden que toque;
   - quien no valida, con la tarjeta en Doing: «To Validate» y «Solo comentar»;
   - con la tarjeta ya en To Validate: «Comentar» y «Nada».
5. **Aplicar**, en este orden y tras revisar la ortografía con `references/ortografia.md`:
   1. `add_comment`;
   2. el checklist «Pendiente en producción», nuevo (`create` y `add_item`) o añadiendo a uno que ya exista;
   3. el ítem (`update_item` con `checked`);
   4. el movimiento (`move`, `pos` `top`).
6. **Resumen**: una línea con lo que se ha hecho y el enlace de la tarjeta.

### Límites de la sesión

- Solo este tablero.
- Crear una tarjeta o un ítem y pasar a Doing al empezar van avisando. Comentar, marcar ítems y cualquier movimiento al terminar van con un sí.
- Nunca mover hacia atrás ni a Week To Do, nunca archivar ni borrar, y nunca reescribir la descripción de una tarjeta: eso es de `/desa:trello-planning`.
- Si una escritura falla, decirlo con el error y seguir con el trabajo, sin reintentar en bucle.

## Complejidad

Cinco etiquetas, una por tarjeta. Las crea Alex en Trello; si falta alguna, `/desa:trello-planning` para y dice cuáles faltan.

**La complejidad es el tiempo que va a costar, con la forma de trabajar del equipo (con Claude Code), no el riesgo ni el dominio.**

| Etiqueta | Color | Tiempo | Ejemplos |
|---|---|---|---|
| `C1 · Trivial` | sky_light | < 1 h | un texto, CSS, una config, un dato |
| `C2 · Pequeña` | sky | ≤ 1 día | un cambio acotado con patrón a la vista, aunque toque back y front o lleve una migración |
| `C3 · Media` | sky_dark | 1–2 días | varias piezas nuevas, o un patrón que todavía no existe |
| `C4 · Grande` | blue_dark | 3–5 días | varios módulos con piezas nuevas, o una integración nueva con un sistema externo |
| `C5 · Épica` | black | > 1 semana, o grande con partes por decidir | se parte antes de entrar en Doing |

- **Lo que no sube el nivel por sí solo**: tocar compras, precios, pedidos, Spyro, Snowflake o DBT. Eso sube el riesgo, que va en «Riesgos y pasos de despliegue», pero no el tiempo. Una integración nueva sí lo sube; leer un campo más de una que ya existe, no.
- **En la duda**, el nivel del tiempo más probable, no el mayor, y el motivo en una línea.
- **El perfil de `/desa:plan` no decide la complejidad**: mide cuánto análisis merece la tarea y su riesgo. Un L puede ser un C2.
- **Precedente**: en octubre de 2026, «Lead times de proveedor y producto» y «Grupos de producto en los lead times de proveedor» salieron C4 desde `/desa:plan` por tocar compras y varios módulos, y eran de menos de un día.

Se reconocen por el prefijo `C1 ·` … `C5 ·`, no por el ARI. Si falta contexto para saber qué se pide, no se clasifica: va «Requiere más contexto».

## Requiere más contexto

Etiqueta `Requiere más contexto`, roja oscura (`red_dark`, para no confundirla con el rojo de «Bloqueado»). Se reconoce por el nombre.

- **Cuándo**: no se puede escribir el objetivo ni los criterios de aceptación sin adivinar.
  - Ejemplos: sin descripción ni comentarios útiles y con un nombre que admite más de una lectura, o algo que depende de una decisión de negocio que no está en la tarjeta, el tablero ni el código.
  - Si solo quedan dudas menores, se refina y van a «Dudas abiertas».
  - Precedente: «Pedido de carga camión» (octubre de 2026) se refinó con dos lecturas y una C5 por alcance incierto. La descripción quedó llena de dudas que solo Alex podía resolver.
- **Qué se hace**: ni se reescribe la descripción ni se pone complejidad. Se pone la etiqueta y un comentario con las preguntas concretas (formato en «Textos»).
- **Qué sigue**:
  1. Alex añade el contexto, en la descripción o en un comentario.
  2. La siguiente pasada lo detecta porque `lastActivityAt` es posterior a ese comentario, con un minuto de margen, porque las escrituras de la propia skill también lo mueven.
  3. Entonces refina, clasifica y quita la etiqueta.
  4. Si el contexto sigue sin bastar, deja un comentario nuevo con lo que falta, sin repetir el anterior.
- **En una sesión**: una tarjeta con esta etiqueta no debería pasar a Doing. Al vincularla, avisar y preguntar antes de moverla.

## Textos

Español de España, sin emojis, con la ortografía de `references/ortografia.md`. Las tarjetas nuevas se nombran con el resultado en una frase corta, como las del tablero: «Añadir importe de portes cobrado en albaranes», «Fix cupones en portal».

### Descripción refinada

La escribe `/desa:trello-planning`. El texto original va siempre literal al final.

```markdown
**Objetivo**
Qué problema resuelve y para quién, en una o dos frases.

**Alcance**
- Entra: …
- No entra: …

**Criterios de aceptación** (propuestos)
- …

**Dónde se toca**
- `grupodesa-backend`: `ruta/vista/en/el/código` …
- `grupodesa-front`: …

**Riesgos y pasos de despliegue**
- …

**Dudas abiertas**
- …

**Complejidad**: C3 · Media. Motivo en una línea.

---
**Descripción original**
El texto que tenía la tarjeta, tal cual, o «(sin descripción)».

_Refinada por Claude · AAAA-MM-DD_
```

Una sección sin nada que decir se quita, salvo «Dudas abiertas», que dice «Ninguna» si no hay. En «Dónde se toca» solo rutas vistas en el código; lo que se supone va con «probable».

### Comentario «Requiere más contexto»

Lo deja `/desa:trello-planning` en vez de refinar:

```markdown
**Requiere más contexto** · Claude · AAAA-MM-DD

Por qué no se ha podido refinar, en una o dos frases. Cuando se añada el contexto, en la descripción o en un comentario, la siguiente pasada la refina, le pone complejidad y quita esta etiqueta.

**Qué falta saber**:
- Preguntas concretas, que se contesten en una línea cada una.

**Para contestar**: dónde mirar o qué hay ya en el código o en el tablero, si ayuda. (Opcional.)

**Aviso**: sin responsable. (Solo los avisos que haya.)
```

### Comentario de cierre

Lo deja «Cerrar», en el formato de los comentarios de David:

```markdown
**Hecho en sesión** · AAAA-MM-DD · {persona}
Qué cambia para quien usa la aplicación, en una a tres líneas.

**Backend** (`grupodesa-backend`, rama `{rama}`): qué cambia.
**Frontend** (`grupodesa-front`, rama `{rama}`): qué cambia.
**Commits**: `abc1234` mensaje, `def5678` mensaje.
**Verificado**: cómo, o «sin verificar».
**Pendiente en producción**: ver checklist. (Solo si lo hay.)
```

### Commits

Mientras la sesión esté vinculada, cada commit lleva en su bloque final, antes de las líneas de coautoría, `Trello: https://trello.com/c/{shortLink}`. Así se llega de `git log` a la tarjeta.
