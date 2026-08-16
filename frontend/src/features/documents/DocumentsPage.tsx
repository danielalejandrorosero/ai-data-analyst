import { useRef, useState, type DragEvent } from 'react'
import { FileSearch, FileUp, Loader2, PackageOpen } from 'lucide-react'
import { useMe } from '../../api/auth'
import { useAuthStore } from '../../lib/auth-store'
import {
  useDeleteDocument,
  useDocuments,
  useSearchDocuments,
  useUploadDocument,
  type OrgDocument,
} from '../../api/documents'
import { ApiError } from '../../api/client'
import { AppShell } from '../../components/AppShell'
import { DocumentCard } from './DocumentCard'

const ACCEPTED_EXTENSIONS = ['.pdf', '.txt', '.md', '.docx']

export function DocumentsPage() {
  const token = useAuthStore((s) => s.token)
  const me = useMe()
  const membership = me.data?.memberships[0]
  const organizationId = membership?.organization_id

  const documents = useDocuments(organizationId, token)
  const upload = useUploadDocument(organizationId, token)
  const deleteDocument = useDeleteDocument(organizationId, token)

  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState('')
  const search = useSearchDocuments(organizationId, token, submittedQuery)

  const canUpload = membership && ['OWNER', 'ADMIN', 'ANALYST'].includes(membership.role)
  const canDelete = membership && ['OWNER', 'ADMIN'].includes(membership.role)

  function handleFile(file: File) {
    const lower = file.name.toLowerCase()
    if (!ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext))) return
    upload.mutate(file)
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setIsDragging(false)
    const file = event.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function handleDelete(document: OrgDocument) {
    deleteDocument.mutate(document.id)
  }

  return (
    <AppShell active="documentos">
      <div className="mb-6">
        <h1 className="flex items-baseline gap-2.5 font-body text-3xl font-bold text-paper-100">
          Documentos
          {documents.data && (
            <span className="font-mono text-sm font-normal text-paper-400">
              {documents.data.length} en total
            </span>
          )}
        </h1>
        <p className="mt-1 font-body text-sm text-paper-400">
          Contexto de negocio para el agente: manuales, reportes y definiciones (RAG)
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          setSubmittedQuery(searchInput.trim())
        }}
        className="mb-6 flex items-center gap-3 rounded-xl border border-ink-700 bg-ink-900 p-3"
      >
        <FileSearch className="h-4 w-4 shrink-0 text-signal-500" aria-hidden="true" />
        <input
          type="search"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Buscá en los documentos… (semántica + texto exacto)"
          aria-label="Buscar en los documentos"
          className="flex-1 bg-transparent font-mono text-sm text-paper-100 placeholder:text-paper-400 focus:outline-none"
        />
        <button
          type="submit"
          disabled={!searchInput.trim()}
          className="rounded-md border border-ink-600 px-3 py-1.5 font-body text-xs font-semibold text-paper-100 transition-colors hover:border-ink-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Buscar
        </button>
      </form>

      {submittedQuery && (
        <div className="mb-6 flex flex-col gap-3">
          <p className="font-mono text-xs text-paper-400">
            Resultados para "{submittedQuery}"
            {search.data && ` · ${search.data.length} fragmento${search.data.length === 1 ? '' : 's'}`}
          </p>
          {search.isPending && (
            <div className="flex items-center gap-2 font-mono text-xs text-paper-400">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              buscando…
            </div>
          )}
          {search.data?.length === 0 && (
            <p className="font-body text-sm text-paper-400">Ningún fragmento coincide con la búsqueda.</p>
          )}
          {search.data?.map((result) => (
            <div
              key={`${result.document_id}-${result.chunk_index}`}
              className="rounded-lg border border-ink-700 bg-ink-900/60 p-4"
            >
              <p className="mb-2 font-mono text-[11px] text-signal-500">
                {result.document_filename} · fragmento {result.chunk_index + 1}
              </p>
              <p className="font-body text-sm leading-relaxed text-paper-300">{result.content}</p>
            </div>
          ))}
        </div>
      )}

      {documents.isPending && (
        <div className="flex items-center gap-2 py-12 font-mono text-sm text-paper-400">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          cargando documentos…
        </div>
      )}

      {documents.isError && (
        <p role="alert" className="font-mono text-sm text-danger-500">
          No se pudieron cargar los documentos.
        </p>
      )}

      {documents.data && documents.data.length > 0 && (
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {documents.data.map((document) => (
            <DocumentCard
              key={document.id}
              document={document}
              canDelete={!!canDelete}
              onDelete={handleDelete}
              deleting={deleteDocument.isPending}
            />
          ))}
        </div>
      )}

      {documents.data && documents.data.length === 0 && (
        <div className="mb-6 flex flex-col items-center gap-2 rounded-xl border border-ink-700 bg-ink-900/40 py-12 text-center">
          <PackageOpen className="h-8 w-8 text-ink-400" aria-hidden="true" />
          <p className="font-body text-sm text-paper-400">Todavía no hay documentos subidos.</p>
        </div>
      )}

      {canUpload && (
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
              {upload.isPending ? (
                <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
              ) : (
                <FileUp className="h-5 w-5" aria-hidden="true" />
              )}
            </span>
            <p className="font-body text-sm text-paper-100">
              {upload.isPending ? (
                'Subiendo…'
              ) : (
                <>
                  Arrastrá un documento, o{' '}
                  <span className="text-signal-500 underline">hacé clic para elegir</span>
                </>
              )}
            </p>
            <p className="font-mono text-xs text-ink-400">
              Formatos: .pdf, .txt, .md, .docx (hasta 20MB) — se indexa en segundo plano
            </p>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.txt,.md,.docx"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) handleFile(file)
                e.target.value = ''
              }}
            />
          </div>
          {upload.isError && (
            <p role="alert" className="font-mono text-xs text-danger-500">
              {upload.error instanceof ApiError ? upload.error.message : 'No se pudo conectar con el servidor.'}
            </p>
          )}
          {upload.isSuccess && (
            <p className="font-mono text-xs text-success-500">
              "{upload.data.filename}" subido — indexándose en segundo plano.
            </p>
          )}
        </div>
      )}
    </AppShell>
  )
}
