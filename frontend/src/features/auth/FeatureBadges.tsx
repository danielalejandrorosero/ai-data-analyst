import { Search, ShieldCheck, Users } from 'lucide-react'

const FEATURES = [
  { icon: Search, label: 'SQL inspeccionable' },
  { icon: ShieldCheck, label: 'Consultas auditables' },
  { icon: Users, label: 'Acceso por organización' },
]

export function FeatureBadges() {
  return (
    <ul className="flex flex-wrap gap-3">
      {FEATURES.map(({ icon: Icon, label }) => (
        <li
          key={label}
          className="flex items-center gap-2 rounded-md border border-ink-700 bg-ink-900 px-3 py-2 font-body text-sm text-paper-300"
        >
          <Icon className="h-4 w-4 text-signal-500" strokeWidth={2} aria-hidden="true" />
          {label}
        </li>
      ))}
    </ul>
  )
}
