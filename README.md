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
