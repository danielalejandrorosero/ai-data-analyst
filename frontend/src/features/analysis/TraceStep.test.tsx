import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Database } from 'lucide-react'
import { TraceStep } from './TraceStep'

// RNF-031: "el usuario DEBE poder distinguir entre respuesta final,
// herramienta ejecutada, SQL y error. Criterio: la UI separa visualmente
// etapas de ejecucion." Estos tests protegen la unica señal extra que
// TraceStep agrega sobre el mockup estatico: el color del nodo/aro segun
// `tone`. Si un cambio futuro iguala por error las clases de `error` con
// las de `success`/`pending`, este test debe romperse.

function nodeFor(text: string): HTMLElement {
  // El nodo circular es el <span class="... rounded-full ..."> que envuelve
  // al icono. Se ubica desde el div de contenido (hermano directo dentro
  // del wrapper "flex" de TraceStep) hacia arriba y luego se busca el
  // primer <span> con "rounded-full" entre sus descendientes.
  const content = screen.getByText(text)
  const wrapper = content.parentElement
  const ring = wrapper?.querySelector<HTMLElement>('span.rounded-full')
  if (!ring) throw new Error(`No se encontro el nodo circular para "${text}"`)
  return ring
}

describe('TraceStep', () => {
  it('usa clases con "danger" para tone="error" y no para tone="success"', () => {
    render(
      <>
        <TraceStep icon={Database} tone="error">
          contenido error
        </TraceStep>
        <TraceStep icon={Database} tone="success">
          contenido success
        </TraceStep>
      </>,
    )

    const errorNode = nodeFor('contenido error')
    const successNode = nodeFor('contenido success')

    expect(errorNode.className).toMatch(/danger/)
    expect(successNode.className).not.toMatch(/danger/)
    expect(errorNode.className).not.toBe(successNode.className)
  })

  it('usa clases con "danger" para tone="error" y no para tone="default"', () => {
    render(
      <>
        <TraceStep icon={Database} tone="error">
          contenido error
        </TraceStep>
        <TraceStep icon={Database} tone="default">
          contenido default
        </TraceStep>
      </>,
    )

    const errorNode = nodeFor('contenido error')
    const defaultNode = nodeFor('contenido default')

    expect(errorNode.className).toMatch(/danger/)
    expect(defaultNode.className).not.toMatch(/danger/)
  })

  it('distingue visualmente tone="pending" (border-ink-600) de tone="error" (border-danger-500)', () => {
    render(
      <>
        <TraceStep icon={Database} tone="pending">
          contenido pending
        </TraceStep>
        <TraceStep icon={Database} tone="error">
          contenido error
        </TraceStep>
      </>,
    )

    const pendingNode = nodeFor('contenido pending')
    const errorNode = nodeFor('contenido error')

    expect(pendingNode.className).toMatch(/border-ink-600/)
    expect(pendingNode.className).not.toMatch(/danger/)
    expect(errorNode.className).toMatch(/border-danger-500/)
    expect(errorNode.className).not.toBe(pendingNode.className)
  })

  it('el icono queda oculto para lectores de pantalla (aria-hidden="true")', () => {
    render(
      <TraceStep icon={Database} tone="success">
        contenido con icono
      </TraceStep>
    )

    const icon = document.querySelector('svg')
    expect(icon).not.toBeNull()
    expect(icon).toHaveAttribute('aria-hidden', 'true')
  })
})
