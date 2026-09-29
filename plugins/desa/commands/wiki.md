---
description: Consultar o documentar en la wiki interna de Grupo Desa. Usar cuando se pregunta qué dice la wiki sobre algo o se pide crear o actualizar una página; cada escritura va con vista previa y un sí explícito
argument-hint: [qué consultar, documentar o actualizar]
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py token-status), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py workdir), Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py GET:*), Read(/${CLAUDE_PLUGIN_ROOT}/references/ortografia.md)
---

# Wiki — Sistema de documentación interna

Consulta la wiki interna de Grupo Desa y, si el usuario tiene permisos, crea o actualiza documentos con la API REST. Una escritura publica al momento para todos los que ven la página, así que ninguna sale sin vista previa y un sí del usuario.

## Modo de operación

Analiza lo que pide el usuario con $ARGUMENTS:

- **Consulta** (buscar, leer, explorar, «qué dice la wiki sobre…»): solo lecturas.
- **Documentar** (crear, actualizar, documentar, escribir): lecturas para explorar y POST para crear o actualizar.

Gestión de errores de la API:

- **401**: Token caducado o inválido → pedir uno nuevo con el procedimiento de `NO_TOKEN` de «Configuración» y reintentar
- **403**: Autenticado pero sin permisos de escritura → informa al usuario y ofrece mostrar el contenido que habría enviado para que lo copie manualmente
- **404**: Documento no encontrado → verifica el ID y navega desde root para encontrar el correcto
- **422**: Error de validación → lee el campo `errors` de la respuesta JSON para identificar el campo problemático
- **5xx**: Error del servidor → informa al usuario e invita a reintentar en unos instantes

## Configuración

Todas las llamadas pasan por el cliente del plugin, que lee el token por su cuenta y solo lo envía a `api2.grupodesa.app`:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py token-status
```

- `OK …` → seguir. El token lo lee el script: no imprimirlo, no ponerlo en ningún comando y no pedirlo si ya hay uno. El que ya estuviera en la clave `desa_wiki_token` de `~/.claude/settings.json` sigue valiendo.
- `NO_TOKEN`, `TOKEN_INVALIDO` o un 401 → pedir al usuario que copie su token de la wiki al portapapeles y lo guarde con esta orden en la propia sesión. El `!` delante hace que el token no pase por la conversación:

  ```
  ! pbpaste | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py set-token --stdin
  ```

  Queda en `~/.config/desa/api-token` con permisos 600. Fuera de macOS, que ejecute en su terminal `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py set-token`, que lo pide por teclado. Si aun así pega el token en el chat, guardarlo con Write en `~/.config/desa/api-token`, ejecutar `chmod 600 ~/.config/desa/api-token` y avisarle de que queda en el historial de la sesión.

  Si `token-status` dice `OK DESA_API_TOKEN`, el token sale de esa variable de entorno, que tiene prioridad: ante un 401, pedir al usuario que la actualice o la quite, porque `set-token` no la cambia.

Sin token válido no se sigue. El mismo token sirve para `/desa:translations`.

## API

- **Base URL**: `https://api2.grupodesa.app` (sin prefijo `/api/`). La pone el cliente.
- **Lecturas**: las rutas de esta skill se escriben como en la API (`/documents?filter[document]={id}&include=documents`), pero al llamar al cliente la ruta va sin `?` y cada parámetro en su `--param`: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py GET /documents --param 'filter[document]=34' --param include=documents --param perPage=100`. Con `?` o `&` en la ruta, el shell la parte o la rompe, y el texto libre (espacios, tildes, `#`) solo se codifica bien en `--param`. El cliente solo admite `/documents…`, `/terms…` y `/locales`.
- **Escrituras**: el body (sin el contenido, al actualizar; ver los pasos 6 y 7 del flujo de documentar) se escribe con Write en un fichero JSON del directorio privado que da `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py workdir`, y se envía con `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py POST /documents/{id} --body {fichero}`. Nunca con el JSON dentro del comando: el shell interpreta `$`, backticks y comillas, y corrompe sin avisar el contenido técnico. El DELETE es `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py DELETE /documents/{id}`.
- **Respuesta**: el cliente imprime `{"status": N, "body": …}`. Sale con 0 si la respuesta es 2xx, 1 si la API devuelve un error (ver la tabla de arriba), 2 sin token o con un token inválido, 3 si hay error de red y 64 si la orden está mal (p. ej. una ruta no permitida). No sigue redirecciones: un 3xx sale como error.

### Endpoints de lectura

| Método | URI | Descripción |
|--------|-----|-------------|
| GET | `/documents/root?include=documents` | Root con hijos directos |
| GET | `/documents?filter[document]={id}&include=documents` | Hijos de un documento |
| GET | `/documents/{id}?include=document` | Documento con cadena de padres (breadcrumb) |
| GET | `/documents?filter[search]=texto` | Buscar por tags |

### Endpoints de escritura

| Método | URI | Descripción |
|--------|-----|-------------|
| POST | `/documents/new` | Crear documento |
| POST | `/documents/{id}` | Actualizar documento |
| DELETE | `/documents/{id}` | Soft delete |

Las respuestas POST devuelven el documento completo. Extraer el campo `id` del body para usarlo en la verificación posterior (`GET /documents/{id}?include=teams,roles`, paso 8 del flujo de documentar).

**DELETE requiere confirmación explícita**: antes de ejecutar cualquier DELETE, mostrar al usuario el título del documento y pedir confirmación. Aunque es soft delete (recuperable por administración), el usuario debe aprobarlo explícitamente.

### Paginación

Los endpoints GET devuelven resultados paginados, por defecto solo 5 por página. En búsquedas y listados de hijos, añadir siempre `&perPage=100` y mirar `meta.has_more_pages`: con 5 por página, un documento que existe pero cae en la página 2 se toma por inexistente y se crea un duplicado. Ejemplo:

```
GET /documents?filter[document]={id}&include=documents&perPage=100
```

### Includes disponibles

`document` (padre recursivo hasta root), `documents` (hijos), `teams`, `roles`, `creator`

No usar `status`: los documentos no tienen estado y ese include devuelve 500. El estado de publicación va en `fields.is_published`.

## Formato de petición (crear/actualizar)

Ejemplo al crear un documento. `TEAMS_DEL_PADRE` y `ROLES_DEL_PADRE` son los IDs que devuelve `GET /documents/{padre}?include=teams,roles`:

```json
{
  "fields": {
    "document_id": 5,
    "title": "Nombre del documento",
    "description": "Breve resumen de lo que contiene la página",
    "content": "Contenido en markdown...",
    "searchable_tags": "palabra1, palabra2, palabra3",
    "is_published": true
  },
  "teams": [TEAMS_DEL_PADRE],
  "roles": [ROLES_DEL_PADRE]
}
```

- `document_id`: ID del padre (obligatorio)
- `description`: resumen breve del contenido (max 255 caracteres). Siempre rellenarlo
- `content`: markdown libre, puede ser null
- `searchable_tags`: palabras clave separadas por coma que facilitan la búsqueda fulltext. El título se añade automáticamente, no hace falta repetirlo. Incluir: nombres de tecnologías, conceptos clave, siglas, términos de negocio relevantes. **Siempre rellenarlo** al crear o actualizar un documento. El GET no lo devuelve: al actualizar, reescribirlo completo (si se omite, se regenera solo a partir del título y la descripción)
- `is_published`: al crear, `true` salvo que el usuario pida explícitamente guardar un borrador. Al actualizar, conservar el valor que tenía (si se omite, pasa a `false`)
- `teams` y `roles`: arrays de IDs (el `id` de cada objeto que devuelve `?include=teams,roles`). `roles` son los roles que pueden ver la página: con `roles: []` solo la ve super-admin. `teams` la restringe además por equipo: con `teams: []` queda abierta a todos los equipos. Al crear, copiar los dos del padre salvo que el usuario pida otra visibilidad
- Root (id=1) no se puede editar por la API

**Al actualizar se conserva la visibilidad.** Leer antes con `GET /documents/{id}?include=teams,roles` y enviar en `teams` y `roles` los IDs que devuelva esa lectura, y en `document_id` e `is_published` los valores leídos. Motivo: el POST sustituye `teams` y `roles` por lo que se envía. Enviar `[]` borraría los equipos y roles de la página, y dejaría de verla todo el que no sea super-admin; quien escribe siempre lo es (la API lo exige), así que no lo notaría. Y `true` publicaría un borrador. Si `fields.is_public` es `false` pero `teams` viene vacío (sus equipos se han borrado), no enviar el POST sin avisar antes al usuario y preguntarle qué equipos poner: cualquier POST la dejaría abierta a todos los equipos. Solo se cambian visibilidad, padre o estado de publicación si el usuario lo pide explícitamente.

## Formato del contenido

- Markdown estándar
- **No incluir el título** en el content (ya está en `fields.title`)
- Idioma: **español de España**. No usar modismos latinoamericanos
- Enlaces entre documentos: `[título visible](document:{id})`
- No usar emojis

## Ortografía

Antes de cada POST, revisar el texto completo de `title`, `description` y `content` con `${CLAUDE_PLUGIN_ROOT}/references/ortografia.md`, por bloques si es largo. La tabla recoge los errores más frecuentes y las formas que dependen del contexto (*publica*, *numero*), pero se revisa todo el texto: la wiki llegó a publicar páginas enteras sin tildes.

## Convenciones de contenido

- Empezar con una frase descriptiva breve
- Usar `---` como separador después de la descripción
- Secciones con `##`
- Si el documento tiene hijos, listarlos como enlaces `[título](document:{id})` con descripción debajo
- Contenido técnico: tablas markdown, bloques de código con lenguaje

## Flujo de trabajo para consultas

Si la sesión tiene el conector de la wiki (herramientas `search_wiki`, `get_wiki_document`, `get_wiki_structure` y `list_wiki_children`), las consultas pueden ir por él; si no está o falla, por la API REST. La lectura previa a una actualización va siempre por REST, porque necesita `include=teams,roles`.

1. **Buscar**: `GET /documents?filter[search]=texto&perPage=100` — si la consulta es sobre un concepto, sistema o proceso concreto, empezar aquí
2. **Si la búsqueda no es fructífera o la consulta es exploratoria**: `GET /documents/root?include=documents` para ver la estructura general
3. **Navegar**: `GET /documents?filter[document]={id}&include=documents&perPage=100` para profundizar en un nodo
4. **Leer**: `GET /documents/{id}` para ver el contenido completo
5. **Resumir**: Presenta la información al usuario de forma clara y concisa

## Flujo de trabajo para documentar

1. **Buscar primero**: `GET /documents?filter[search]=palabras_clave&perPage=100` — verificar si ya existe documentación sobre el tema. Si existe, continuar como **actualización** del documento encontrado; si no, continuar como **creación**
2. **Explorar**: `GET /documents/root?include=documents` para entender la estructura y determinar dónde debe vivir el nuevo contenido
3. **Navegar**: `GET /documents?filter[document]={id}&include=documents&perPage=100` para localizar el nodo padre correcto
4. **Leer**: `GET /documents/{id}` — obligatorio antes de cualquier escritura. Al actualizar: `GET /documents/{id}?include=teams,roles`, para preservar el contenido y la visibilidad existentes. Al crear: leer el padre con `?include=teams,roles` para entender el contexto y heredar su visibilidad. En los dos casos, si `roles` viene vacío (la página solo la ve super-admin, probablemente porque se creó con una versión anterior de esta skill), o si `fields.is_public` es `false` y `teams` viene vacío (sus equipos se han borrado), no copiar esa visibilidad en silencio: avisar al usuario y preguntar qué equipos y roles poner. Quien escribe siempre es super-admin, así que no lo notaría
5. **Redactar y revisar la ortografía** del texto completo (sección «Ortografía»), con lo visto en la sesión (sección «Fuentes»).
6. **Vista previa y un sí explícito**, igual que con el DELETE: un POST publica al momento para quien tenga acceso y, al actualizar, sustituye la página entera. La vista previa incluye:
    - acción (crear o actualizar), padre (id y título), título, `description`, `searchable_tags`, `is_published` y visibilidad, con los nombres de equipos y roles;
    - al crear, el contenido completo. Al actualizar, el diff real frente a la API, no frente a una copia hecha a mano:
        1. guardar el contenido actual dos veces, con `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/desa_api.py GET /documents/{id} --param include=teams,roles --save-content actual.md` y lo mismo con `--save-content nuevo.md` (quedan en el directorio de `workdir`, con los saltos de línea tal cual). Si responde con `ERROR=`, no seguir: el contenido no se ha guardado;
        2. aplicar los cambios a `nuevo.md` con Edit;
        3. enseñar `diff -u {workdir}/actual.md {workdir}/nuevo.md`;
    - las fuentes de cada regla documentada, con `fichero:línea`, y lo que queda fuera por no haberse podido confirmar.
7. **Enviar el POST** tras el sí:
    - **Al crear**: `POST /documents/new` con todos los campos, `document_id` del padre (paso 3) incluido, y con `teams` y `roles` del padre. Si es documentación de lógica de negocio, seguir también «Referencias cruzadas» para enlazarla desde el eje de negocio y actualizar el índice de la aplicación.
    - **Al actualizar**: el POST sustituye el documento entero, y un campo omitido o `null` borra su contenido. Justo antes, volver a leer el documento y comparar `fields.updated_at` con el del paso 4: si ha cambiado, alguien lo ha editado mientras tanto (el backend no tiene bloqueo optimista, y el POST machacaría esa edición). En ese caso no enviar: enseñar qué ha cambiado, rehacer los cambios sobre la versión nueva y volver al paso 6. Si no ha cambiado, `POST /documents/{id}` con el body completo leído en el paso 4 más los cambios, con `document_id`, `is_published`, `teams` y `roles` tal como estaban, y el contenido con `--content-from nuevo.md`, para que los párrafos que no se tocan viajen tal cual.
8. **Verificar**: `GET /documents/{id}?include=teams,roles` para confirmar que el resultado es el esperado: al actualizar, que `teams`, `roles` y `fields.is_public` no han cambiado; al crear, que `roles` no ha quedado vacío salvo que el usuario lo pidiera.
9. **Resumen al usuario**: qué se ha creado o cambiado (id y título), las fuentes con `fichero:línea` y lo que ha quedado fuera.

## Estructura de la wiki

La wiki tiene dos ejes principales. Los ids de este apartado se anotaron en febrero de 2026: antes de usar uno, comprobar que el título del documento coincide.

### Eje de negocio (cómo funciona la empresa)

```
Wiki (1)
├── General (2)
├── Flujo de Ventas (3) → Marketing, Ventas, SAC, Centro Logístico, Transporte, Devoluciones
├── Flujo de Aprovisionamiento (4) → Producto, Proveedor, Compras, Planificación, Transporte
└── Capa Digital (5) → Sistemas, Herramientas, Apps, Datos, Analítica
```

### Eje técnico (cómo funciona el sistema)

Cada aplicación bajo Capa Digital puede tener su propia sección de Lógica de Negocio. Ejemplo actual:

```
Desaverse Backend (27)
├── Documentación Técnica
│   └── Kernel (28) → Middleware, Tareas, Errores, Providers
└── Lógica de Negocio (33) → Reglas del sistema en lenguaje no técnico
    └── Pedidos (34)
    └── ... (futuros dominios)
```

Otras aplicaciones (Desaverse Frontend, Desa Connect, etc.) pueden seguir el mismo patrón cuando tengan lógica de negocio propia que documentar.

### Referencias cruzadas

La documentación de lógica de negocio vive bajo la **aplicación correspondiente > Lógica de Negocio** (fuente de verdad), pero debe enlazarse desde las páginas del eje de negocio para que perfiles no técnicos la encuentren.

**Al crear documentación de lógica de negocio:**

1. **Identificar** en qué aplicación reside la lógica (backend, frontend, Desa Connect, etc.)
2. **Crear** la página bajo la sección Lógica de Negocio de esa aplicación, con lenguaje no técnico, sin código
3. **Enlazar** desde la página del flujo de negocio correspondiente (Ventas, Centro Logístico, etc.). Es una actualización: seguir el paso 7 («Al actualizar») y conservar su visibilidad
4. **Actualizar** la página índice de Lógica de Negocio de la aplicación con el nuevo enlace, también como actualización

**Ejemplo**: La lógica de pedidos (id: 34) está bajo Desaverse Backend > Lógica de Negocio (id: 33), y Ventas (id: 11) la enlaza como referencia cruzada.

**Al crear documentación técnica:**
- Va bajo la sección de Documentación Técnica de la aplicación correspondiente
- No necesita referencia cruzada desde los flujos de negocio

### Formato de lógica de negocio

Las páginas de Lógica de Negocio están orientadas a perfiles no técnicos (dirección, logística, comercial):

- Lenguaje de negocio, sin código ni nombres de funciones
- Explicar qué decide el sistema, por qué y en qué condiciones
- Usar tablas para comparar opciones/modos
- Usar ejemplos numéricos concretos cuando ayuden a entender
- Estructura: descripción breve → separador → secciones por regla

## Fuentes

Documentar solo lo que se ha visto en esta sesión: el código fuente del proyecto, su configuración y estructura, o lo que diga el usuario. Lo que no se ha podido confirmar se pregunta o se deja fuera, y se dice qué ha quedado fuera. Las referencias `fichero:línea` van en la vista previa y en el resumen, no en las páginas de lógica de negocio, que leen perfiles no técnicos.
