---
description: Gestionar las traducciones (terms) de Grupo Desa en la API y sincronizar los ficheros de idioma locales. Usar cuando hay que crear, cambiar, buscar o borrar un texto traducible, o sincronizar los ficheros con la API, y cuando el CLAUDE.md del proyecto manda pasar las traducciones por aquí
argument-hint: [crear term, sincronizar, buscar texto]
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py token-status), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py workdir), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py project), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py locales), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py find:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py search:*), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py sync), Read(/${CLAUDE_PLUGIN_ROOT}/references/ortografia.md)
---

# Translations — Gestión de traducciones de Grupo Desa

Gestiona las traducciones (terms) del proyecto con la API de Terms: crear, actualizar, eliminar y buscar terms, y sincronizar los ficheros locales de i18n con la API, que es la fuente de verdad.

Todo pasa por `terms.py`, que lee el token por su cuenta, pagina, aborta sin escribir ante cualquier error de la API y escribe los ficheros con el orden y el formato de los que ya hay en los proyectos (regenerar los actuales da bytes idénticos). No llamar a la API con curl ni generar los ficheros a mano. Sin `--apply`, ningún subcomando escribe nada: enseña lo que haría.

## Paso 1: Detectar tipo de proyecto

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py project
```

- `PROYECTO=frontend`: namespace siempre `app`, ficheros en `packages/i18n/src/locales/{lang}/translations.json`.
- `PROYECTO=backend`: un fichero por namespace en `resources/lang/{lang}/` (o `lang/{lang}/`). `NAMESPACES` son los que hay en local, sin los propios de Laravel (`auth`, `validation`, `passwords`, `pagination`, `errors`), que no vienen de la API y no se tocan nunca: sobrescribirlos borraría los mensajes del framework.
- `PROYECTO=no-project`: solo API. Se pueden crear, actualizar, eliminar y buscar terms, pero no sincronizar ficheros. Decírselo al usuario.

La raíz es la del repositorio git, así que da igual desde qué subdirectorio se ejecute. Los idiomas salen siempre de la API (`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py locales`), nunca escritos a mano.

## Paso 2: Token

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py token-status
```

- `OK …` → seguir. El token lo lee el script: no imprimirlo, no ponerlo en ningún comando y no pedirlo si ya hay uno. El que ya estuviera en la clave `desa_wiki_token` de `~/.claude/settings.json` sigue valiendo.
- `NO_TOKEN`, `TOKEN_INVALIDO` o un 401 más adelante → pedir al usuario que copie su token de la API al portapapeles y lo guarde con esta orden en la propia sesión. El `!` delante hace que el token no pase por la conversación:

  ```
  ! pbpaste | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py set-token --stdin
  ```

  Queda en `~/.config/desa/api-token` con permisos 600. Fuera de macOS, que ejecute en su terminal `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py set-token`, que lo pide por teclado. Si aun así pega el token en el chat, guardarlo con Write en `~/.config/desa/api-token`, ejecutar `chmod 600 ~/.config/desa/api-token` y avisarle de que queda en el historial de la sesión.

Si `token-status` dice `OK DESA_API_TOKEN`, el token sale de esa variable de entorno, que tiene prioridad: ante un 401, pedir al usuario que la actualice o la quite, porque `set-token` no la cambia.

Sin token válido no se sigue. El mismo token sirve para `/desa:wiki`.

## Modo de operación

Deducir la intención de `$ARGUMENTS`:

- **Sincronizar** («sincroniza», «sync», «actualiza los ficheros de idioma»): traer de la API a los ficheros locales.
- **Buscar** («busca X», «¿existe una traducción para…?»).
- **Crear o actualizar** un term («añade», «crea», «cambia el texto de…», «traduce… al francés»).
- **Eliminar** un term («elimina», «borra»).

«Actualiza las traducciones», sin más, es ambiguo entre sincronizar y cambiar un term: preguntar. Si `$ARGUMENTS` está vacío, pedir qué hacer y terminar.

## Errores de la API

`terms.py` aborta con `ERROR=` y no escribe nada, ni en la API ni en local. Los cambios locales se calculan antes de escribir en la API; si la API ya se ha escrito y falla la escritura local, lo dice aparte con `ERROR_LOCAL=`, y entonces hay que avisar al usuario de que la API sí quedó actualizada. Los errores de la API:

- **401**: token caducado o inválido → pedir uno nuevo con el procedimiento del Paso 2.
- **403**: autenticado pero sin permisos de escritura → decírselo al usuario.
- **404** en una búsqueda por code: el term no existe (no es un error). En `/terms/{id}`: el id no existe.
- **422**: error de validación → enseñar el campo `errors` de la respuesta.
- **5xx** o error de red → decírselo al usuario e invitarle a reintentar en unos instantes.

## Flujo: Buscar

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py search 'texto a buscar'
```

Imprime una tabla con una columna por idioma de `/locales` (`—` donde no hay traducción). Si sale `HAY_MAS=si`, decírselo al usuario y preguntar si quiere la siguiente página (`--page 2`).

## Flujo: Crear o actualizar un term

1. Namespace: en frontend, siempre `app`; en backend, deducirlo del contexto o preguntar, con `app` por defecto.
2. Comprobar si existe: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py find --ns {ns} --code {code}` (imprime el term o `NO_EXISTE`). Antes de crear uno nuevo, buscar también por el texto en español (`search`): si ya hay un `global.*` con el mismo valor y significado, mencionarlo en el resultado, sin bloquear la creación.
3. Escribir los valores con Write en un fichero JSON (`{"es": "…", "fr": "…"}`), solo con idiomas de `/locales`, en el directorio que da `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py workdir`. Por defecto, los idiomas que ha dado el usuario; `upsert` avisa con `SIN_TRADUCCION` de los que faltan. Si el `CLAUDE.md` del proyecto pide traducir a todos los idiomas de `/locales`, proponer los que falten: son traducciones del modelo y requieren la confirmación del paso 6. Nunca cadenas vacías. Variantes: `es` es español de España y `pt`, portugués de Portugal.
4. Revisar la ortografía de `es` (sección «Ortografía»). Si se corrige el texto que ha dado el usuario, cuenta para la confirmación del paso 6.
5. Dry-run: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py upsert --ns {ns} --code {code} --values {fichero}`. Enseña, por idioma, el valor actual, el nuevo y si es nuevo o sobrescribe, y en `LOCAL` los ficheros que tocaría. Con un namespace propio de Laravel se niega; con uno que no existe en local, lo deja solo en la API y lo avisa.
6. **Pedir confirmación** antes de `--apply` si se sobrescribe algún valor, si hay traducciones propuestas por el modelo o si se ha corregido la ortografía del texto del usuario. En ese caso, enseñar la tabla del dry-run y decir de dónde sale cada valor. Si el usuario ha dado todos los valores de un term nuevo, basta con enseñar el resultado.
7. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py upsert --ns {ns} --code {code} --values {fichero} --apply`. Envía el objeto completo (lo actual fusionado con lo nuevo) y actualiza los ficheros locales de cada idioma con valor. No se sabe si la API fusiona o reemplaza `value`, así que no se promete que omitir un idioma lo borre.

Si sale `AVISO=idioma nuevo …`, decirle al usuario que registre el idioma en `packages/i18n/src/index.js` (import, resources y supportedLngs) y en la configuración de i18n de web y mobile.

## Flujo: Eliminar un term

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py delete --ns {ns} --code {code}`: enseña el id y los valores actuales, sin borrar.
2. Confirmar con el usuario, enseñando code y valores.
3. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py delete --ns {ns} --code {code} --apply`: lo borra de la API (soft delete) y quita la clave de los ficheros locales de todos los idiomas.

## Flujo: Sincronizar (API → ficheros locales)

Requiere estar en un proyecto. La API es la fuente de verdad: el contenido de cada fichero gestionado se sustituye por el de la API.

1. Dry-run: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py sync`. Imprime, por fichero, altas, cambios y bajas (`+N ~N -N`, con las claves que se darían de baja), y además:
   - `BAJAS`: número de claves que desaparecerían;
   - `CAMBIOS_SIN_COMMITEAR`: ficheros de idioma con cambios en git que el sync sobrescribiría;
   - `NAMESPACE_AJENO`: namespaces locales que se llaman como uno de la API pero no comparten ninguna clave con él (p. ej. el `app` propio de gdapps frente al `app` de grupodesa); no se tocan;
   - `OBSOLETO`: ficheros de un idioma sin terms en la API; no se borran;
   - `SIN_TERMS_EN_API`: namespaces locales que la API no gestiona; no se tocan;
   - `SOLO_EN_API`: namespaces de la API que no existen en local;
   - `IDIOMAS_NUEVOS`.
2. Si `BAJAS=0` y `CAMBIOS_SIN_COMMITEAR=ninguno`, aplicar directamente. Si hay bajas o cambios sin commitear, enseñárselos al usuario y pedir confirmación: pueden ser trabajo local sin subir, o terms borrados en la API por error.
3. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/terms.py sync --apply`, con los mismos argumentos que el dry-run que se ha revisado. Para crear en local un namespace de `SOLO_EN_API`, o sustituir uno de `NAMESPACE_AJENO`, añadir `--include-ns {ns}` solo si el usuario lo pide, y volver a hacer antes el dry-run con ese flag y aplicarle la regla del paso 2. En frontend solo existe el namespace `app`.
4. Resumen al usuario: ficheros escritos, idiomas y avisos. Si hay `IDIOMAS_NUEVOS` en frontend, recordar registrarlos en `packages/i18n/src/index.js`.

## Referencia de la API

`terms.py` ya la usa. Esta sección es para entender sus mensajes, no para llamarla a mano.

| Método | URI | Descripción |
|--------|-----|-------------|
| GET | `/locales` | Idiomas disponibles |
| GET | `/terms?filter[namespace]=…&filter[search]=…&perPage=100&page=N` | Listado paginado (`meta.has_more_pages`) |
| GET | `/terms?filter[code]=…&filter[namespace]=…` | Un term exacto: `data` es un **objeto**, o 404 si no existe. Siempre con namespace, porque el mismo code puede estar en varios |
| POST | `/terms/new` | Crear: `{"fields": {"namespace", "code", "value": {"es": …}}}` |
| POST | `/terms/{id}` | Actualizar, con el mismo body |
| DELETE | `/terms/{id}` | Soft delete |

`value` es un objeto por idioma y solo trae los idiomas con traducción.

## Formatos de fichero

`terms.py` los escribe, y los lee sin ejecutarlos: si un PHP no es un `return array(...)` plano de pares texto => texto, se niega y pide `--allow-php`, que lo carga con PHP y por tanto lo ejecuta. Añadir `--allow-php` solo si el usuario confía en ese fichero, porque no está preaprobado. Se describen para poder revisar un diff:

- **Frontend**: JSON plano con claves en dot-notation ordenadas, 2 espacios de indentación, UTF-8 sin escapar y salto de línea final.
- **Backend**: `<?php\n\nreturn array(...);` plano, con claves ordenadas, comillas dobles, `=>` alineados con la clave más larga y salto de línea final. Claves y valores se escapan en este orden: `\` → `\\`, `"` → `\"`, `$` → `\$`. Dentro de comillas dobles PHP interpola `$var` y evalúa `{${expr}}`, así que un valor sin escapar tumba el fichero entero (Laravel convierte el warning en excepción) o ejecuta código al cargarlo, y los valores los escribe cualquiera con acceso a la API.

## Ortografía

Antes de cada escritura, revisar el `value.es` completo con `${CLAUDE_PLUGIN_ROOT}/references/ortografia.md`. La tabla recoge los errores más frecuentes y las formas que dependen del contexto (*publica*, *numero*), pero se revisa todo el texto. Solo se aplica a `es`.

## Límites

- **La API es la fuente de verdad**, y los ficheros locales se escriben solo con `terms.py`.
- **Buscar antes de crear**, siempre con code y namespace.
- **Ortografía** de `value.es` revisada antes de cada escritura.
- **Los ficheros propios de Laravel no se tocan nunca.**
