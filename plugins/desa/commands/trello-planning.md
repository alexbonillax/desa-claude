---
description: Refinar las tarjetas de Week To Do del tablero Desarrollo Interno de Trello, o una tarjeta concreta por su URL, para que se puedan empezar sin preguntar. Reescribe la descripción con objetivo, alcance, criterios de aceptación, dónde se toca, riesgos y dudas, conserva el texto original, pone la etiqueta de complejidad C1 a C5 y comenta qué ha cambiado. Si falta contexto para saber qué se pide, no especula y la marca con la etiqueta Requiere más contexto y las preguntas. Usar cuando se pide refinar, detallar, planificar o clasificar tarjetas, y desde la rutina programada. Escribe sin pedir confirmación y nunca mueve, archiva ni asigna
argument-hint: [URL de tarjeta | rutas de repos]
allowed-tools: Read, Grep, Glob
---

# Trello planning — Week To Do, lista para empezar

Week To Do es lo priorizado, pero en octubre de 2026 siete de sus nueve tarjetas no tenían responsable y casi ninguna tenía descripción: quien cogía una tenía que preguntar antes de empezar. Esta skill rellena el detalle de cada tarjeta y la clasifica por complejidad. Es idempotente, así que puede correr cada día como rutina sin rehacer lo ya hecho.

Antes de nada, leer `${CLAUDE_PLUGIN_ROOT}/references/trello.md`: IDs, herramientas, escala de complejidad, «Requiere más contexto» y plantillas.

## Entrada

Según `$ARGUMENTS`:

- **URLs de tarjetas** (`https://trello.com/c/…`): solo esas, estén en la lista que estén, y siempre, aunque ya estén refinadas.
- **Rutas absolutas de carpetas**: los repos donde buscar el código.
- **Sin rutas**: el directorio de trabajo, si es un repo de Grupo Desa (remote `origin` llamado `grupodesa-*` o `desa-*`), y los repos hermanos con ese nombre en la misma carpeta. Si no hay ninguno, se refina sin mirar código y se dice.
- **Sin URLs**: todas las tarjetas abiertas de Week To Do.

## Antes de escribir

1. **Herramientas**: cargarlas como dice la referencia. Sin conector, decirlo y terminar.
2. **Etiquetas**: `trelloReadBoard` `list_labels`, y localizar las cinco de complejidad por su prefijo (`C1 ·` … `C5 ·`) y `Requiere más contexto` por su nombre. Si falta alguna, terminar sin escribir nada, con los nombres y colores de la referencia para que Alex las cree.
3. **Fecha de hoy** en Europe/Madrid, para la marca.

## Por cada tarjeta

1. **Leer**:
   - `trelloReadCard` `get`: descripción, comentarios, etiquetas, miembros y `lastActivityAt`;
   - `trelloReadChecklist` `list_by_card`;
   - `trelloReadCard` `list_attachments`, por nombre.
2. **¿Saltarla?** Solo en la pasada sobre Week To Do. Se salta si la descripción termina en la marca `_Refinada por Claude · AAAA-MM-DD_` y no hay comentarios, checklists ni adjuntos posteriores a esa fecha, aparte del propio comentario de refinado.
   - Si hay novedades, se refina otra vez sobre la descripción actual: se conserva todo lo que haya añadido una persona, y el bloque «Descripción original» que ya había, sin anidar otro.
   - Con la etiqueta «Requiere más contexto», se salta si `lastActivityAt` no es posterior al último comentario «Requiere más contexto» de Claude, con un minuto de margen. Si lo es, alguien ha añadido contexto: se sigue.
3. **Contexto**:
   - **Tarjetas relacionadas**: `trelloSearch` `search_cards` con dos o tres palabras clave, en abiertas y con `is:archived`. Sirven de precedente y para detectar duplicados.
   - **Código**: en los repos disponibles, Grep de los términos del dominio (modelos, servicios, componentes, rutas) y Read de lo justo para nombrar los ficheros que se tocarían. Sin agentes.
   - **Nada inventado**: lo que no se deduzca de la tarjeta, del tablero o del código va a «Dudas abiertas», redactado como pregunta para quien la priorizó.
4. **¿Hay contexto suficiente?** Con el criterio de «Requiere más contexto» de la referencia: si el objetivo o los criterios de aceptación no se pueden escribir sin adivinar (dos lecturas, una decisión de negocio que nadie ha tomado), no se refina.
   - No tocar la descripción ni poner complejidad.
   - `attach_label` con `Requiere más contexto`, si no la tenía.
   - `add_comment` con el formato «Comentario "Requiere más contexto"» de la referencia: las preguntas concretas y, si ayuda, dónde mirar. Si ya había uno y el contexto añadido no basta, el comentario nuevo dice solo lo que sigue faltando.
   - Si ya había uno y desde entonces no hay descripción ni comentarios nuevos de una persona, no se escribe nada: la actividad era de la propia skill o de algo que no aporta contexto (una etiqueta, un movimiento).
   - Pasar a la siguiente tarjeta.
5. **Clasificar** con la escala de la referencia, por el tiempo que va a costar y no por el dominio que toca. En la duda, el nivel del tiempo más probable, con el motivo en una línea.
6. **Escribir**, sin pedir confirmación porque está pensada para la rutina, tras revisar la ortografía con `${CLAUDE_PLUGIN_ROOT}/references/ortografia.md`, y de una en una, con el reintento ante un 429 de «Trampas del conector» en la referencia (también en el paso 4):
   1. `trelloWriteCard` `update` con la descripción según la plantilla y el texto original literal al final;
   2. `attach_label` con la etiqueta de complejidad, y `detach_label` de la anterior si tenía otra distinta y de `Requiere más contexto` si la tenía;
   3. `add_comment`, que empieza por «Refinada por Claude» y dice qué secciones se han añadido, la complejidad y su motivo, las dudas abiertas y los avisos.
7. **Avisos**, en el comentario y en el resumen, sin mover nada:
   - sin responsable;
   - más de 30 días sin actividad (según el `lastActivityAt` leído antes de escribir, que la escritura lo cambia);
   - C5: hay que partirla antes de Doing, con una propuesta de partición en tarjetas o en checklist;
   - etiqueta «Bloqueado» sin el motivo en un comentario;
   - posible duplicado de otra tarjeta abierta o archivada, con su enlace.

## Resumen final

Una tabla y, debajo, las tarjetas saltadas (ya refinadas, o esperando contexto, y sin novedades) y las que han dado error. En la rutina, este resumen es la salida de la ejecución.

| Tarjeta | Complejidad | Cambios | Avisos |
|---|---|---|---|
| [#{número} {nombre}](https://trello.com/c/{shortLink}) | C3 · Media | descripción, etiqueta, comentario | sin responsable |
| [#{número} {nombre}](https://trello.com/c/{shortLink}) | Requiere más contexto | etiqueta, comentario con 4 preguntas | sin responsable |

## Límites

- Solo el tablero Desarrollo Interno, y solo la descripción, las etiquetas de complejidad, la de «Requiere más contexto» y los comentarios.
- Nada de especular: una descripción con varias lecturas no es un refinado, es «Requiere más contexto».
- Nunca mover, archivar, asignar, borrar, renombrar ni tocar otras etiquetas.
- Nunca perder texto: el original va literal, y lo que una persona añada tras un refinado se conserva.
- Si una escritura falla en una tarjeta, anotarla en el resumen y seguir con la siguiente.
