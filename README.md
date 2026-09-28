# Desa Claude

Plugin de Claude Code con skills internas de Grupo Desa.

## Instalación

Desde Claude Code:

```
/plugin marketplace add https://github.com/alexbonillax/desa-claude.git
/plugin install desa@desa
```

Reiniciar Claude Code después de instalar.

## Actualización

```
/plugin marketplace update desa
```

Si no se actualiza, borrar el cache y reinstalar:

```bash
rm -rf ~/.claude/plugins/cache/desa
```

Y luego en Claude Code: `/plugin install desa@desa`

## Comandos disponibles

### /desa:wiki

Consulta o documenta en la wiki interna vía API. Lee código fuente y genera documentación basada en el código real.

```
/desa:wiki documenta el flujo de ventas basándote en el código
/desa:wiki qué dice la wiki sobre pedidos
```

El token de la API se lee de la variable `DESA_API_TOKEN`, de `~/.config/desa/api-token` o, si ya lo tenías guardado, de la clave `desa_wiki_token` de `~/.claude/settings.json`; el mismo token sirve para `/desa:translations`. La primera vez, la skill te da la orden para guardarlo sin pegarlo en el chat (copias el token y ejecutas `! pbpaste | python3 …/desa_api.py set-token --stdin`). El token no aparece nunca en los comandos ni en el historial. Antes de crear o actualizar una página, la skill enseña una vista previa y espera tu confirmación.

### /desa:review

Revisa código antes de commits o PRs aplicando los estándares del equipo. Detecta el tipo de proyecto (backend Laravel, monorepo React con web y mobile, o websites Next.js) y aplica los criterios de cada tipo que toque el diff; un mismo diff puede ser frontend + mobile.

```
/desa:review                       # staged; si no hay, unstaged y ficheros nuevos; con el árbol limpio, la rama frente a su base (main o develop), o el último commit si estás en ella
/desa:review src/Models/Order.php  # revisa solo un fichero
/desa:review 42                    # revisa los cambios de la PR #42
/desa:review --verbose             # añade las incidencias descartadas por baja confianza
```

Reporta incidencias agrupadas por severidad (Crítico / Importante / Menor) con referencia a fichero y línea. Después ejecuta los tests de los ficheros del diff. En backend, siempre con `APP_ENV=testing` y nunca la suite entera ni un directorio. Si un test falla, dice si es una regresión o un test desactualizado y propone la corrección al final del informe sin tocar nada. Si hay líneas nuevas sin cubrir, genera tests y deja en staging los que crea y los que modifica si no tenían cambios tuyos, sin commit. En backend solo ejecuta tests si el entorno de tests usa una BD sqlite aislada. La cabecera del informe dice siempre qué se revisó, qué tests se ejecutaron y la cobertura del diff, también cuando no se pudo ejecutar nada.

## Mantenimiento: `allowed-tools`

`allowed-tools` no restringe nada: preaprueba herramientas durante el turno en que se invoca la skill, y el modelo puede invocar las skills del plugin por su cuenta. Por eso:

- No añadir intérpretes ni red (`Bash(python3:*)`, `Bash(php:*)`, `Bash(curl:*)`, `Bash(claude:*)`).
- No añadir prefijos de git (`Bash(git:*)`, `Bash(git log:*)`, `Bash(git diff:*)`…). Claude Code ya aprueba por su cuenta `git diff/log/show/status` con flags seguros, y un prefijo admite también `--output=<fichero>`, que escribe ficheros arbitrarios.
- Si hace falta preaprobar algo, que sea el comando exacto, p. ej. `Bash(claude plugin marketplace update desa)`. Excepciones:
  - `Bash(gh pr diff:*)` en `/desa:review`, porque Claude Code no aprueba solo ningún comando `gh` y `gh pr diff` no tiene flags que escriban ficheros.
  - Los scripts de solo lectura del propio plugin, p. ej. `Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/diff-context.sh:*)`. Claude Code sustituye `${CLAUDE_PLUGIN_ROOT}` también dentro de `allowed-tools`.
  - Las lecturas de los clientes de la API: `desa_api.py token-status`, `workdir` y `GET:*` (el cliente solo admite las rutas de la wiki y de terms), y los subcomandos de `terms.py` que no escriben ni ejecutan PHP (`project`, `locales`, `find`, `search` y `sync` sin `--apply`, este como orden exacta). Nunca un prefijo que admita `POST`, `DELETE`, `--apply` o `--allow-php`. Un GET no significa «sin efectos» en cualquier API: por eso el cliente limita las rutas.

Los scripts de `plugins/desa/scripts/` tienen sus pruebas en `tests/`, que no se distribuye con el plugin: `bash tests/diff-context.test.sh`, `bash tests/test-context.test.sh` y `python3 -m unittest discover -s tests`.
