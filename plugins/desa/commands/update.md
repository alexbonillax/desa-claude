---
description: Actualizar el plugin Desa a la última versión
allowed-tools: Bash(claude:*)
---

# Update — Actualizar plugin Desa

Actualiza el plugin Desa a la última versión disponible en el repositorio.

## Pasos

1. Refrescar el marketplace (git pull del repo):

```bash
claude plugin marketplace update desa
```

2. Actualizar el plugin a la última versión:

```bash
claude plugin update desa@desa
```

3. Informar al usuario: **"Plugin actualizado. Reinicia la sesión de Claude Code para que apliquen los cambios."**

Si algún comando falla, mostrar el error al usuario.
