---
description: Actualizar el plugin Desa a la última versión
allowed-tools: Bash(claude plugin marketplace update desa), Bash(claude plugin update desa@desa), Bash(claude plugin list --json), Read(~/.claude/plugins/installed_plugins.json), Read(~/.claude/plugins/known_marketplaces.json), Read(~/.claude/plugins/marketplaces/desa/CHANGELOG.md)
disable-model-invocation: true
---

# Update — Actualizar plugin Desa

Actualiza el plugin Desa a la última versión publicada y dice qué ha cambiado. El mensaje final sale solo de lo que muestren los comandos, no de lo que se espera que pase.

## Pasos

1. Anotar:
    - la versión que tiene cargada esta sesión: el último directorio de `${CLAUDE_PLUGIN_ROOT}`;
    - la instalada: `version` de la entrada `desa@desa` en

        ```bash
        claude plugin list --json
        ```

    - el `gitCommitSha` de `desa@desa` en `~/.claude/plugins/installed_plugins.json`, y el `installLocation` de `desa` en `~/.claude/plugins/known_marketplaces.json`, que es el clon del marketplace (normalmente `~/.claude/plugins/marketplaces/desa`).

2. Comprobar que el clon del marketplace no tiene trabajo sin subir. Primero `fetch`, porque Claude Code actualiza el clon con `git pull origin HEAD`, que no mueve `origin/main`: sin él, todo lo que llegó en actualizaciones anteriores parecería trabajo sin subir.

    ```bash
    git -C {installLocation} fetch origin
    git -C {installLocation} status --porcelain
    git -C {installLocation} log --oneline @{u}..HEAD
    ```

    Si alguna devuelve algo, parar y enseñárselo al usuario: si el `git pull` del paso 3 falla, Claude Code aparta el clon, lo vuelve a clonar y borra ese trabajo sin avisar, y el comando sale bien. Que lo suba o lo guarde antes de actualizar.

3. Refrescar el marketplace:

    ```bash
    claude plugin marketplace update desa
    ```

4. Actualizar el plugin:

    ```bash
    claude plugin update desa@desa
    ```

5. Volver a ejecutar `claude plugin list --json` y comparar la versión con la del paso 1.

Si algún comando falla, parar ahí: enseñar el error y no decir que el plugin se ha actualizado. Las causas habituales son dos: no hay red, o `claude` no está en el PATH del Bash tool, p. ej. si solo se usa la app de escritorio.

Las órdenes `git -C …` no están preaprobadas, porque la ruta y el commit cambian de una máquina a otra, y pedirán permiso. La lectura del `CHANGELOG.md` solo está preaprobada en la ruta habitual del clon.

## Qué decir al usuario

- **Versión nueva**: «Plugin Desa actualizado de X a Y.» Después, como mucho una línea por cada versión posterior a X, sacada del `CHANGELOG.md` de `installLocation`. Si falta alguna entrada, listar en su lugar `git -C {installLocation} log --oneline {gitCommitSha del paso 1}..HEAD -- plugins/desa` (el paso 2 ya ha comprobado que no hay commits locales); si git no encuentra ese commit (el clon se rehízo con poca profundidad), decir que no se puede listar. Terminar con: «Ejecuta `/reload-plugins` (si avisa por la caché del prompt, `/reload-plugins --force`) o reinicia la sesión; hasta entonces, esta sesión sigue con las skills de la versión anterior.» Es una indicación para el usuario: el modelo no puede ejecutarlo.
- **Misma versión**: «Ya tenías la última versión (X).» Si la versión cargada en la sesión (paso 1) es otra, añadir que esta sesión sigue con esa y dar la misma indicación de `/reload-plugins`. Si `git -C {installLocation} log --oneline {gitCommitSha}..HEAD -- plugins/desa` muestra commits, explicar que se publicaron cambios sin subir `version` en `plugin.json` y ofrecer el procedimiento del README (borrar `~/.claude/plugins/cache/desa` y reinstalar). No ejecutarlo sin confirmación.
