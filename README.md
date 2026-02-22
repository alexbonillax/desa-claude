# Desa Claude

Plugin de Claude Code con skills internas de Grupo Desa.

## Instalación

```
/install-plugin https://github.com/alexbonillax/desa-claude
```

## Skills disponibles

### /wiki

Documenta en la wiki interna vía API. Lee código fuente y genera documentación basada en el código real.

```
/wiki documenta el flujo de ventas basándote en el código
```

Requiere variable de entorno `DESA_WIKI_TOKEN`:

```bash
export DESA_WIKI_TOKEN="tu-token-aquí"
```

Añádelo a tu `~/.zshrc` para que persista entre sesiones.
