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

El token se guarda automáticamente en `~/.claude/settings.json`. La primera vez que uses el comando, te pedirá el token y lo guardará para futuras sesiones.

### /desa:review

Revisa código antes de commits o PRs aplicando los estándares del equipo. Detecta automáticamente si el proyecto es backend (Laravel) o frontend (React monorepo) y aplica los criterios correspondientes.

```
/desa:review                    # revisa cambios staged, unstaged o último commit
/desa:review src/Models/Order.php  # revisa solo un fichero
/desa:review 42                 # revisa los cambios de la PR #42
```

Reporta incidencias agrupadas por severidad (Crítico / Importante / Menor) con referencia a fichero y línea.

## Mantenimiento: `allowed-tools`

`allowed-tools` no restringe nada: preaprueba herramientas durante el turno en que se invoca la skill, y el modelo puede invocar las skills del plugin por su cuenta. Por eso:

- No añadir intérpretes ni red (`Bash(python3:*)`, `Bash(php:*)`, `Bash(curl:*)`, `Bash(claude:*)`).
- No añadir prefijos de git (`Bash(git:*)`, `Bash(git log:*)`, `Bash(git diff:*)`…). Claude Code ya aprueba por su cuenta `git diff/log/show/status` con flags seguros, y un prefijo admite también `--output=<fichero>`, que escribe ficheros arbitrarios.
- Si hace falta preaprobar algo, que sea el comando exacto, p. ej. `Bash(claude plugin marketplace update desa)`. Única excepción: `Bash(gh pr diff:*)` en `/desa:review`, porque Claude Code no aprueba solo ningún comando `gh` y `gh pr diff` no tiene flags que escriban ficheros.
