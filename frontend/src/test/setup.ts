import '@testing-library/jest-dom/vitest'

// jsdom no implementa scrollIntoView (usado por el auto-scroll del chat de
// AnalysisPage) - sin este shim, cualquier componente que lo invoque en un
// efecto crashea el arbol entero en el entorno de test.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}
