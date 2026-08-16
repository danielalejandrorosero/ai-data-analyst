import { useRef, useState, type DragEvent } from 'react'
import { Loader2, Upload } from 'lucide-react'
import { useImportDataset } from '../../api/datasets'
import { ApiError } from '../../api/client'

const ACCEPTED_EXTENSIONS = ['.csv', '.xlsx']

interface UploadDropzoneProps {
  organizationId: string | undefined
  token: string | null
}

export function UploadDropzone({ organizationId, token }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const importDataset = useImportDataset(organizationId, token)

  function handleFile(file: File) {
    const lower = file.name.toLowerCase()
    if (!ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext))) return
    importDataset.mutate({ file })
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setIsDragging(false)
    const file = event.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div className="flex flex-col gap-2">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
          isDragging ? 'border-signal-500 bg-signal-500/5' : 'border-ink-700 hover:border-ink-600'
        }`}
      >
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-ink-800 text-signal-500">
          {importDataset.isPending ? (
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
          ) : (
            <Upload className="h-5 w-5" aria-hidden="true" />
          )}
        </span>
        <p className="font-body text-sm text-paper-100">
          {importDataset.isPending ? (
            'Importando…'
          ) : (
            <>
              Arrastrá un CSV o Excel, o{' '}
              <span className="text-signal-500 underline">hacé clic para elegir</span>
            </>
          )}
        </p>
        <p className="font-mono text-xs text-ink-400">Archivos soportados: .csv, .xlsx (hasta 20MB)</p>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) handleFile(file)
            e.target.value = ''
          }}
        />
      </div>
      {importDataset.isError && (
        <p role="alert" className="font-mono text-xs text-danger-500">
          {importDataset.error instanceof ApiError
            ? importDataset.error.message
            : 'No se pudo conectar con el servidor.'}
        </p>
      )}
      {importDataset.isSuccess && (
        <p className="font-mono text-xs text-success-500">
          "{importDataset.data.name}" importado — {importDataset.data.row_count.toLocaleString('es-AR')} filas.
        </p>
      )}
    </div>
  )
}
