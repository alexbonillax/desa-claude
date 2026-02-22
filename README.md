# Desa Claude

Plugin de Claude Code con skills internas de Grupo Desa.

## Instalacion

Desde Claude Code:

```
/plugin marketplace add https://github.com/alexbonillax/desa-claude.git
/plugin install desa@desa
```

Reiniciar Claude Code despues de instalar.

## Actualizacion

```
/plugin marketplace update desa
```

## Comandos disponibles

### /desa:wiki

Documenta en la wiki interna via API. Lee codigo fuente y genera documentacion basada en el codigo real.

```
/desa:wiki documenta el flujo de ventas basandote en el codigo
```

Requiere variable de entorno `DESA_WIKI_TOKEN`:

```bash
export DESA_WIKI_TOKEN="tu-token-aqui"
```

Anadelo a tu `~/.zshrc` para que persista entre sesiones.
