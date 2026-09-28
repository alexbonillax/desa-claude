---
description: Acotar una tarea antes de invertir esfuerzo en ella, dimensionando el premio y declarando el presupuesto antes de gastarlo
argument-hint: [descripción de la tarea, pregunta de decisión o síntoma]
allowed-tools: Read, Grep, Glob, Agent
---

# Triage — Acotar una tarea antes de trabajar en ella

Primera skill de una sesión. Convierte una petición en una decisión acotada: **qué merece esfuerzo, en qué orden, con qué presupuesto y cuándo parar**. No planifica (eso es `/desa:plan`) y no implementa.

Existe porque el fallo caro no es analizar mal, es **analizar mucho lo que no lo merecía**. Todas las reglas de aquí salen de fallos reales, y están numeradas `[T-N]` para poder citarlas.

Si `$ARGUMENTS` está vacío, pedir la petición al usuario y terminar.

## Paso 1: Clasificar y, si procede, SALIR YA

Antes de cualquier otra cosa, clasificar `$ARGUMENTS`:

| tipo | señal | qué hacer |
|---|---|---|
| **A — implementación de alcance claro** | se sabe qué tocar y por qué; rename, campo nuevo, endpoint calcado de otro | **Triage de 3 líneas** y encaminar a `/desa:plan`. NO ejecutar los pasos 3-7 |
| **B — síntoma** | «tarda X», «falla a veces», «no aparece» | Pasos 2-7 completos. La disciplina de medición es obligatoria |
| **C — decisión** | «¿merece la pena?», «¿aplica en otros sitios?», «¿cuál de estas dos?» | Pasos 2-4 y 6-7. La comprobación descalificante es lo único que importa |

**[T-1] Un tipo A no lleva ceremonia.** Si esta skill añade seis pasos a un cambio de una línea, es el mismo desperdicio que pretende evitar, con otro disfraz. Salir en tres líneas es el resultado correcto y frecuente.

## Paso 2: El premio, antes del análisis

Escribir en **una línea** cuánto vale esto si sale perfecto, con la unidad explícita: ms, consultas, filas, € o «no lo sé».

**[T-2] No se analiza lo que no se ha dimensionado.** Si el premio no se puede acotar ni con un orden de magnitud, eso es el hallazgo: decirlo y preguntar, en vez de investigar a ciegas.

**[T-3] Un premio que sale «pequeño» cierra el asunto.** Es un resultado, no un fracaso. Preferible en el minuto 2 que en el 40.

## Paso 3: La comprobación descalificante

Escribir la pregunta más barata cuya respuesta haría **irrelevante todo lo demás**, y responderla antes de nada.

Ejemplos reales de las que valieron una tarde cada una:

- *¿la consulta lleva `with(...)`?* — 18 candidatas de un refactor, 16 descartadas en 30 s: el ahorro nunca fue la hidratación, eran los eager loads
- *¿qué índice elige el plan?* — un `EXPLAIN` antes de teorizar sobre por qué una consulta es lenta
- *¿el endpoint devuelve 200?* — tres peticiones con un `<token>` literal daban 401 y se leyeron como «endpoint rápido»
- *¿este valor es una columna o un accesor?* — sumar un accesor sobre `stdClass` devuelve **0 en silencio**
- *¿este código se llega a ejecutar?* — una rama `never executed` en el plan de consulta

**[T-4] La comprobación descalificante va SIEMPRE delante del trabajo ancho.** Ordenar barato → caro no es una preferencia de estilo: es lo único que evita pagar el análisis de algo ya muerto.

## Paso 4: Presupuesto declarado

Antes de gastar, escribir **una línea visible** con el coste previsto y esperar si supera el nivel 1:

```
Presupuesto: {N} agentes · ~{M} min · {K} mediciones. Nivel {1|2|3}.
```

| nivel | tope | cuándo |
|---|---|---|
| **1 — directo** | 0 agentes, ≤5 min | lectura, grep, 1-3 mediciones. Por defecto |
| **2 — acotado** | ≤3 agentes en total, ~10 min | el ancho es el cuello de botella de verdad: varios dominios o ficheros sin relación |
| **3 — fan-out** | ≤8 agentes en total, con veto del usuario | sólo tras el Paso 3 y con el premio del Paso 2 ya cuantificado |

**[T-5] El tope es TOTAL, no por rama.** Un `slice(0, 6)` sobre 4 ramas son 24 agentes. Contar el producto, no el factor.

**[T-6] Un adversario vale más que seis confirmadores.** Para validar una conclusión, un agente que busque el contraejemplo bate a N que la comprueben. Los N convergen en lo mismo y no aportan información nueva.

**[T-7] Nivel 3 se pide, no se toma.** Si el presupuesto pasa de ~10 min o de 3 agentes, decirlo y esperar. El usuario es quien decide si el premio lo justifica; sin ese punto de veto, el descubrimiento de que sobraba llega cuando ya se pagó.

**[T-8] No editar ficheros que un barrido está leyendo.** Si hay agentes recorriendo el árbol, un edit invalida su resultado en silencio. Medir sin editar (construir las dos variantes en el mismo proceso) o esperar.

Las mediciones (`php`, `curl`, `python3`, consultas a BD) no están preaprobadas, pero no hay que contar con el aviso de permiso: en auto mode no aparece. Antes de cada medición, escribir en una línea el comando y el entorno contra el que va (local, staging o producción). Si no es local o toca una base de datos, esperar a que el usuario lo confirme: el `CLAUDE.md` del proyecto dice a qué apunta cada entorno, y en alguno la BD «local» es la de producción.

## Paso 5: Medir, nunca restar

Sólo para el tipo B. Es la sección que más veces se ha incumplido.

**[T-9] Prohibido presentar una resta como medición.** «El total menos la latencia media» no es un dato. Medir el tiempo del lado del servidor:

- BD → `EXPLAIN ANALYZE` (inmune a la red)
- HTTP → `ttfb − tls` de `curl -w`
- capas → aislar por códigos: 404 (routing) → 401 (auth) → 200 (controlador)
- trabajo de ida y vuelta → **número de consultas**, que es determinista, en vez de ms

**[T-10] Comprobar que se mide la capa correcta.** `php -i` informa del SAPI de **CLI**, no del de FPM. Antes de concluir, verificar que el instrumento observa el proceso que sirve la petición.

**[T-11] A/B en el mismo proceso y el mismo instante, con control.** Comparar dos ejecuciones separadas no distingue la mejora del ruido. Y medir en la misma ventana algo **no tocado** como control: si el control también ha bajado, la mejora no es tuya.

**[T-12] Tres hipótesis refutadas en la misma capa significan que la capa es la equivocada.** No es mala suerte ni falta de profundidad: es la señal de cambiar de capa o de pedir otro instrumento (un slow log, una traza). Seguir insistiendo es el patrón que quema tardes.

## Paso 6: Separar medido de razonado

La salida lleva las dos cosas, **nunca fundidas**:

| hallazgo | medido | razonado |
|---|---|---|
| ... | número + cómo se obtuvo | hipótesis + qué la confirmaría |

**[T-13] Una ganancia prevista se enuncia como previsión, con su aritmética a la vista.** «18 round trips menos; a ~26 ms de RTT serían ~470 ms, sin medir» es honesto. «Ahorra 470 ms» no lo es. Precedentes: 827→663 predichos contra 795→773 reales, y un «vale ~190 ms» que valía 0.

**[T-14] Probar el camino infeliz antes de proponer.** Sin filtros, sin includes, con cero filas, con el principal más restringido. Un diseño validado sólo en el camino feliz llevaba un **500** dentro.

## Paso 7: Regla de paro

Declararla antes de empezar: **qué resultado concreto hace abandonar**. Y cumplirla.

**[T-15] Un resultado negativo bien medido es un entregable.** «Los 18 sitios no ganan nada, y este es el motivo» cierra el tema para siempre y merece anotarse igual que un arreglo.

## Paso 8: Salida — una página, y encaminar

```
## Triage — {petición en una línea}

**Tipo**: {A|B|C}   **Premio**: {valor + unidad, o «no acotable»}
**Comprobación descalificante**: {pregunta} → {respuesta}
**Presupuesto gastado**: {N agentes · M min · K mediciones}

### Medido
| hallazgo | número | cómo |

### Razonado (sin medir)
| hipótesis | qué la confirmaría |

### Descartado
- {qué} — {por qué, con el dato}

### Regla de paro
{qué hará abandonar, o qué la activó}

### Recomendación
{una de: `/desa:plan` · arreglo directo aquí · no vale la pena · hace falta {instrumento/dato} }
```

Encaminar explícitamente:

- **`/desa:plan`** — merece la pena y hay que planificarlo
- **arreglo directo** — una o dos líneas con el premio ya medido; proponer el diff, no planificar
- **no vale la pena** — con el número que lo demuestra
- **bloqueado** — falta un instrumento o una decisión de negocio; decir exactamente cuál

## Reglas estrictas

- **Nunca implementar.** Esta skill acota y encamina. El código va por `/desa:plan` o por un arreglo directo aprobado.
- **Nunca gastar nivel 2 o 3 sin haber escrito antes el premio (Paso 2) y la comprobación descalificante (Paso 3).**
- **Nunca ampliar el presupuesto a mitad de camino sin decirlo.** Si el análisis se desborda, parar y reportar lo que hay.
- **Nunca fundir medido con razonado**, ni en la salida ni en el mensaje al usuario.
- **Nunca dar por buena una medición de un agente sin el cómo.** Un número sin instrumento es una opinión.
- **Siempre leer `CLAUDE.md` y el `MEMORY.md` del proyecto antes del Paso 3**: la comprobación descalificante suele estar ya escrita ahí, y los instrumentos y trampas concretos de cada proyecto (comandos destructivos, cómo correr tests sin tocar producción, gotchas de medición) viven ahí, no aquí.
- **Si al terminar el triage el premio medido es cero o cerca**, decirlo en la primera línea de la respuesta, no al final.
