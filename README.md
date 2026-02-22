# Desa Claude

Plugin de Claude Code con skills internas de Grupo Desa.

## Instalación

```bash
git clone https://github.com/alexbonillax/desa-claude.git ~/.claude/plugins/marketplaces/claude-plugins-official/external_plugins/desa-claude
```

Reiniciar Claude Code después de instalar.

## Actualización

```bash
cd ~/.claude/plugins/marketplaces/claude-plugins-official/external_plugins/desa-claude && git pull
```

## Skills disponibles

### /desa-wiki

Documenta en la wiki interna vía API. Lee código fuente y genera documentación basada en el código real.

```
/desa-wiki documenta el flujo de ventas basándote en el código
```

Requiere variable de entorno `DESA_WIKI_TOKEN`:

```bash
export DESA_WIKI_TOKEN="tu-token-aquí"
```

Añádelo a tu `~/.zshrc` para que persista entre sesiones.
