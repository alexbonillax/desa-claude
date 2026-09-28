# Evals del plugin desa

Casos de `claude plugin eval` que fijan comportamientos que ya se han roto alguna vez o que no deben romperse. Hace falta Claude Code 2.1.269 o posterior con acceso a `plugin eval` (en septiembre de 2026, en early access).

```bash
claude plugin eval plugins/desa --scaffold --allow-tools Bash Edit --max-cost-usd 5
```

- `--scaffold` ejecuta los `fixture.sh` de los casos, que montan un repo git de juguete en el directorio temporal del caso. Son bash que corre como tú: revísalos antes si alguien los cambia.
- `--allow-tools Bash Edit` da esas herramientas solo a los casos que las declaran en `allowed_tools`.
- Por defecto cada caso corre 3 veces con el plugin y 3 sin él (ablation). Los graders `tool_used: Skill` son indicadores de que la skill se disparó y no puntúan en el brazo sin plugin. Los de «no se dispara» llevan `arm: both`.

| Caso | Qué fija | Estado esperado |
|---|---|---|
| `review-mobile-unstaged` | Un cambio sin stagear solo en `apps/mobile` se revisa como mobile y se cita #65 (bug de `DIFF_FILES`, 1.12.0) | pasa |
| `plan-websites` | `/desa:plan` en un Next.js single-app aplica los criterios de websites y no termina en «unknown» (1.12.0) | pasa |
| `triage-tipo-a` | Un cambio de alcance claro sale en el formato A de tres líneas y va a `/desa:plan` (1.15.0) | pasa |
| `translations-desde-claude-md` | Si el `CLAUDE.md` lo pide, se invoca `/desa:translations` y nadie edita los ficheros de idioma a mano | pasa |
| `update-no-se-dispara` | El modelo no lanza `/desa:update` por su cuenta (1.11.0) | pasa |
| `magic-factorial-no-se-dispara` | Una pregunta sobre el balance no dispara `/desa:magic-factorial` | **falla** hasta que se decida su diseño (ver la auditoría) |

Ningún caso llama a la API real de Grupo Desa. El de translations no tiene Bash, así que la skill no puede ejecutar `terms.py` aunque haya un token en la máquina, y los que tienen Bash (review y plan) usan skills que no llaman a la API. Un caso nuevo que necesite la API tiene que simularla: nunca con el token de nadie.

Los casos se han escrito con la documentación de `plugin eval` y todavía no se han ejecutado: la versión instalada al escribirlos (2.1.236) no tiene el subcomando. La primera ejecución puede pedir ajustes en los graders.
