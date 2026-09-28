---
description: Actualizar el plugin Desa a la última versión
allowed-tools: Bash(claude plugin marketplace update desa), Bash(claude plugin update desa@desa), Bash(claude plugin list --json), Read(~/.claude/plugins/installed_plugins.json), Read(~/.claude/plugins/known_marketplaces.json), Read(~/.claude/plugins/marketplaces/desa/CHANGELOG.md)
disable-model-invocation: true
---

# Update — Actualizar plugin Desa

Actualiza el plugin Desa a la última versión publicada y dice qué ha cambiado. El mensaje final sale solo de lo que muestren los comandos, no de lo que se espera que pase.

## Pasos

1. Anotar lo que hay instalado: `version` de la entrada `desa@desa` en

    ```bash
    claude plugin list --json
    ```

    Anotar también el `gitCommitSha` de `desa@desa` en `~/.claude/plugins/installed_plugins.json`, y el `installLocation` de `desa` en `~/.claude/plugins/known_marketplaces.json`, que es el clon del marketplace (normalmente `~/.claude/plugins/marketplaces/desa`).

2. Refrescar el marketplace:

    ```bash
    claude plugin marketplace update desa
    ```

3. Actualizar el plugin:

    ```bash
    claude plugin update desa@desa
    ```

4. Volver a ejecutar `claude plugin list --json` y comparar la versión con la del paso 1.

Si algún comando falla, parar ahí: enseñar el error y no decir que el plugin se ha actualizado. Las causas habituales son tres: no hay red; hay cambios locales en el clon del marketplace (`installLocation`); o `claude` no está en el PATH del Bash tool, p. ej. si solo se usa la app de escritorio.

## Qué decir al usuario

- **Versión nueva**: «Plugin Desa actualizado de X a Y.» Después, como mucho una línea por cada versión posterior a X, sacada del `CHANGELOG.md` de `installLocation`. Si falta alguna entrada, listar en su lugar `git -C {installLocation} log --oneline {gitCommitSha del paso 1}..HEAD -- plugins/desa`. Terminar con: «Ejecuta `/reload-plugins` (si avisa por la caché del prompt, `/reload-plugins --force`) o reinicia la sesión; hasta entonces, esta sesión sigue con las skills de la versión anterior.» Es una indicación para el usuario: el modelo no puede ejecutarlo.
- **Misma versión**: «Ya tenías la última versión (X).» Si `git -C {installLocation} log --oneline {gitCommitSha}..HEAD -- plugins/desa` muestra commits, explicar que se publicaron cambios sin subir `version` en `plugin.json` y ofrecer el procedimiento del README (borrar `~/.claude/plugins/cache/desa` y reinstalar). No ejecutarlo sin confirmación.
