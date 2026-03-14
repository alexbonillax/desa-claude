---
description: Gestionar traducciones (terms) vía API y sincronizar archivos locales
argument-hint: [crear term, sincronizar, buscar texto]
allowed-tools: Bash(curl:*), Bash(python3:*)
---

# Translations — Gestión de traducciones de Grupo Desa

Gestionas las traducciones (terms) del proyecto vía la API de Terms. Puedes crear, actualizar, eliminar y buscar traducciones, y sincronizar los archivos locales de i18n con la API (fuente de verdad).

## Paso 1: Detectar tipo de proyecto

Desde el directorio de trabajo actual:

```bash
if [ -d packages/i18n/src/locales ]; then echo "frontend"; elif [ -d resources/lang ]; then echo "backend"; else echo "no-project"; fi
```

Comportamiento según resultado:

- **frontend**: Namespace siempre `app`. Archivos en `packages/i18n/src/locales/{lang}/translations.json`
- **backend**: Múltiples namespaces (app, export, notifications, paper-catalog). Archivos en `resources/lang/{lang}/{namespace}.php`. **NUNCA modificar**: auth.php, validation.php, passwords.php, pagination.php, errors.php
- **no-project**: Modo API-only. Puedes crear/actualizar/eliminar/buscar terms, pero no sincronizar archivos locales. Informa al usuario

**Idiomas**: Siempre obtener de la API (`GET /locales`) antes de sync. No hardcodear idiomas.

## Paso 2: Configuración

**Antes de cualquier llamada a la API**, extrae el token de `~/.claude/settings.json`:

```bash
python3 -c "import json, os; f=os.path.expanduser('~/.claude/settings.json'); print(json.load(open(f)).get('desa_wiki_token','') if os.path.exists(f) else '')"
```

Guarda el valor resultante y úsalo directamente en todas las llamadas curl como `Bearer TOKEN`.

Si el resultado está vacío (no hay token guardado):

1. Pide al usuario que te pase su token ("Pásame tu token para continuar")
2. Una vez lo proporcione, guárdalo en `~/.claude/settings.json` usando Read para leer el fichero y Edit para añadir la clave `"desa_wiki_token": "TOKEN_DEL_USUARIO"` al objeto JSON raíz
3. Usa ese token directamente en las llamadas curl de esta sesión

**No continúes sin token válido.**

## API

- **Base URL**: `https://api2.grupodesa.app`
- **Auth**: `Authorization: Bearer TOKEN` (el token extraído de settings.json)
- **curl**: Usar siempre `-g` para evitar problemas con corchetes en URLs
- **Importante**: No usar variables de entorno en curl. No persisten entre llamadas. Siempre pegar el token directamente en el comando curl

### Endpoints de Terms

| Método | URI | Descripción |
|--------|-----|-------------|
| GET | `/terms` | Listado paginado con filtros |
| GET | `/terms/{id}` | Detalle de un term |
| POST | `/terms/new` | Crear term |
| POST | `/terms/{id}` | Actualizar term |
| DELETE | `/terms/{id}` | Soft delete |

### Filtros (query params en GET /terms)

- `filter[namespace]=app` — Filtrar por namespace
- `filter[code]=global.save` — Coincidencia exacta por código. **Siempre combinar con `filter[namespace]`** porque el mismo code puede existir en múltiples namespaces
- `filter[search]=guardar` — Búsqueda fulltext en searchable_tags
- `perPage=100` — Resultados por página (usar 100 para sync)
- `sort[by]=code&sort[dir]=asc` — Ordenar por código ascendente
- `page=N` — Paginación

### Endpoint de Locales

| Método | URI | Descripción |
|--------|-----|-------------|
| GET | `/locales` | Locales disponibles con códigos |

### Estructura de respuesta

**GET /terms** (listado):
```json
{
  "data": [
    {
      "id": 1,
      "fields": {
        "namespace": "app",
        "code": "accounts.amortizations",
        "value": {
          "es": "Amortizaciones",
          "fr": "Amortissement",
          "pt": "Depreciação"
        },
        "created_at": "2026-03-07T06:53:35.000000Z",
        "updated_at": "2026-03-07T07:17:12.000000Z"
      }
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 100,
    "has_more_pages": true,
    "total": 1138
  }
}
```

**GET /locales**:
```json
{
  "data": [
    { "id": 1, "fields": { "code": "es", "name": "Español", "is_default": true } },
    { "id": 2, "fields": { "code": "pt", "name": "Português", "is_default": false } },
    { "id": 3, "fields": { "code": "fr", "name": "Française", "is_default": false } },
    { "id": 4, "fields": { "code": "en", "name": "English", "is_default": false } },
    { "id": 5, "fields": { "code": "it", "name": "Italiano", "is_default": false } }
  ]
}
```

**GET /terms/{id}** y **GET /terms?filter[code]+filter[namespace]** (term individual):
```json
{
  "data": {
    "id": 604,
    "fields": {
      "namespace": "app",
      "code": "global.save",
      "value": { "es": "Guardar", "en": "Save", "fr": "Sauvegarder", "pt": "Guardar" },
      "created_at": "2026-03-07T06:55:09.000000Z",
      "updated_at": "2026-03-08T08:14:44.000000Z"
    }
  }
}
```

**Importante**: `filter[code]` + `filter[namespace]` devuelve `data` como **objeto** (un term), no como array. Si no encuentra coincidencia, devuelve 404. El listado paginado (`filter[search]`, sin `filter[code]`) devuelve `data` como **array** con `meta`.

Notas sobre la respuesta:
- `value` solo contiene los idiomas que tienen traducción (no incluye claves vacías)
- Paginación (solo en listados): usar `meta.has_more_pages` para saber si hay más páginas
- El `id` del term es necesario para actualizar (`POST /terms/{id}`) y eliminar (`DELETE /terms/{id}`)

### Body para crear/actualizar (POST)

```json
{
  "fields": {
    "namespace": "app",
    "code": "global.save",
    "value": {
      "es": "Guardar",
      "fr": "Sauvegarder",
      "pt": "Salvar"
    }
  }
}
```

`value` es un objeto clave-locale. Solo incluir locales que tengan traducción. No enviar cadenas vacías.

### Ejemplos curl

**Buscar (fulltext)**:
```bash
curl -s -g -X GET "https://api2.grupodesa.app/terms?filter[search]=guardar&perPage=25&sort[by]=code&sort[dir]=asc" \
  -H "Authorization: Bearer TOKEN" \
  -H "Accept: application/json"
```

**Buscar (exacta por code — siempre con namespace)**:
```bash
curl -s -g -X GET "https://api2.grupodesa.app/terms?filter[code]=global.save&filter[namespace]=app" \
  -H "Authorization: Bearer TOKEN" \
  -H "Accept: application/json"
```

**Obtener por ID**:
```bash
curl -s -g -X GET "https://api2.grupodesa.app/terms/487" \
  -H "Authorization: Bearer TOKEN" \
  -H "Accept: application/json"
```

**Crear**:
```bash
curl -s -g -X POST "https://api2.grupodesa.app/terms/new" \
  -H "Authorization: Bearer TOKEN" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"fields":{"namespace":"app","code":"global.save","value":{"es":"Guardar","en":"Save"}}}'
```

**Actualizar** (requiere ID del term):
```bash
curl -s -g -X POST "https://api2.grupodesa.app/terms/42" \
  -H "Authorization: Bearer TOKEN" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"fields":{"namespace":"app","code":"global.save","value":{"es":"Guardar","en":"Save","fr":"Sauvegarder","pt":"Salvar"}}}'
```

**Eliminar** (requiere ID del term):
```bash
curl -s -g -X DELETE "https://api2.grupodesa.app/terms/42" \
  -H "Authorization: Bearer TOKEN" \
  -H "Accept: application/json"
```

**Locales**:
```bash
curl -s -g -X GET "https://api2.grupodesa.app/locales" \
  -H "Authorization: Bearer TOKEN" \
  -H "Accept: application/json"
```

## Formatos de archivo

### Frontend (React/i18next)

- Ruta: `packages/i18n/src/locales/{lang}/translations.json`
- JSON plano, claves dot-notation, ordenadas alfabéticamente
- Indentación: 2 espacios, trailing newline
- Crear directorio `{lang}/` si no existe
- Ejemplo:

```json
{
  "accounts.amortizations": "Amortizaciones",
  "activities.featured": "Destacadas",
  "activities.goal-notes": "Deja aquí tus notas sobre {{goal}}"
}
```

**Importante para frontend**: Al añadir un nuevo idioma (ej. `it`), también hay que registrarlo en `packages/i18n/src/index.js` (import + resources + supportedLngs) y en las configuraciones de i18n de web y mobile. Informar al usuario de este paso.

### Backend (Laravel)

- Ruta: `resources/lang/{lang}/{namespace}.php`
- PHP `return array(...)` plano con claves dot-notation (incluido notifications, siempre aplanado)
- Ordenadas alfabéticamente, comillas dobles, `=>` alineados
- Escapar `"` → `\"` y `\` → `\\` en valores
- Trailing newline
- Crear directorio `{lang}/` si no existe
- Ejemplo:

```php
<?php

return array(
    "activities.featured"   => "Destacadas",
    "activities.goal-notes" => "Deja aquí tus notas sobre {{goal}}",
);
```

Alineación: encontrar la clave más larga del archivo, rellenar con espacios antes de `=>` para que todos queden alineados.

## Ortografía — OBLIGATORIO

Todo el contenido en español debe tener **acentos correctos**. Esto es un requisito bloqueante: no envíes ningún POST sin haber verificado la ortografía del campo `value.es`.

Palabras que frecuentemente se escriben sin tilde por error:

| Incorrecto | Correcto |
|-----------|----------|
| topologia | topología |
| fisico/a | físico/a |
| tuneles | túneles |
| funcion | función |
| publica | pública |
| logica | lógica |
| parametro | parámetro |
| configuracion | configuración |
| informacion | información |
| gestion | gestión |
| autenticacion | autenticación |
| conexion | conexión |
| operacion | operación |
| direccion | dirección |
| descripcion | descripción |
| sincronizacion | sincronización |
| documentacion | documentación |
| numero | número |
| codigo | código |
| metodo | método |
| unico/a | único/a |
| tecnologia | tecnología |
| logistico/a | logístico/a |
| analisis | análisis |
| politica | política |
| automatico/a | automático/a |
| vehiculo | vehículo |
| catalogo | catálogo |
| periodo | período |
| almacen | almacén |
| tambien | también |
| asi | así |
| mas (adverbio) | más |
| actua | actúa |

**Antes de cada POST**, revisa `value.es` y corrige cualquier palabra sin tilde. Solo aplicar al locale `es`.

## Modo de operación

Analiza lo que pide el usuario con `$ARGUMENTS`:

- **"sincroniza"**, **"sync"**, **"actualiza archivos"**: Modo sync (pull API → archivos locales)
- **"busca X"**, **"search X"**: Modo búsqueda
- **"crea ..."**, **"crear ..."**, **"add ..."**, **"nuevo ..."**: Modo crear
- **"actualiza ..."**, **"update ..."**, **"modifica ..."**: Modo actualizar
- **"elimina ..."**, **"delete ..."**, **"borra ..."**: Modo eliminar

Si un POST devuelve error 403, informa al usuario de que no tiene permisos. Si devuelve 422, muestra los detalles del error de validación.

## Flujo: Crear/Actualizar term

1. Detectar proyecto
2. Extraer token
3. Determinar namespace: frontend → siempre `app`; backend → inferir del contexto o preguntar, default `app`
4. **Buscar si el term ya existe**: `GET /terms?filter[code]={code}&filter[namespace]={ns}`. Devuelve 0 o 1 resultado. Si existe, usar su `id` para actualizar; si no existe, crear
5. Construir el objeto `value`: incluir solo los locales con traducción conocida. No enviar cadenas vacías
6. **Spell-check** de `value.es` contra la tabla de ortografía
7. POST a `/terms/new` (crear) o `/terms/{id}` (actualizar con merge de valores existentes)
8. Verificar respuesta exitosa
9. **Actualizar archivos locales** si estamos en un proyecto:
   - Leer el archivo, añadir/actualizar la clave, reordenar alfabéticamente, escribir
   - Frontend: actualizar `translations.json` de cada idioma que tenga valor
   - Backend: actualizar `{namespace}.php` de cada idioma que tenga valor

Para actualizar: GET `/terms/{id}` para obtener valores actuales, mergear los nuevos valores sobre los existentes, luego POST con el resultado completo.

## Flujo: Eliminar term

1. Detectar proyecto
2. Extraer token
3. Buscar el term por código: `GET /terms?filter[code]={code}&filter[namespace]={ns}` para obtener el `id`
4. Confirmar con el usuario antes de eliminar (mostrar code y valores actuales)
5. `DELETE /terms/{id}`
6. Eliminar la clave de los archivos locales si estamos en un proyecto

## Flujo: Sync (pull desde API)

Requiere estar en un proyecto (frontend o backend). La API es la fuente de verdad: los archivos locales se sobreescriben completamente.

1. Detectar proyecto (obligatorio)
2. Extraer token
3. GET `/locales` para obtener todos los idiomas disponibles

### Sync frontend

4. Fetch todos los terms de namespace `app` con paginación (ver sección Paginación)
5. Para cada idioma obtenido de `/locales`:
   - Construir JSON: `{ "code": value[lang] }` para cada term que tenga valor en ese idioma
   - Si no hay terms para ese idioma, no crear el archivo
   - Ordenar claves alfabéticamente
   - Crear directorio `packages/i18n/src/locales/{lang}/` si no existe
   - Escribir en `packages/i18n/src/locales/{lang}/translations.json`
6. Si se crea un directorio de idioma nuevo, informar al usuario de que debe registrarlo en `packages/i18n/src/index.js`

### Sync backend

4. Para cada namespace en [app, export, notifications, paper-catalog]:
   - Fetch todos los terms con paginación (ver sección Paginación)
   - Para cada idioma obtenido de `/locales`:
     - Recoger terms que tengan valor para este idioma
     - Si hay terms: crear directorio `resources/lang/{lang}/` si no existe, generar PHP y escribir en `resources/lang/{lang}/{namespace}.php`
     - Si no hay terms para este idioma+namespace: no crear el archivo

5. Mostrar resumen: cuántos terms sincronizados, cuántos archivos escritos, qué idiomas

### Paginación

Usar un script python3 para fetch paginado eficiente. Ejemplo para un namespace:

```bash
python3 -c "
import json, subprocess

def fetch_all(namespace, token):
    all_terms = []
    page = 1
    while True:
        r = subprocess.run(['curl', '-s', '-g',
            f'https://api2.grupodesa.app/terms?filter[namespace]={namespace}&perPage=100&sort[by]=code&sort[dir]=asc&page={page}',
            '-H', f'Authorization: Bearer {token}',
            '-H', 'Accept: application/json'], capture_output=True, text=True)
        data = json.loads(r.stdout)
        all_terms.extend(data['data'])
        if not data['meta']['has_more_pages']:
            break
        page += 1
    return all_terms

token = 'TOKEN_AQUI'
terms = fetch_all('app', token)
print(json.dumps(terms, ensure_ascii=False))
"
```

Adaptar el script según el flujo (frontend genera JSON, backend genera PHP). Procesar todos los idiomas en un solo script para evitar múltiples ejecuciones.

## Flujo: Búsqueda

1. Extraer token
2. `GET /terms?filter[search]={query}&perPage=25&sort[by]=code&sort[dir]=asc`
3. Mostrar resultados en tabla con todos los idiomas que tengan valor:

```
| Namespace | Code | ES | FR | PT | EN | IT |
|-----------|------|----|----|----|----|----|
| app | global.save | Guardar | Sauvegarder | Salvar | Save | — |
```

Usar `—` para idiomas sin traducción.

4. Si `meta.has_more_pages` es true, indicar al usuario y preguntar si quiere ver más

## Reglas importantes

- **API es la fuente de verdad** — sync siempre sobreescribe archivos locales completamente
- **NUNCA tocar** auth.php, validation.php, passwords.php, pagination.php, errors.php
- **Spell-check** obligatorio para `value.es` antes de cada POST
- **Buscar antes de crear** — usar `filter[code]` + `filter[namespace]` para verificar si el term ya existe. Nunca usar solo `filter[code]` sin namespace
- **Error handling**: 422 → mostrar errores de validación; 403 → informar permisos insuficientes
- **Namespace por defecto**: `app` si el usuario no especifica otro
- **Idiomas dinámicos**: siempre obtener de `/locales`, no hardcodear. Crear directorios y archivos para todos los idiomas que tengan datos
