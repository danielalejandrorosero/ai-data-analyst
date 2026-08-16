import { useTypewriterProgress } from '../../lib/use-typewriter'

const LINE_1 = 'Preguntá tus datos.'
const LINE_2 = 'El agente muestra su trabajo.'
const TRACE_COPY =
  'Cada consulta queda trazada de punta a punta: esquema inspeccionado, SQL validado, resultado auditable. Nunca a ciegas.'

const ENDS = [LINE_1.length, LINE_1.length + LINE_2.length, LINE_1.length + LINE_2.length + TRACE_COPY.length]
const TOTAL_LENGTH = ENDS[2]

function segmentReveal(text: string, start: number, revealed: number) {
  const count = Math.max(0, Math.min(text.length, revealed - start))
  return { shown: text.slice(0, count), hidden: text.slice(count) }
}

function Cursor() {
  return (
    <span className="animate-cursor-blink font-mono text-paper-400" aria-hidden="true">
      ▌
    </span>
  )
}

// El texto completo (tipeado + oculto) siempre está en el DOM, solo cambia
// la opacidad del resto - así el alto del bloque no cambia mientras tipea
// y no empuja el contenido de abajo (layout shift).
function TypedSegment({
  shown,
  hidden,
  active,
}: {
  shown: string
  hidden: string
  active: boolean
}) {
  return (
    <span aria-hidden="true">
      {shown}
      {active && <Cursor />}
      <span className="opacity-0">{hidden}</span>
    </span>
  )
}

export function TerminalIntro() {
  const revealed = useTypewriterProgress(TOTAL_LENGTH, 22, 3500)
  const activeSegment = ENDS.findIndex((end) => revealed <= end)

  const l1 = segmentReveal(LINE_1, 0, revealed)
  const l2 = segmentReveal(LINE_2, ENDS[0], revealed)
  const trace = segmentReveal(TRACE_COPY, ENDS[1], revealed)

  return (
    <>
      <h1 className="max-w-xl font-body text-4xl leading-tight font-bold text-paper-100 md:text-5xl">
        <TypedSegment shown={l1.shown} hidden={l1.hidden} active={activeSegment === 0} />
        <br />
        <span className="text-paper-400">
          <TypedSegment shown={l2.shown} hidden={l2.hidden} active={activeSegment === 1} />
        </span>
      </h1>
      <p className="max-w-lg font-body text-base leading-relaxed text-paper-400">
        <TypedSegment shown={trace.shown} hidden={trace.hidden} active={activeSegment === 2} />
      </p>
      <span className="sr-only">
        {LINE_1} {LINE_2} {TRACE_COPY}
      </span>
    </>
  )
}
