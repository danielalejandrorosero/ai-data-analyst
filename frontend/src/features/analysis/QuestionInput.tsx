import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { Loader2, SendHorizonal, TerminalSquare } from 'lucide-react'

interface QuestionInputProps {
  disabled: boolean
  submitting: boolean
  disabledReason?: string
  onSubmit: (question: string) => void
}

export function QuestionInput({ disabled, submitting, disabledReason, onSubmit }: QuestionInputProps) {
  const [question, setQuestion] = useState('')

  function submit() {
    const trimmed = question.trim()
    if (!trimmed || disabled || submitting) return
    onSubmit(trimmed)
    setQuestion('')
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    submit()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-3 rounded-xl border border-ink-700 bg-ink-900 p-3 shadow-lg shadow-ink-950/50"
    >
      <TerminalSquare className="mb-2 h-4 w-4 shrink-0 text-signal-500" aria-hidden="true" />
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled || submitting}
        rows={1}
        placeholder={
          disabledReason ?? 'Preguntá algo sobre tus datos… (ej: ¿cuáles fueron las ventas por región el último trimestre?)'
        }
        className="max-h-32 flex-1 resize-none bg-transparent py-1.5 font-mono text-sm text-paper-100 placeholder:text-paper-400 focus:outline-none disabled:cursor-not-allowed"
      />
      <button
        type="submit"
        disabled={disabled || submitting || !question.trim()}
        aria-label="Enviar pregunta"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-r from-signal-400 to-signal-600 text-ink-950 transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
      >
        {submitting ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : (
          <SendHorizonal className="h-4 w-4" aria-hidden="true" />
        )}
      </button>
    </form>
  )
}
