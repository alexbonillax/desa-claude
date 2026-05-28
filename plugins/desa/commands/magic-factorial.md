---
description: Crear, corregir y cuadrar fichajes en Factorial vía GraphQL interna usando cookies del navegador
argument-hint: [rango, ej. "desde 1 enero hasta ayer"]
allowed-tools: Bash(curl:*), Bash(python3:*), Bash(mkdir:*), Bash(chmod:*), Bash(cat:*), Bash(sleep:*), Read, Write, Edit
---

# Magic Factorial — Fichajes automatizados

Crear, modificar y cuadrar fichajes (attendance shifts) en Factorial usando la **API GraphQL interna**, autenticada con cookies del navegador del usuario. Soporta crear días faltantes, reescribir días incorrectos y cuadrar el balance mensual a cero.

> **Importante**: Esta es la API interna de Factorial (`api.factorialhr.com/graphql`), no la API pública. Funciona porque reutilizamos la sesión web del usuario. NO es estable contractualmente — Factorial puede cambiar el schema. Para integraciones de producción usar la API pública con OAuth/API Key.

## Paso 1: Obtener cookies del navegador

Pide al usuario que copie el header de cualquier request a `api.factorialhr.com` desde DevTools (Network → cualquier request → Headers → Request Headers en formato "view source"). Acepta el bloque entero pegado tal cual, incluyendo todas las líneas `:authority`, `:method`, `cookie`, etc.

**No continúes sin que el usuario haya pegado el header completo.** Avisa que el JWT `_factorial_id` dura ~2h, así que tendrá que volver a pegarlo cuando caduque.

Parsear y guardar el valor de `cookie` y el `eid` (employee id) extraído del JWT:

```bash
mkdir -p /tmp/factorial-magic
```

Usar Write para guardar el bloque pegado en `/tmp/factorial-magic/header.txt`, luego:

```bash
python3 << 'EOF'
import re, json, base64
raw = open('/tmp/factorial-magic/header.txt').read()
# Extract cookie value: line after 'cookie\n' OR 'cookie:' inline
m = re.search(r'^cookie[:\s]+\n?([^\n]+)', raw, re.MULTILINE)
if not m:
    # Try multi-line capture
    m = re.search(r'cookie\n([^\n]+)', raw)
cookie = m.group(1).strip()
open('/tmp/factorial-magic/cookies.txt', 'w').write(cookie)

# Decode _factorial_id JWT payload to get employeeId (eid)
jwt_m = re.search(r'_factorial_id=([^;]+)', cookie)
parts = jwt_m.group(1).split('.')
# pad base64
pad = '=' * (-len(parts[1]) % 4)
payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad))
print(f"Employee ID (eid): {payload.get('eid')}")
print(f"JWT exp: {payload.get('exp')} (cookies caducan ~2h)")
open('/tmp/factorial-magic/employee_id.txt', 'w').write(str(payload.get('eid')))
EOF
```

Si el parse falla, pídele al usuario que vuelva a pegar el header completo.

## Paso 2: Validar auth

```bash
COOKIE=$(cat /tmp/factorial-magic/cookies.txt)
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST 'https://api.factorialhr.com/graphql?T' \
  -H "Cookie: $COOKIE" -H "Content-Type: application/json" \
  -H "Origin: https://app.factorialhr.com" -H "Referer: https://app.factorialhr.com/" \
  -H "x-factorial-bigint-support: true" -H "x-factorial-origin: web" \
  -d '{"operationName":"T","variables":{},"query":"query T { __schema { queryType { name } } }"}'
```

- `200` → seguir
- `401` → cookies caducadas, pedir al usuario que las pegue de nuevo

## Headers obligatorios (siempre)

Para cada request a Factorial:

```
Cookie: <todo el string>
Content-Type: application/json
Origin: https://app.factorialhr.com
Referer: https://app.factorialhr.com/
x-factorial-bigint-support: true
x-factorial-origin: web
```

## Paso 3: Recopilar contexto

Cargar en paralelo (una sola query GraphQL combinada para minimizar peticiones):

```bash
EMP=$(cat /tmp/factorial-magic/employee_id.txt)
START="2026-01-01"  # ajustar al rango pedido
END="2026-05-25"

QUERY='query Ctx($employeeIds:[ID!]!,$startOn:ISO8601Date!,$endOn:ISO8601Date!){
  attendance{
    shiftsConnection(employeeIds:$employeeIds,startOn:$startOn,endOn:$endOn,first:500){
      nodes{ id date clockIn clockOut minutes workable }
    }
    estimatedTimesConnection(employeeIds:$employeeIds,startOn:$startOn,endOn:$endOn,first:500){
      nodes{ date contractMinutes expectedMinutes }
    }
    balancesConnection(employeeIds:$employeeIds,startOn:$startOn,endOn:$endOn,first:500){
      nodes{ date dailyBalance }
    }
    periodsConnection(employeeIds:$employeeIds,startOn:$startOn,endOn:$endOn,first:20){
      nodes{ year month state }
    }
  }
  holidays{
    companyHolidaysConnection(employeeIds:$employeeIds,startAt:$startOn,endAt:$endOn,first:50){
      nodes{ date }
    }
  }
}'
```

Campos clave:

| Campo | Significado |
|---|---|
| `shiftsConnection.minutes` | Duración de un shift (clockOut - clockIn) |
| `shiftsConnection.workable` | `true` = trabajo, `false` = **pausa** |
| `estimatedTimesConnection.expectedMinutes` | Lo que se ESPERA fichar ese día (incluye horarios reducidos por Semana Santa, vísperas, etc.) |
| `estimatedTimesConnection.contractMinutes` | Horas contractuales del día. `0` = festivo o no laborable |
| `balancesConnection.dailyBalance` | Delta del día considerando ausencias. Es la métrica para cuadrar a 0 mensual |
| `periodsConnection.state` | Estado del periodo mensual. Si `state == "closed"` no se puede tocar |

## Detección de festivos / reducidos / no laborables

**No hardcodear festivos.** Usar el resultado de la API:

- `contractMinutes == 0` → no laborable (festivo, fin de semana, vacaciones)
- `expectedMinutes > 0 && contractMinutes > 0` → laborable, duración objetivo = `expectedMinutes`
- Los valores típicos de `expectedMinutes` son `510` (8h30, L-J normal) y `390` (6h30, V o reducido por Semana Santa/víspera festivo)

## Paso 4: Estructura de fichajes esperada

La regla legal: **>6h trabajadas requiere 15min de pausa obligatoria**. Excepción: días de 6h30 no necesitan pausa.

| Tipo de día | Estructura | Total worked |
|---|---|---|
| L-J 8h30 (`expectedMinutes=510`) | **3 fichajes**: trabajo + pausa + trabajo | 510min |
| V o reducidos 6h30 (`expectedMinutes=390`) | **1 fichaje** sin pausa | 390min |
| Festivo / vacaciones (`contractMinutes=0`) | Sin fichaje | 0 |

Patrón horario L-J recomendado:
```
TRABAJO  08:00 ± 5min  →  14:00 ± 3min   (6h ≈ 360min)
PAUSA    14:00         →  14:15           (15min, workable:false)
TRABAJO  14:15         →  16:45 ± 3min   (2h30 ≈ 150min)
```

Patrón V y reducidos:
```
TRABAJO  08:00 ± 5min  →  14:30 ± 3min   (6h30 = 390min)
```

## Paso 5: Mutations

### Crear shift

```
createAttendanceShift(
  employeeId: ID!
  date: ISO8601Date!
  referenceDate: ISO8601Date!
  clockIn: ISO8601DateTime
  clockOut: ISO8601DateTime
  workable: Boolean       # false para pausas
  source: AttendanceEnumsShiftSourceEnum  # "desktop"
  timeSettingsBreakConfigurationId: ID    # opcional
)
```

### Actualizar shift

```
updateAttendanceShift(
  id: ID!
  date: ISO8601Date!
  referenceDate: ISO8601Date!
  clockIn: ISO8601DateTime
  clockOut: ISO8601DateTime
)
```

### Borrar shift

```
deleteAttendanceShift(id: ID!)
```

## ⚠️ Trampas críticas aprendidas

### 1. Timezone bug

`createAttendanceShift` NO convierte timezone (guarda la hora tal cual). `updateAttendanceShift` SÍ convierte CET→UTC (restando 1h). **Solución: usar SIEMPRE `+00:00`** en clockIn/clockOut, con la hora que quieres que se vea:

```
✅ "clockIn": "2026-04-15T08:00:00+00:00"
❌ "clockIn": "2026-04-15T08:00:00+01:00"  (update lo guardará como 07:00)
```

### 2. WorkedTime tiene delay de procesamiento

Tras un `create`, el `effectiveWorkedMinutes` puede tardar minutos en recalcularse. Solución: hacer un `update` no-op (mismo clockIn/clockOut) al shift recién creado para forzar recálculo inmediato. Llámalo "touch pass".

```python
# Pseudocódigo
for shift in created_shifts:
    update_shift(shift.id, shift.clockIn, shift.clockOut, ...)  # no-op
```

### 3. Pausas son shifts con `workable: false`

NO son un campo separado. Son shifts normales con `workable: false`. Ejemplo de día L-J completo:

```
Shift 1: 08:00-14:00 workable=true   (trabajo, 360min)
Shift 2: 14:00-14:15 workable=false  (PAUSA, 15min)
Shift 3: 14:15-16:45 workable=true   (trabajo, 150min)
```

`effectiveWorkedMinutes` = 510 (la pausa no cuenta).

### 4. Periodos cerrados

Si `periodsConnection[mes].state == "closed"` para un mes, **no tocar nada** de ese mes (ni crear ni borrar). Saltarlo y avisar al usuario.

### 5. clockIn devuelto con fecha "today"

Al leer un shift, la API devuelve `clockIn: "2026-XX-XXTHH:MM:00+00:00"` donde la fecha es el día actual del servidor (no la fecha real del shift). Esto es solo display — el campo `date` tiene la fecha real. Al actualizar, usar `date` para reconstruir el clockIn.

## Paso 6: Generación del plan

```python
import random
from datetime import date, timedelta
random.seed(42)

def generate_plan(expected_by_date, contract_by_date, existing_shifts_by_date, start, end):
    plan = []
    d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    while d <= end_d:
        iso = d.isoformat()
        em = expected_by_date.get(iso, 0)
        cm = contract_by_date.get(iso, 0)
        # Skip non-working days
        if d.weekday() >= 5 or cm == 0 or em == 0:
            d += timedelta(days=1); continue
        plan.append({
            'date': iso,
            'target_min': em,
            'needs_break': em > 390,  # >6h30 needs break
            'existing_ids': [s['id'] for s in existing_shifts_by_date.get(iso, [])]
        })
        d += timedelta(days=1)
    return plan
```

## Paso 7: Ejecución por bloques

**No ejecutes todo de golpe.** Procesa mes a mes. Para cada mes:

1. **Confirma con el usuario** el alcance antes de ejecutar (creates, updates, deletes).
2. Por cada día del plan:
   - Borrar shifts existentes (`deleteAttendanceShift`).
   - Si `needs_break`: crear shift mañana (workable=true), crear pausa (workable=false), crear shift tarde (workable=true).
   - Si no: crear 1 shift único.
3. Touch pass: re-update cada shift creado para forzar recálculo de `workedTime`.
4. Verificar `effectiveWorkedMinutes` de cada día contra `target_min`.

Espaciar las peticiones con `time.sleep(0.1)` entre cada una para evitar rate limit silencioso.

## Paso 8: Cuadrar balance mensual a 0

Después de ejecutar, consultar `balancesConnection.dailyBalance` y sumar por mes:

```python
from collections import defaultdict
month_balance = defaultdict(float)
for n in nodes:
    if n['date'] > END: continue  # ignorar días futuros del mes
    month_balance[n['date'][:7]] += float(n['dailyBalance'])
```

Para cada mes con delta != 0:
- Coger un día L-J cualquiera del mes.
- Hacer update del shift de tarde sumando/restando los minutos del delta al `clockOut`.
- Esperar ~5s y re-verificar.

Puede requerir 2-3 iteraciones por recálculos asíncronos. Aceptar ±0min como cuadrado.

## Paso 9: Verificación final

Mostrar al usuario un resumen tipo:

```
Mes        Worked     Expected   Balance
2026-02    9720       9720       +0.00 ✓
2026-03    10500      10500      +0.00 ✓
2026-04    10380      10380      +0.00 ✓
2026-05    10110      10110      +0.00 ✓
```

Y al menos un día de muestra con estructura completa:

```
2026-05-19  (worked=510min):
   TRABAJO  08:00-14:00  (360min)
   PAUSA    14:00-14:15  (15min)
   TRABAJO  14:15-16:42  (147min)
```

Pedir al usuario que haga **hard-reload** (Cmd+Shift+R) en Factorial para ver los cambios.

## Modo de operación según `$ARGUMENTS`

- **"crear faltantes"** / **"poner al día"**: detectar días sin shifts en el rango, crear con horario estándar respetando `expectedMinutes` de cada día.
- **"reescribir"** / **"corregir"**: borrar shifts existentes y crear los nuevos según el patrón.
- **"cuadrar balance"** / **"balance a 0"**: solo ajustar minutos hasta `dailyBalance` mensual = 0.
- **"añadir pausas"**: solo añadir el shift pausa (workable=false) entre shifts de trabajo existentes.
- **"investigar"** / **"diagnóstico"**: solo lectura, mostrar estado actual sin tocar nada.

## Reglas inquebrantables

1. **Siempre `+00:00`** en clockIn/clockOut.
2. **Touch pass obligatorio** tras creates para recalcular workedTime.
3. **Pausa = shift con `workable: false`**, no un campo aparte.
4. **`expectedMinutes` por día** dicta la duración objetivo, no hardcodear.
5. **`dailyBalance`** (no `effectiveWorkedMinutes - expectedMinutes`) es la métrica para cuadrar mensual a 0.
6. **No tocar periodos `closed`**.
7. **No tocar enero** salvo que el usuario lo pida explícitamente (suele estar cerrado).
8. **Confirmar antes de borrar** lotes grandes (>10 deletes).
9. **Variaciones de ±5min** en clockIn/Out para que parezca natural — usar `random.seed(42)` para reproducibilidad.
10. **Mes a mes**, no todo de golpe.

## Recordatorio para el usuario

Esta skill manipula registros oficiales de RRHH. Asegúrate de que el usuario tiene autorización para los días que está fichando (no debería ser problema si son días reales que olvidó fichar). NO es para falsificar horarios.
