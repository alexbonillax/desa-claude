---
type: llm
weight: 2
---
PASS si el plan trata el proyecto como websites y aplica sus criterios: reutiliza `src/api/api.js` o `SitesService` en vez de llamar a `fetch` directamente (#102), usa una constante de `REVALIDATE` (#103) y cita criterios de websites (#86-#106). FAIL si dice que no reconoce el tipo de proyecto, si aplica criterios de backend o del monorepo, o si propone `fetch` directo.
