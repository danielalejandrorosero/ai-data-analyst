import { useState, type InputHTMLAttributes } from 'react'
import { Eye, EyeOff, Lock } from 'lucide-react'
import { TextField } from './TextField'

interface PasswordFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string
  hint?: string
  error?: string
}

export function PasswordField({ label, hint, error, ...rest }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false)

  return (
    <TextField
      label={label}
      hint={hint}
      error={error}
      type={visible ? 'text' : 'password'}
      icon={<Lock className="h-4 w-4" aria-hidden="true" />}
      trailingAction={
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          className="rounded-sm p-1 text-paper-400 hover:text-paper-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500"
          aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
        >
          {visible ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
        </button>
      }
      {...rest}
    />
  )
}
