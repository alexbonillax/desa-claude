# Desa Claude

Plugin de Claude Code con las skills internas de Grupo Desa.

## Instalación

Desde Claude Code:

```
/plugin marketplace add https://github.com/alexbonillax/desa-claude.git
/plugin install desa@desa
```

Después, `/reload-plugins` o reiniciar la sesión.

## Actualización

```
/desa:update
```

Comprueba que el clon del marketplace no tiene trabajo sin subir (una actualización fallida lo vuelve a clonar y lo borra), refresca el marketplace, actualiza el plugin y dice de qué versión a qué versión ha pasado y qué trae. Si no hay versión nueva, también lo dice, y avisa si la sesión sigue con una versión anterior.

A mano, lo mismo son dos órdenes: `claude plugin marketplace update desa` y `claude plugin update desa@desa`. `/plugin marketplace update desa` solo refresca el catálogo, no el plugin instalado.

Si aun así no llegan los cambios, borrar la caché y reinstalar (último recurso):

```bash
rm -rf ~/.claude/plugins/cache/desa
```

Y luego, en Claude Code: `/plugin install desa@desa`.

## Skills

| Skill | Para qué | Escribe fuera del chat | El modelo la puede lanzar solo |
|---|---|---|---|
| `/desa:triage` | Acotar una tarea antes de trabajarla | No. Solo lee y mide, y confirma las mediciones que no son locales | Sí |
| `/desa:plan` | Planificar en plan mode con los criterios de review | No. El plan se aprueba antes de implementar | Sí |
| `/desa:review` | Revisar cambios antes de commit o PR, ejecutar los tests y generar los que falten | Sí: tests nuevos, en staging y sin commit | Sí |
| `/desa:wiki` | Consultar y documentar la wiki interna | Sí: páginas de la wiki, con vista previa y confirmación | Sí |
| `/desa:translations` | Terms de traducción y ficheros de idioma | Sí: API de terms y ficheros locales, con dry-run y confirmación | Sí |
| `/desa:update` | Actualizar este plugin | Sí: el plugin instalado | No |
| `/desa:magic-factorial` | Fichajes en Factorial | Sí: el registro de jornada en Factorial | Sí |

«El modelo la puede lanzar solo» significa que Claude puede invocarla sin que escribas el comando, p. ej. porque lo pide el `CLAUDE.md` de un proyecto. Salvo que tengas una regla `allow` para esa skill, Claude Code pide permiso antes.

### /desa:triage

Primera skill de una sesión cuando la tarea es un síntoma («va lento», «falla a veces») o una decisión («¿merece la pena?»). Dimensiona el premio, responde primero la pregunta que haría irrelevante el resto y declara el presupuesto antes de gastarlo. Termina en un veredicto y, si procede, con la invocación de `/desa:plan` lista para pegar.

```
/desa:triage el listado de pedidos tarda 4 s
/desa:triage ¿merece la pena cachear los precios por cliente?
```

### /desa:plan

Convierte una tarea acotada en un plan: explora el código, inventaría lo que se puede reusar, lo contrasta con los criterios de `/desa:review` y termina en plan mode para que lo apruebes antes de implementar. Detecta backend, monorepo (web y mobile) y websites.

```
/desa:plan añadir el filtro por región al listado de expediciones
```

### /desa:review

Revisa código antes de commits o PRs aplicando los estándares del equipo. Detecta el tipo de proyecto (backend Laravel, monorepo React con web y mobile, o websites Next.js) y aplica los criterios de cada tipo que toque el diff; un mismo diff puede ser frontend + mobile.

```
/desa:review                       # staged; si no hay, unstaged y ficheros nuevos; con el árbol limpio, la rama frente a su base (main o develop), o el último commit si estás en ella
/desa:review src/Models/Order.php  # revisa solo un fichero
/desa:review 42                    # revisa los cambios de la PR #42
/desa:review --verbose             # lista también las incidencias descartadas (sin evidencia o con baja confianza)
```

Reporta incidencias agrupadas por severidad (Crítico / Importante / Menor) con referencia a fichero y línea y al criterio `#N`. Los criterios están en `plugins/desa/references/`, uno por stack.

Después ejecuta los tests de los ficheros del diff. En backend, solo si el entorno de tests usa una BD sqlite aislada, siempre con `APP_ENV=testing` y nunca la suite entera ni un directorio. Si `config/database.php` tiene conexiones a servidores reales (escritas en el fichero o en sus variables de entorno), como en grupodesa-backend, no los ejecuta sola: te lo ofrece al final del informe. Si un test falla, dice si es una regresión o un test desactualizado y propone la corrección al final del informe sin tocar nada. Si hay líneas nuevas sin cubrir, genera tests y deja en staging los que crea y los que modifica si no tenían cambios tuyos, sin commit. La cabecera del informe dice siempre qué se revisó, qué tests se ejecutaron y la cobertura del diff, también cuando no se pudo ejecutar nada.

### /desa:wiki

Consulta o documenta en la wiki interna vía API. Para documentar, lee el código fuente y documenta solo lo que ha visto.

```
/desa:wiki documenta el flujo de ventas basándote en el código
/desa:wiki qué dice la wiki sobre pedidos
```

Antes de crear o actualizar una página, enseña una vista previa (con la visibilidad y el diff) y espera tu confirmación. Al actualizar, conserva los equipos y roles que ya tenía la página, y no envía nada si alguien la ha editado mientras tanto.

### /desa:translations

Gestiona los terms de traducción vía API y sincroniza los ficheros de idioma del proyecto: `packages/i18n/src/locales/` en frontend, y `resources/lang/` o `lang/` en backend.

```
/desa:translations busca "guardar"
/desa:translations crea global.save-changes: es «Guardar cambios», fr «Enregistrer les modifications»
/desa:translations sincroniza
```

Todo pasa por `scripts/terms.py`: sin `--apply` solo enseña lo que haría, escribe los ficheros con el formato de grupodesa-front y grupodesa-backend (si un proyecto usa otro, el dry-run lo marca), escapa bien los valores en PHP, lee los PHP sin ejecutarlos y no escribe nada si la API da un error. Pide confirmación antes de sobrescribir traducciones, de publicar traducciones propuestas por Claude, de reescribir ficheros que cambiarían de formato, o de sincronizar si hay bajas o cambios sin commitear.

### /desa:update

Ver «Actualización».

### /desa:magic-factorial

Crea, corrige y cuadra fichajes en Factorial usando la API interna de Factorial con las cookies de sesión del navegador. Escribe en el registro oficial de jornada.

## Token de la API (wiki y translations)

Las dos skills usan el mismo token de `api2.grupodesa.app`, y lo lee `scripts/desa_api.py`, que no lo imprime nunca ni lo pone en ningún comando. Lo busca en este orden: la variable `DESA_API_TOKEN`, `~/.config/desa/api-token` y las claves `desa_api_token` o `desa_wiki_token` de `~/.claude/settings.json`. Si ya lo tenías en `desa_wiki_token`, no hay que hacer nada.

Para guardarlo la primera vez sin pegarlo en el chat, copia el token y ejecuta en la sesión la orden que te da la skill (`! pbpaste | python3 …/desa_api.py set-token --stdin`). Queda en `~/.config/desa/api-token` con permisos 600.

## Mantenimiento

### `allowed-tools`

`allowed-tools` no restringe nada: preaprueba herramientas durante el turno en que se invoca la skill, y el modelo puede invocar las skills del plugin por su cuenta. Por eso:

- No añadir intérpretes ni red (`Bash(python3:*)`, `Bash(php:*)`, `Bash(curl:*)`, `Bash(claude:*)`).
- No añadir prefijos de git (`Bash(git:*)`, `Bash(git log:*)`, `Bash(git diff:*)`…). Claude Code ya aprueba por su cuenta `git diff/log/show/status` con flags seguros, y un prefijo admite también `--output=<fichero>`, que escribe ficheros arbitrarios.
- Si hace falta preaprobar algo, que sea el comando exacto, p. ej. `Bash(claude plugin marketplace update desa)`. Excepciones:
  - `Bash(gh pr diff:*)` en `/desa:review`, porque Claude Code no aprueba solo ningún comando `gh` y `gh pr diff` no tiene flags que escriban ficheros.
  - Los scripts de solo lectura del propio plugin, p. ej. `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh:*)`. Claude Code sustituye `${CLAUDE_PLUGIN_ROOT}` también dentro de `allowed-tools`.
  - La lectura de los ficheros de `references/` que usa cada skill, como `Read(/${CLAUDE_PLUGIN_ROOT}/references/ortografia.md)`: la doble barra que queda al sustituir la variable es la forma de las reglas para una ruta absoluta.
  - Las lecturas de los clientes de la API: `desa_api.py token-status`, `workdir` y `GET:*` (el cliente solo admite las rutas de la wiki y de terms), y los subcomandos de `terms.py` que no escriben ni ejecutan PHP (`project`, `locales`, `find`, `search` y `sync` sin `--apply`, este como orden exacta). Nunca un prefijo que admita `POST`, `DELETE`, `--apply` o `--allow-php`. Un GET no significa «sin efectos» en cualquier API: por eso el cliente limita las rutas.

### Criterios de review

Los criterios de `/desa:review`, que también usa `/desa:plan`, están en `plugins/desa/references/criterios-{compartidos,backend,frontend,mobile,websites}.md`, y cada skill carga solo los del tipo de proyecto que toca. Los números `#N` los citan los informes, los planes y las PRs de otros repos, así que no se renumeran nunca: un criterio nuevo va al final de su fichero con el siguiente número libre, y uno retirado se queda marcado como «(retirado)». Un criterio de websites marcado `(= #N)` es gemelo de uno del monorepo: si se cambia uno, se cambia el otro.

La tabla de ortografía de `/desa:wiki` y `/desa:translations` está en `plugins/desa/references/ortografia.md`.

### Versiones y CHANGELOG

Todo cambio en `plugins/desa/` sube `version` en `plugins/desa/.claude-plugin/plugin.json` y lleva su entrada en `CHANGELOG.md`. Si la versión no cambia, `claude plugin update` no instala nada: la caché va por versión. CI lo comprueba en cada PR.

### Pruebas y CI

Los scripts de `plugins/desa/scripts/` tienen sus pruebas en `tests/`, que no se distribuye con el plugin:

```bash
bash tests/diff-context.test.sh
bash tests/test-context.test.sh
python3 -m unittest discover -s tests
```

`.github/workflows/ci.yml` las ejecuta en cada PR, junto con `claude plugin validate --strict`, la comprobación de que ha subido la versión y un aviso si alguna skill preaprueba intérpretes, red o git completos.

Los evals de comportamiento de las skills están en `plugins/desa/evals/` (ver su README).
