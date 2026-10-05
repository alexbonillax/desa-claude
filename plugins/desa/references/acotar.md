# Acotar — rutas B y C de /desa:plan

Lo lee `/desa:plan` en las rutas B (síntoma), C (decisión) y Freno antes de la primera medición o agente. Es lo que fue `/desa:triage` hasta la 1.18.2, con los mismos `[T-N]`: convierte la petición en una decisión acotada, **qué merece esfuerzo, en qué orden, con qué presupuesto y cuándo parar**. La ruta, el perfil, la tabla de niveles y las reglas [T-1], [T-4] a [T-7], [T-16] a [T-19] y [T-21] están en `plan.md`; aquí va el resto.

Orden: premio → comprobación descalificante → presupuesto → (solo B) medir → medido frente a razonado → regla de paro → veredicto. En C se salta la medición. En Freno, primero se para lo que ya no decide nada ([T-19]) y se acota lo que queda.

## 1. El premio, antes del análisis

Escribir en **una línea** cuánto vale esto si sale perfecto, con la unidad explícita: ms, consultas, filas, € o «no lo sé».

**[T-2] No se analiza lo que no se ha dimensionado.** Si el premio no se puede acotar ni con un orden de magnitud, eso es el hallazgo: decirlo y preguntar, en vez de investigar a ciegas. Mientras tanto, nivel 1.

**[T-3] Un premio que sale «pequeño» cierra el asunto.** Es un resultado, no un fracaso. Preferible en el minuto 2 que en el 40.

## 2. La comprobación descalificante

Escribir la pregunta más barata cuya respuesta haría **irrelevante todo lo demás**, y responderla en solo antes de nada ([T-4]): delegarla en un agente es saltársela.

Suele estar ya escrita en el `CLAUDE.md` del proyecto o en su memoria, junto con los instrumentos y las trampas de ese proyecto (comandos destructivos, cómo correr tests sin tocar producción, gotchas de medición), que no se repiten aquí. Si ya están en contexto, consultarlos ahí; si no, leer el `CLAUDE.md` del proyecto y `~/.claude/projects/{project-path}/memory/MEMORY.md`, y abrir los ficheros de tema que enlace el índice si son del dominio de la petición.

**[T-20] Lo que sabe el usuario va primero.** Si trae una hipótesis («es muy probable que…», «creo que es…»), es la primera que se comprueba, en solo. Si la evidencia la tiene él (logs del servidor, configuración de nginx, rol del usuario afectado, payload real, qué está desplegado), pedirla cuesta menos que buscarla. Precedentes: «es muy probable que el Valor sea 0» era la causa, con un Workflow a punto de salir; un Workflow de 16 agentes dio un diagnóstico que se descartó, y la causa salió de los logs del usuario.

Ejemplos reales de las que valieron una tarde cada una:

- *¿la consulta lleva `with(...)`?* — 18 candidatas de un refactor, 16 descartadas en 30 s: el ahorro nunca fue la hidratación, eran los eager loads
- *¿qué índice elige el plan?* — un `EXPLAIN` antes de teorizar sobre por qué una consulta es lenta
- *¿el endpoint devuelve 200?* — tres peticiones con un `<token>` literal daban 401 y se leyeron como «endpoint rápido»
- *¿este valor es una columna o un accesor?* — sumar un accesor sobre `stdClass` devuelve **0 en silencio**
- *¿este código se llega a ejecutar?* — una rama `never executed` en el plan de consulta

## 3. Presupuesto

La tabla de niveles y la línea `Presupuesto:` están en `plan.md`. Lo que solo aplica al acotar:

**[T-8] No editar ficheros que un barrido está leyendo.** Si hay agentes recorriendo el árbol, un edit invalida su resultado en silencio. Medir sin editar (construir las dos variantes en el mismo proceso) o esperar.

Además del encargo de `plan.md`, el agente de un acotar solo mide en local y sin tocar una base de datos: `Explore` tiene Bash y no puede pedir la confirmación que exige `plan.md` antes de cada medición, así que cualquier otra medición la devuelve como comando propuesto, con su entorno, y la lanza el agente principal cuando el usuario la confirme. Si es un `EXPLAIN ANALYZE`, recordarle que ejecuta la sentencia de verdad (abajo).

## 4. Medir, nunca restar (solo B)

Es la sección que más veces se ha incumplido.

**[T-9] Prohibido presentar una resta como medición.** «El total menos la latencia media» no es un dato. Medir el tiempo del lado del servidor:

- BD → `EXPLAIN ANALYZE` (inmune a la red). Ojo: **ejecuta la sentencia de verdad**. Si basta con el plan, `EXPLAIN` a secas. Sobre una escritura, solo dentro de `BEGIN … ROLLBACK`, que ni así deshace las secuencias ni el DDL de MySQL. Contra producción, una consulta pesada se paga entera
- HTTP → tiempo de servidor ≈ `%{time_starttransfer}` − `%{time_pretransfer}` de `curl -w`; en remoto aún incluye 1 RTT, que se cancela en el A/B de [T-11]. No usar `%{time_appconnect}`: sin TLS vale 0. Si la respuesta trae `Server-Timing`, mejor esa. Imprimir `%{http_code}` en cada muestra: una sola con un código distinto del esperado (2xx, salvo al aislar capas) invalida la medición. Si el endpoint escribe (POST, PUT, DELETE), cada muestra escribe: decirlo en la línea de la medición, con el entorno
- capas → aislar por códigos: 404 (routing) → 401 (auth) → 200 (controlador)
- trabajo de ida y vuelta → **número de consultas**, que es determinista, en vez de ms
- frontend → número de peticiones y de renders, también deterministas, con la herramienta que indique el `CLAUDE.md` del proyecto

**[T-10] Comprobar que se mide la capa correcta.** `php -i` informa del SAPI de **CLI**, no del de FPM. Antes de concluir, verificar que el instrumento observa el proceso que sirve la petición.

**[T-11] A/B en el mismo proceso y el mismo instante, con control.** Comparar dos ejecuciones separadas no distingue la mejora del ruido. Y medir en la misma ventana algo **no tocado** como control: si el control también ha bajado, la mejora no es tuya.

**[T-12] Tres hipótesis refutadas en la misma capa significan que la capa es la equivocada.** No es mala suerte ni falta de profundidad: es la señal de cambiar de capa o de pedir otro instrumento (un slow log, una traza). Seguir insistiendo es el patrón que quema tardes.

## 5. Separar medido de razonado

La salida lleva las dos cosas, **nunca fundidas**:

| hallazgo | medido | razonado |
|---|---|---|
| ... | número + cómo se obtuvo | hipótesis + qué la confirmaría |

**[T-13] Una ganancia prevista se enuncia como previsión, con su aritmética a la vista.** «18 round trips menos; a ~26 ms de RTT serían ~470 ms, sin medir» es honesto. «Ahorra 470 ms» no lo es. Precedentes: 827→663 predichos contra 795→773 reales, y un «vale ~190 ms» que valía 0.

**[T-14] Probar el camino infeliz antes de proponer.** Sin filtros, sin includes, con cero filas, con el principal más restringido. Un diseño validado sólo en el camino feliz llevaba un **500** dentro.

## 6. Regla de paro

Declararla antes de empezar: **qué resultado concreto hace abandonar**. Y cumplirla.

**[T-15] Un resultado negativo bien medido es un entregable.** «Los 18 sitios no ganan nada, y este es el motivo» cierra el tema para siempre y merece anotarse igual que un arreglo.

## 7. Veredicto y salida

- **Merece la pena y la petición pide hacer algo** → dos líneas en el chat (veredicto y el número que lo decide) y Paso 1 de `plan.md` en la misma invocación, con el premio, lo medido, lo descartado y la regla de paro en el Context del plan. Lo descartado no se vuelve a explorar, y los agentes gastados cuentan para el tope ([T-5]).
- **Arreglo directo** (una o dos líneas, con el premio ya medido) → Paso 1 con el perfil S y la plantilla corta del plan.
- **Solo era una pregunta** → responderla, con lo medido separado de lo razonado, y ofrecer el plan en una línea.
- **No merece la pena, bloqueado o Freno** → esta salida y terminar el turno, sin relanzar nada. Si ya se está en plan mode (se volvió a acotar desde el Paso 3), va como plan file con «nada que implementar» en la primera línea y se cierra con `ExitPlanMode`:

```
## Acotado — {petición en una línea}

**Veredicto**: {no merece la pena · bloqueado · parar · seguir con presupuesto nuevo} — {el número que lo decide}
**Ruta**: {B|C|Freno} · Perfil {S|M|L|XL}   **Premio**: {valor + unidad, o «no acotable»}
**Comprobación descalificante**: {pregunta} → {respuesta}
**Presupuesto**: declarado {N agentes · K mediciones · ~M min} → gastado {N' agentes · K' mediciones}{; si difiere, por qué}

### Medido
| hallazgo | número | cómo | alcance (N de M revisados) |

### Razonado (sin medir)
| hipótesis | qué la confirmaría |

### Descartado
- {qué} — {por qué, con el dato}

### Regla de paro
{qué hará abandonar, o qué la activó}

### Siguiente
{una de: no vale la pena · hace falta {instrumento/dato/decisión de negocio}, y cuál exactamente · seguir con {presupuesto}, con tu sí}
**Presupuesto vigente**: {N agentes · sin Workflow salvo tu sí} hasta cerrar esta tarea ([T-17])
```

Minutos gastados solo si se han medido (`date +%s` al empezar y al terminar). Si no, se omiten: una estimación presentada como dato es lo que prohíbe [T-13].
