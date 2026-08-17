import { Clock, FileText, Layers, Loader2, Trash2 } from 'lucide-react'
import type { OrgDocument } from '../../api/documents'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}

const FORMAT_CHIP: Record<OrgDocument['file_format'], string> = {
  pdf: 'border-danger-500/30 text-danger-500',
  docx: 'border-code-500/30 text-code-500',
  txt: 'border-paper-400/30 text-paper-400',
  md: 'border-signal-500/30 text-signal-500',
}

function StatusPill({ document }: { document: OrgDocument }) {
  if (document.status === 'PROCESSING') {
    return (
      <span className="flex items-center gap-1.5 rounded-full border border-signal-500/30 bg-signal-500/10 px-2 py-0.5 font-mono text-[11px] text-signal-500">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        Indexando
      </span>
    )
  }
  if (document.status === 'FAILED') {
    return (
      <span className="flex items-center gap-1.5 rounded-full border border-danger-500/30 bg-danger-500/10 px-2 py-0.5 font-mono text-[11px] text-danger-500">
        <span className="h-1.5 w-1.5 rounded-full bg-danger-500" aria-hidden="true" />
        Falló
      </span>
    )
  }
  return (
    <span className="flex items-center gap-1.5 rounded-full border border-success-500/30 bg-success-500/10 px-2 py-0.5 font-mono text-[11px] text-success-500">
      <span className="h-1.5 w-1.5 rounded-full bg-success-500" aria-hidden="true" />
      Listo
    </span>
  )
}

interface DocumentCardProps {
  document: OrgDocument
  canDelete: boolean
  onDelete: (document: OrgDocument) => void
  deleting: boolean
}

export function DocumentCard({ document, canDelete, onDelete, deleting }: DocumentCardProps) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-ink-700 bg-ink-900/60 p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-signal-500/10 text-signal-500">
            <FileText className="h-4.5 w-4.5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="truncate font-body text-sm font-semibold text-paper-100">{document.filename}</p>
            <span className={`mt-0.5 inline-block rounded border px-1.5 font-mono text-[10px] leading-4 uppercase ${FORMAT_CHIP[document.file_format]}`}>
              {document.file_format}
            </span>
          </div>
        </div>
        <StatusPill document={document} />
      </div>

      {document.status === 'FAILED' && document.error && (
        <p role="alert" className="font-mono text-xs text-danger-500">
          {document.error}
        </p>
      )}

      <div className="border-t border-ink-800" />

      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-paper-400">
          <span className="flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-ink-400" aria-hidden="true" />
            {document.chunk_count} fragmentos · {formatSize(document.size_bytes)}
          </span>
          <span className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-ink-400" aria-hidden="true" />
            {formatDate(document.created_at)}
          </span>
        </div>
        {canDelete && (
          <button
            type="button"
            onClick={() => onDelete(document)}
            disabled={deleting}
            aria-label={`Eliminar ${document.filename}`}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-paper-400 transition-colors hover:bg-danger-500/10 hover:text-danger-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  )
}
