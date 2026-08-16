import { Building2 } from 'lucide-react'
import { Button } from '../../components/Button'

// SSO todavia no existe en el backend (sin RF asociado) - el boton queda
// visible pero deshabilitado hasta que se implemente.
export function SsoDivider() {
  return (
    <>
      <div className="my-5 flex items-center gap-3" aria-hidden="true">
        <span className="h-px flex-1 bg-ink-700" />
        <span className="font-mono text-xs text-ink-400">o</span>
        <span className="h-px flex-1 bg-ink-700" />
      </div>
      <Button type="button" variant="ghost" disabled className="w-full">
        <Building2 className="h-4 w-4" aria-hidden="true" />
        Entrar con SSO (Organización)
      </Button>
    </>
  )
}
