# Criterios mobile (React Native)

Criterios `#N` de `/desa:review` para mobile (`apps/mobile/`). También los usa `/desa:plan`.

Los números son estables porque los citan los informes, los planes y las PRs de otros repos: no se renumeran nunca, los nuevos van al final de su fichero con el siguiente número libre (hoy, #107) y los retirados se quedan marcados como «(retirado)».

A mobile se le aplican los compartidos y estos; los de `criterios-frontend.md`, no, aunque sean de JavaScript. Si un criterio de la web tiene que valer también en mobile, se añade aquí con su propio número y la marca `(= #N)`, como en `criterios-websites.md`.

65. **Mobile: useTheme() para estilos, no StyleSheet.create** — En mobile, todos los estilos van via `useTheme()`. Acceder como `theme.pressable.primary`, `theme.text.hint`, `theme.view.screen`. Nunca `StyleSheet.create()` ni estilos inline arbitrarios. Overrides puntuales con array: `style={[theme.textInput.text, {marginBottom: 8}]}`
82. **Reutilizar core antes de reimplementar** — Comprobar `packages/core/src/hooks/` antes de crear lógica nueva en mobile
83. **Screens sin lógica de componentes** — `app/` solo contiene screens (routing). Lógica en `components/features/`
84. **Nombres de theme = componente RN** — `pressable` no `button`, `textInput` no `input`
85. **Textos anidados en theme** — `theme.pressable.primary.text`, no `theme.pressable.primaryText`
