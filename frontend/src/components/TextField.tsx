import { useId, type InputHTMLAttributes, type ReactNode } from 'react'

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hint?: string
  error?: string
  icon?: ReactNode
  trailingAction?: ReactNode
}

export function TextField({
  label,
  hint,
  error,
  icon,
  trailingAction,
  id,
  className = '',
  ...rest
}: TextFieldProps) {
  const generatedId = useId()
  const fieldId = id ?? generatedId
  const hintId = hint ? `${fieldId}-hint` : undefined
  const errorId = error ? `${fieldId}-error` : undefined
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={fieldId} className="font-mono text-xs text-paper-400">
        {label}
      </label>
      <div className="relative">
        {icon && (
          <span
            className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-paper-400"
            aria-hidden="true"
          >
            {icon}
          </span>
        )}
        <input
          id={fieldId}
          className={`w-full rounded-md border border-ink-600 bg-ink-950 py-3.5 font-body text-sm text-paper-100 placeholder:text-paper-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500 ${
            icon ? 'pl-9' : 'pl-3'
          } ${trailingAction ? 'pr-9' : 'pr-3'} ${error ? 'border-danger-500' : ''} ${className}`}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          {...rest}
        />
        {trailingAction && (
          <span className="absolute inset-y-0 right-0 flex items-center pr-2">{trailingAction}</span>
        )}
      </div>
      {hint && !error && (
        <p id={hintId} className="font-mono text-xs text-paper-400">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="font-mono text-xs text-danger-500">
          {error}
        </p>
      )}
    </div>
  )
}
