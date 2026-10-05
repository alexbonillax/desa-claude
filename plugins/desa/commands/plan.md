---
description: Planificar una tarea antes de implementarla, desde la petición hasta un plan que el usuario aprueba en plan mode. Usar cuando se pide un plan, y también con síntomas sin la causa a la vista («va lento», «tarda X», «falla a veces», «no aparece»), con preguntas de decisión («¿merece la pena?», «¿se puede borrar?», «¿aplica en otros sitios?», «¿cuál de las dos?»), con auditorías o barridos («detecta y enumera», «barrido», «todas las…», «carencias»), con peticiones de alcance incierto y para frenar un trabajo en curso que se alarga. Primero clasifica la petición. Si el alcance está claro, planifica sin ceremonia; si es un síntoma o una decisión, la acota antes (premio, comprobación descalificante y presupuesto de agentes con veto del usuario) y puede cerrar sin plan. Explora el código, inventaría lo reutilizable, aplica los criterios de /desa:review y el plan dice con qué modelo, esfuerzo y cuántos agentes ejecutarlo. No implementa ni cambia el modelo de la sesión. No usar para arreglar un error cuya causa ya está a la vista si no se pide un plan
argument-hint: [tarea, síntoma o pregunta de decisión]
allowed-tools: Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh:*), Read, Grep, Glob
hooks:
  PreToolUse:
    - matcher: "Workflow"
      hooks:
        - type: command
          command: >-
            printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"/desa:plan [T-7]: un Workflow necesita tu sí explícito, también con ultracode activo"}}'
    - matcher: "Agent"
      hooks:
        - type: command
          command: |-
            sid=$(tr -d '\n' | grep -o '"session_id" *: *"[^"]*"' | sed 's/.*: *"//; s/"$//' | tr -cd 'A-Za-z0-9_-')
            f="${TMPDIR:-/tmp}/desa-plan-agentes-${sid:-$PPID}"
            n=$(( $(cat "$f" 2>/dev/null || echo 0) + 1 ))
            echo "$n" > "$f"
            [ "$n" -le 3 ] || printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"/desa:plan [T-7]: más de 3 agentes en esta sesión necesitan tu sí"}}'
---

# Plan — De la petición al plan aprobado, con estándares Grupo Desa

Convierte una petición en un plan ejecutable que el usuario aprueba antes de implementar, aplicando los criterios de `/desa:review` *antes* de escribir código y priorizando la reutilización de lo que ya existe. Antes de planificar decide cuánto análisis merece la petición, y el plan dice con qué modelo, esfuerzo y cuántos agentes ejecutarlo.

Existe porque el fallo caro no es planificar mal, es **analizar mucho lo que no lo merecía**. Las reglas `[T-N]` salen de fallos reales medidos y se citan por su número, como los `#N` de review; no se renumeran. Venían de `/desa:triage`, que en la 1.19.0 se fundió aquí como la ruta «acotar».

Si `$ARGUMENTS` está vacío y la petición tampoco está en el mensaje que ha invocado la skill, pedirla al usuario y terminar.

## Flujo y límites

Pasos: 0) ruta y perfil; en B, C y Freno, acotar; 1) tipo de proyecto; 2) contexto fijo; 3) explorar; 4) borrador; 5) criterios de review; 6) ejecución; 7) plan file; 8) `ExitPlanMode`. Si tras una compactación falta parte de estas instrucciones, releer `${CLAUDE_PLUGIN_ROOT}/commands/plan.md`, y en B, C o Freno también `${CLAUDE_PLUGIN_ROOT}/references/acotar.md`, antes de seguir.

**Plan mode.** El plan se aprueba con `ExitPlanMode`, y el fichero del plan solo tiene ruta asignada en plan mode. Si el system reminder no indica plan mode, llamar a `EnterPlanMode` justo antes del Paso 3, no antes: acotar mide, y una petición que termina sin plan no debe dejar la sesión en plan mode. Si no está disponible o el usuario prefiere no usarlo, entregar el plan en el chat sin escribir ficheros, y terminar ahí. El recordatorio de plan mode sugiere lanzar Explore en paralelo y un Plan agent: no cambia el tope del perfil. En S, 0 agentes, y nunca un Plan agent: el plan lo escribe esta skill.

**Límites**:

- **Nunca implementar antes de que el usuario apruebe el plan** en `ExitPlanMode`: el valor del plan está en esa aprobación. Acotar tampoco implementa: mide y encamina.
- **Ningún agente antes de la línea de ruta y, en B, C y Freno, del premio y la comprobación descalificante respondida en solo** ([T-4]): escribir la pregunta y delegar la respuesta no cuenta. En la ruta A la comprobación es el Grep de reuso del Paso 3; por eso empieza en 0 agentes.
- **Ni nivel 3 ni un Workflow sin el sí del usuario** ([T-7], [T-16]), **ni un presupuesto ampliado a mitad de camino sin decirlo.** Si el trabajo se desborda, parar y reportar lo que hay. Nunca un Workflow para explorar ni para revisar el plan.
- **Nunca fundir medido con razonado**, ni en el plan ni en el chat ([T-13]). Un número de un agente sin el comando que lo produjo es una opinión.
- **Antes de cada medición** (`php`, `curl`, `python3`, una consulta), una línea con el comando y el entorno contra el que va (local, staging o producción). Si no es local o toca una base de datos, esperar a que el usuario lo confirme: el `CLAUDE.md` del proyecto dice a qué apunta cada entorno, y en alguno la BD «local» es la de producción. En auto mode no aparece el aviso de permiso, así que esta línea es el punto de control.
- **Un coste externo o una escritura irreversible** (API de pago, borrados, buckets, BD de producción, SQL que lanza el usuario) va en la Ejecución del plan con su punto de confirmación: aprobar el plan no autoriza un gasto que no estaba escrito en él.
- **Nunca proponer código nuevo** sin la búsqueda de reuso (Paso 3) y el Reuse inventory (Paso 4). Nunca pseudocódigo largo: referenciar archivos y líneas. Siempre los `#N` de review que aplican, sin copiar su texto.

## Paso 0: Ruta y perfil

Antes de leer código, clasificar la petición y escribir la línea de ruta. Una petición compuesta lleva una línea por parte.

| ruta | señal | qué hacer |
|---|---|---|
| **A — alcance claro** | se sabe qué tocar y por qué: campo, filtro, columna, rename, endpoint calcado de otro, contrato de API pegado, «como en X» | Paso 1 directamente, sin acotar |
| **B — síntoma** | «tarda X», «lento», «optimiza», «falla a veces», «no aparece», «no funciona», un error o un log pegado | Acotar con la disciplina de medición, y Paso 1 si merece la pena |
| **C — decisión** | «¿merece la pena?», «¿se puede borrar?», «¿aplica en otros sitios?», «¿cuál de las dos?», «la mejor solución», «primero entiende…», un barrido («detecta y enumera», «revisa todo») | Acotar: la comprobación descalificante es lo único que importa. Paso 1 si la petición pide hacer algo; si solo pregunta, responder y ofrecer el plan en una línea |
| **Pull** | pull, merge o revisar la rama de otro | Sin plan ni plan mode: una línea y proponer `/desa:review` del diff, sin Workflow, empezando por los ficheros que tocan las dos ramas, las migraciones y las columnas nuevas. Fin de esa parte; las demás siguen su ruta |
| **Freno** | la petición es sobre el trabajo en curso («se te va la olla», «¿te estás pasando?», «cómo vas» repetido) | Leer `acotar.md`, parar lo que sigue corriendo salvo que su resultado decida algo que se pueda nombrar ([T-19]) y acotar lo que queda: premio, comprobación descalificante y presupuesto. Cerrar con la salida de una página (declarado frente a gastado y lo que aportó) y terminar el turno sin relanzar nada. «Premio: 0» es una salida válida |

En la duda entre A y B o C, B o C en nivel 1. Una petición compuesta comparte el tope del perfil mayor. Si la exploración del Paso 3 destapa un síntoma o una decisión sin resolver, volver a acotar con el presupuesto que quede; si entonces no merece la pena, la salida de una página va como plan file, con «nada que implementar» en la primera línea, y se cierra con `ExitPlanMode` para no dejar la sesión en plan mode. **Atajo en B**: con la causa a la vista (un stack trace con `fichero:línea`, o la hipótesis del usuario que se comprueba leyendo), comprobarla con Read y Grep es la comprobación descalificante; si se confirma, Paso 1 con el perfil S y la plantilla corta.

**[T-1] Un tipo A no lleva ceremonia.** Si esta skill añade los pasos de acotar a un cambio de una línea, es el mismo desperdicio que pretende evitar, con otro disfraz. La línea de ruta y el plan son el resultado correcto y frecuente: el ~80 % de las peticiones de plan son A.

Y elegir el perfil, que fija a la vez el tope de agentes de toda la tarea y con qué conviene implementar:

| perfil | señales | agentes (tope total) | implementar con |
|---|---|---|---|
| **S** | A de 1-3 ficheros (CSS, columna, filtro, texto, un campo); error pegado con `fichero:línea`; C que se responde con un Grep («¿se usa?», «¿se puede borrar?»); «sencillo», «no te mates» | 0 | Sonnet 5.5 · medium, high si toca lógica |
| **M** | un endpoint o un componente con un patrón a la vista; back y front de un campo con el contrato pegado; un error o un fallo con un caso reproducible | 0-1 Explore | Sonnet 5.5 · high; Opus 5.5 · high si toca algo de lo que cuelga todo (precios, pedidos) |
| **L** | C entre opciones, de diseño o de comprensión de un sistema; rendimiento («tarda», «lento») que hay que medir; cambio transversal; riesgo declarado («bestia», «no la podemos liar», producción); coste externo o escritura irreversible | ≤3, como mucho 1 adversario | Opus 5.5 · xhigh, en solo |
| **XL** | auditoría o barrido de un universo enumerable; fallo solo en producción, asíncrono o intermitente, con la primera hipótesis ya caída; el usuario pide un workflow | ≤8, o lo que apruebe el usuario ([T-7]) | Opus 5.5 · xhigh; Workflow solo para lo paralelizable, con los lectores en Sonnet |

Coste por token frente a Sonnet 5.5: Haiku 4.5 0,5×, Opus 5.5 2×, Fable 5.1 5×. Pesa más el número de agentes: en sesiones cortas parecidas, mediana de $14 con Workflow frente a $2,3 en solo. Sonnet 5.5 habría bastado en ~40 de 67 tareas acotadas. **Fable 5.1**, solo si el usuario lo pide; **Haiku 4.5**, solo como lector mecánico; **max**, nunca por defecto.

**[T-21] El perfil sale de señales que se pueden señalar, no de la impresión de dificultad.** La línea nombra la señal. «Bestia» o «en producción» suben como mínimo a L; «sencillo» o «no te mates» lo dejan en S, salvo que la comprobación descalificante diga otra cosa. En la muestra lanzaron agentes 3 de 12 peticiones marcadas como difíciles y 5 de 13 marcadas como fáciles. En la duda, el perfil menor: subir cuesta una línea, y bajar después de lanzar no devuelve lo gastado.

La línea, igual en todas las rutas (en A no lleva nada más; en B, C y Freno la sigue acotar):

```
**Ruta {A|B|C|Freno} · Perfil {S|M|L|XL}** — {la señal que lo decide}. {modelo · esfuerzo}, {N} agentes{. Sesión en {modelo}: {basta con {modelo} | cambiar con {orden}}}
```

En L o XL con la sesión por debajo del perfil (Sonnet o Haiku cuando pide Opus), terminar el turno tras la línea con la orden para cambiarlo (`/model opus`) y, si hace falta, la pregunta de [T-7] en el mismo mensaje: una sola parada. Planificar un «bestia» en Sonnet es lo que se quiere evitar. Sin nadie que responda, seguir y decirlo. En S y M no se para por el modelo: si la sesión va sobrada, la línea dice con qué bastaría y se sigue.

## Presupuesto y agentes (todas las rutas)

| nivel | tope | cuándo |
|---|---|---|
| **1 — directo** | 0 agentes, ≤5 min | lectura, Grep, 1-3 mediciones. Por defecto en todas las rutas |
| **2 — acotado** | ≤3 agentes en total, ~10 min | el ancho es el cuello de botella de verdad: varios dominios o ficheros sin relación |
| **3 — fan-out** | ≤8 agentes en total, con veto del usuario | perfil XL, tras la comprobación descalificante y con el premio ya cuantificado (en A, el propio cambio) |

Antes de pasar del nivel 1, una línea visible: `Presupuesto: {N} agentes · ~{M} min · {K} mediciones. Nivel {2|3}.`

**[T-4] La comprobación descalificante va siempre delante del trabajo ancho.** Ordenar barato → caro no es una preferencia de estilo: es lo único que evita pagar el análisis de algo ya muerto.

**[T-5] El tope es el total, no el de cada rama.** Un `slice(0, 6)` sobre 4 ramas son 24 agentes. Contar el producto, no el factor, y también los que lance un subagente. Acotar, explorar e implementar comparten un solo tope: un plan que viene de acotar empieza el Paso 3 con lo que quede, no con un tope nuevo.

**[T-6] Un adversario vale más que seis confirmadores.** Para validar una conclusión, un agente que busque el contraejemplo bate a N que la comprueben: los N convergen en lo mismo y no aportan información nueva. Un plan tampoco se valida con rondas de agentes: se contrasta con los criterios en el Paso 5, en primera persona.

**[T-7] Nivel 3 se pide, no se toma.** Si el presupuesto pasa de ~10 min o de 3 agentes, decirlo y esperar: terminar el turno con la línea de presupuesto y la pregunta (o usar AskUserQuestion si está disponible), sin lanzar agentes hasta la respuesta. Declarar el presupuesto no es pedir permiso. El usuario es quien decide si el premio lo justifica; sin ese punto de veto, el descubrimiento de que sobraba llega cuando ya se pagó. Si no hay nadie que responda (`claude -p`, un subagente, un workflow), no escalar: quedarse en nivel 2 y decir en la salida que haría falta el 3.

**[T-16] Ultracode activo no es el sí de [T-7].** El modo pide un Workflow en cada tarea sustancial sin saber lo que vale esta; el presupuesto de esta skill sí lo sabe, y es el que manda. Por eso la skill registra dos hooks que, desde que se invoca y hasta el final de la sesión, piden confirmación antes de cada Workflow y a partir del cuarto agente, también en auto mode. Si el usuario ya dio el sí en el chat, la confirmación se repite: es el precio de que no dependa de la prosa. Precedente: cuatro sesiones en que se reconoció haberse saltado el presupuesto, una anunciando 27 agentes y lanzándolos en el mismo turno.

**[T-17] El presupuesto declarado vale para toda la tarea, no para el turno.** El último de la sesión (el de acotar o el de la Ejecución del plan aprobado) rige los turnos siguientes de la misma tarea aunque no se invoque la skill. Subirlo es volver a pedir el sí. Precedente: en 9 de 13 sesiones con triage hubo workflows después, uno de 9 agentes justo tras un triage de 0.

**[T-18] Una dimensión por capa o por pregunta, y sin las pistas del líder.** Siete lectores sobre el mismo sistema son siete veces la misma lectura: 161 hallazgos para 33 carencias únicas. A cada agente, la pregunta y no la respuesta esperada.

**[T-19] Con la conclusión confirmada, lo que sigue corriendo sobra.** Pararlo con `TaskStop` y decirlo. Tres veces la causa ya estaba confirmada leyendo mientras 38, 56 y 139 agentes seguían.

**Encargo de cada agente.** Un subagente no ve esta skill: lo que no se le pida no lo hará. El encargo lleva la pregunta concreta y la regla de paro; qué devolver (rutas con `fichero:línea`, y cada número con el comando que lo produjo y su salida); el tipo `Explore`, que no tiene Edit, Write ni la herramienta de agentes; y `model: "sonnet"`, porque leer y devolver rutas no necesita el modelo de la sesión, que es el que heredan si no se dice. El juicio se queda en el agente principal, y el adversario de [T-6] recibe la conclusión y los datos, no el razonamiento. En un Workflow aprobado, cada `agent()` lleva su `model` y, en las etapas mecánicas, `effort: 'low'`.

## Acotar (rutas B, C y Freno)

Leer `${CLAUDE_PLUGIN_ROOT}/references/acotar.md` antes de la primera medición o agente, y seguirlo. En resumen:

1. **Premio** en una línea, con unidad: ms, consultas, filas, € o «no lo sé». No se analiza lo que no se ha dimensionado ([T-2]): con «no lo sé», nivel 1 y preguntar. Un premio pequeño cierra el asunto ([T-3]).
2. **Comprobación descalificante**: la pregunta más barata cuya respuesta haría irrelevante el resto, respondida en solo antes de nada ([T-4]). Lo que sabe el usuario va primero ([T-20]): su hipótesis es la primera que se comprueba, y si la evidencia la tiene él (logs, rol, payload, qué está desplegado), pedirla cuesta menos que buscarla.
3. **Presupuesto**, con la tabla de arriba. No editar ficheros que un barrido está leyendo ([T-8]).
4. **Solo B: medir, nunca restar** ([T-9]), en la capa correcta ([T-10]), A/B en el mismo proceso con control ([T-11]); tres hipótesis refutadas en la misma capa piden cambiar de capa ([T-12]).
5. **Medido separado de razonado** ([T-13]), con el camino infeliz probado antes de proponer ([T-14]).
6. **Regla de paro**, declarada antes de empezar y cumplida. Un negativo bien medido es un entregable ([T-15]).
7. **Veredicto.** Si merece la pena y la petición pide hacer algo: dos líneas en el chat (veredicto y el número que lo decide) y Paso 1 en la misma invocación, con el premio, lo medido, lo descartado y la regla de paro en el Context del plan; lo descartado no se vuelve a explorar. Si solo era una pregunta: responderla, con lo medido separado de lo razonado, y ofrecer el plan en una línea. Si no merece la pena, está bloqueado o es un Freno: la salida de una página de `acotar.md`, con el presupuesto que queda vigente ([T-17]), y terminar.

Si la invocación ya trae «Medido», «Descartado» o «Regla de paro» de un análisis anterior, no repetirlo: llevarlo al Context y pasar al Paso 1.

## Paso 1: Detectar tipo de proyecto

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh --repo
```

- `REPO=backend` → backend.
- `REPO=websites` → websites.
- `REPO=monorepo` → frontend, mobile o los dos según la tarea (`APPS` dice qué apps existen). `apps/mobile/` es mobile y el resto (`apps/web/`, `packages/`) frontend, igual que en `/desa:review`: una tarea de mobile que añade un hook en `packages/core` lleva los dos ficheros de criterios, el de frontend y el de mobile. Si la petición no lo deja claro, cargar los dos en el Paso 2 y quedarse con los que correspondan al redactar el borrador, cuando la exploración lo aclare.
- `REPO=unknown` o `ERROR` → informar al usuario y terminar.

El tipo sale del repositorio y de la tarea, no del diff: al planificar, los cambios de la tarea aún no existen y lo que haya en el árbol es otro trabajo.

## Paso 2: Cargar contexto fijo

- `CLAUDE.md` del proyecto e índice de memoria: si ya están en contexto, aplicarlos sin releerlos. Si no, porque la sesión se abrió en otro directorio o la memoria automática está desactivada, leer el `CLAUDE.md` del proyecto y `~/.claude/projects/{project-path}/memory/MEMORY.md`. Leer además las notas de memoria cuyo título sea del dominio de la tarea.
- Los criterios de `/desa:review` del tipo detectado, en paralelo desde `${CLAUDE_PLUGIN_ROOT}/references/`: `criterios-compartidos.md` siempre, más `criterios-backend.md`, `criterios-frontend.md`, `criterios-mobile.md` o `criterios-websites.md`.

## Paso 3: Explorar

Empezar por Read y Grep: el patrón de referencia del dominio y lo que se puede reusar. En la ruta A es la comprobación descalificante: si lo que se pide ya existe, el plan es reusarlo. Si viene de acotar, lo cerrado no se vuelve a explorar y los agentes ya gastados cuentan para el tope ([T-5]).

- **Por defecto, 0 agentes** (perfiles S y M, y todo lo que venga de acotar): rename, campo, filtro, columna, un endpoint o un componente con un patrón de referencia a la vista, también con un contrato de API pegado.
- **1 Explore** si la tarea cruza un dominio que el Grep no ha resuelto.
- **Hasta 3 Explore en paralelo** (un solo mensaje, varias llamadas) solo en L o XL, con dominios sin relación entre sí y con la línea de presupuesto. Un foco cada uno, sin solaparse ([T-18]):
  1. **Patrones existentes en el dominio**: ficheros del mismo dominio o similar que sirvan de referencia.
  2. **Reutilizables**: `packages/core/src/hooks`, `app/Services`, `app/Models`, `app/Http/Resources` (en websites, `src/hooks`, `src/lib`, `src/api/services`).
  3. **Tests y casos límite**: tests existentes de código similar.

Cada agente devuelve **rutas exactas con números de línea**, no descripciones vagas. Nunca un Workflow para explorar ni para revisar el plan: los A pequeños que lo lanzaron (un scroll, una línea de CSS) tardaron 15-29 min y costaron 3-4 veces más que sus equivalentes en solo, con el mismo resultado.

## Paso 4: Borrador del plan

Redactar un borrador, que todavía no se enseña al usuario, con:

- **Reuse inventory**: lista de funciones/hooks/componentes/servicios existentes que se van a reusar, con `file_path:line`.
  - Si la lista está vacía en una tarea no trivial, reintentar la búsqueda antes de seguir. La causa #1 de mala planificación es reinventar lo que ya existe.
- **Archivos a modificar**: rutas exactas.
- **Archivos a crear**: solo si son imprescindibles; justificar por qué no se puede reusar algo existente.
- **Cambios clave por archivo**: 1–3 líneas por archivo, sin pseudocódigo extenso.
- **Supuestos sin comprobar**: lo que el plan da por cierto sin haberlo visto en el código (p. ej. «el Service ya filtra por rol»), y qué lo confirmaría.

Al redactar cada cambio, tener en cuenta:

- **Caminos infelices** que apliquen a ese cambio: estado vacío o nulo, errores esperados, permisos y roles, concurrencia, datos existentes que puedan romper al aplicarlo. En backend, además, entidades con soft-delete y transacciones completas con try/catch. En el plan se anotan solo los que apliquen; en B y C, probados antes de proponer ([T-14]).
- **Simplificación**: nada de abstracciones que no hagan falta, wrappers triviales, configurabilidad sobrante, soluciones «clever» ni pasos «para el futuro» (#9). Si se puede borrar código en vez de añadir, o reusar más de lo inventariado, hacerlo.

## Paso 5: Comprobar contra los criterios de review

Para cada archivo planificado, comprobar las reglas cargadas en el Paso 2 que le apliquen; los ejemplos típicos de cada tipo están en el anexo, al final. Si el borrador viola alguna, corregirlo.

## Paso 6: Ejecución

Confirmar el perfil del Paso 0 con lo que ha enseñado la exploración, o cambiarlo diciendo por qué. Si sube a nivel 3 o pide un Workflow, es volver a pedir el sí ([T-7]).

Esta skill **no puede** cambiar el modelo ni el esfuerzo de la sesión: `/model` y `/effort` son del usuario, `model` y `effort` en el frontmatter valdrían solo para este turno e igual para cualquier tarea, y la herramienta del escritorio que cambia el modelo rechaza la propia sesión. En su lugar:

- **Recomienda** con la señal, el coste y la orden exacta (`/model sonnet`, `/model opus`, `/effort high`, `/effort xhigh`), en una línea antes de `ExitPlanMode`. El cambio vale desde el siguiente mensaje del usuario, no a mitad de este turno. Para quien trabaje siempre así, `/model opusplan`: Opus en plan mode y Sonnet fuera de él.
- **Ultracode**: si está activo y el perfil no es XL, añade `/effort ultracode off`. Su recordatorio empuja a orquestar en cada turno, y estaba encendido en el 93 % de las sesiones con plan o triage.
- **Fija** el tope de agentes de la implementación ([T-17]) y el modelo de cada subagente (Encargo).
- En endurecimiento de seguridad (brechas, scopes, permisos), avisa de que los safeguards de Opus 5.5 cortaron respuestas en dos tareas así; la alternativa es Sonnet 5.5, sin medir que lo evite.

## Paso 7: Escribir plan file

Escribir el plan consolidado en la ruta que el sistema de plan mode haya asignado (el entorno la indica en el system reminder, p. ej. `/Users/.../.claude/plans/{name}.md`). Estructura:

```markdown
# Plan — {resumen corto de la tarea}

## Context
{por qué se hace esta tarea, qué problema resuelve, resultado esperado}
{si viene de acotar, en esta invocación o en una anterior: premio, «Medido» (número y cómo), «Descartado» (no volver a explorarlo) y regla de paro. Si no están en contexto, decirlo, sin reconstruirlos}

## Ejecución
- Ruta {A|B|C} · Perfil {S|M|L|XL} — {señal}
- {modelo · esfuerzo} — {por qué}; coste ~{N}× frente a Sonnet en solo. {si no es el de la sesión: la orden}
- Agentes: {0 | N y para qué} · Workflow: {no | aprobado: N agentes · ~M min}. Vale hasta terminar la implementación [T-17]
- Confirmaciones: {coste externo o escritura irreversible, y cuándo se pide el sí | ninguna}

## Reuse inventory
- `file_path:line` — qué función/hook/componente/servicio y cómo se usa

## Archivos a modificar
- `path/exact.ext` — qué cambia (1-3 líneas)

## Archivos a crear (solo si imprescindible)
- `path/exact.ext` — justificación de por qué no existe ya algo reusable

## Cambios clave
{descripción del approach, sin pseudocódigo extenso}

## Supuestos sin comprobar
- {supuesto} — qué lo confirmaría

## Verificación
- Cómo probar end-to-end (comandos, rutas UI, tests a correr)
- Edge cases específicos a validar manualmente

## Reglas aplicadas
Lista de los #N de los criterios de `/desa:review` (`references/criterios-*.md`) más relevantes que el plan ya respeta (trazabilidad), y los [T-N] que han decidido la ruta o el presupuesto.
```

En perfil S, plantilla corta: Context en una o dos líneas, Ejecución, Reuse inventory, Archivos a modificar, Verificación y Reglas aplicadas.

## Paso 8: Salir con ExitPlanMode

Llamar a `ExitPlanMode` para que el usuario apruebe antes de implementar. Al aprobar el plan se aprueba también su Ejecución, con el tope de agentes ([T-17]). Si la Ejecución pide un modelo por encima del de la sesión, tras la aprobación no implementar: terminar el turno con la orden para cambiarlo, porque el cambio solo vale desde el siguiente mensaje, y seguir cuando el usuario responda.

## Anexo: ejemplos de criterios por tipo

**Backend**: whitelist de roles (#13, #33), `entityQuery()` al inicio de `query()` (#27), transacción + try/catch (#22), `event()`/`broadcast()` después de `commit()` (#23), `withTrashed()` en morphTo/belongsTo a soft-deletable (#30), Resource con `addEntityRelations` (#20), controller ultra-thin (#26), audit trail en save (#28), guardia de estado en save/delete (#29), convenciones HTTP (#31), naming de Events (#32).

**Frontend**: `useCustomNavigate` no `useNavigate` (#58), `memo()` + `useCallback` en `*TableBody` y filas (#54, #59), `useTable`/`useFilter` para listados (#60), `i18next.t()` nunca a nivel módulo (#69), no `fal` (solo `fasr`/`fass`) (#49), `ActionTypography` para códigos copiables (#50), API `include` siempre plano (#74), `TextNumericFormat` para números (#75), `import * as XService` (#55), `useDisplayColumn` para columnas opcionales (#61), `hasRole(..., false)` para portal exclusivo (#64).

**Mobile**: `useTheme()` no `StyleSheet.create` (#65), reuso de `packages/core` antes de reimplementar (#82), screens sin lógica de componentes (#83), naming de theme = componente RN (#84, #85).

**Websites**: `LocaleLink` en Client Components y `localePath()` en Server Components (#98), imports directos de MUI (#99), Server Components por defecto (#100), desestructurar `.data` y comprobar `null` (#101), `fetch` solo vía `api.js` (#102), ISR con las constantes `REVALIDATE` (#103), lógica testable fuera de los Server Components async (#104), `i18next.t()` nunca a nivel módulo (#97).
