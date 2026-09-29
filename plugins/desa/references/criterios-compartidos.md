# Criterios compartidos (todos los tipos)

Criterios `#N` de `/desa:review` para todos los tipos de proyecto. También los usa `/desa:plan`.

Los números son estables porque los citan los informes, los planes y las PRs de otros repos: no se renumeran nunca, los nuevos van al final de su fichero con el siguiente número libre (hoy, #107) y los retirados se quedan marcados como «(retirado)».

1. **Adherencia a patrones preexistentes** — El código nuevo DEBE seguir los patrones del proyecto. Si hay duda, leer un fichero de referencia del mismo dominio para comparar
2. **Escalabilidad y mantenibilidad** — Acoplamiento excesivo, lógica duplicada, abstracciones prematuras o ausentes
3. **Legibilidad** — Nombres claros, flujo comprensible, sin complejidad innecesaria
4. **Sin comentarios** — Ni explicativos ni TODOs. Código autodocumentado
5. **Causas raíz** — Detectar fixes temporales, workarounds o parches sobre código problemático
6. **Seguridad** — SQL injection, XSS, autenticación/autorización, secretos hardcodeados, inputs no validados
7. **Complejidad innecesaria** — Nesting >3 niveles sin early return, ternarios anidados (`a ? b ? c : d : e`), funciones >50 líneas que deberían dividirse
8. **Código redundante** — Bloques duplicados o lógica repetida que debería extraerse a función/componente compartido
9. **Over-engineering** — Abstracciones sin uso real, wrappers triviales, configurabilidad innecesaria, soluciones "clever" difíciles de leer (one-liners densos, destructuring excesivo)
