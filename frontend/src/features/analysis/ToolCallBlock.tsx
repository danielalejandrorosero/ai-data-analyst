import { useState } from 'react'
import { ChevronDown, Download } from 'lucide-react'
import type { AnalysisArtifact } from '../../api/analyses'
import { toolLabel, type TracedToolCall } from './toolTrace'
import { formatSql, highlightSql, summarizeSql } from './sqlHighlight'
import { ResultTable } from './ResultTable'
import { ChartArtifact } from './ChartArtifact'

interface SchemaColumn {
  name: string
  type: string
}

function isSchemaOutput(summary: Record<string, unknown> | null): summary is { columns: SchemaColumn[] } {
  return !!summary && Array.isArray((summary as { columns?: unknown }).columns)
}

// SQL con gutter de numeros de linea (el validador lo re-serializa en una
// linea, formatSql lo reparte por clausula solo para mostrarlo).
function SqlBlock({ sql }: { sql: string }) {
  const lines = formatSql(sql).split('\n')
  return (
    <pre className="overflow-x-auto rounded-md bg-ink-950 p-3 font-mono text-[11px] leading-relaxed">
      <code>
        {lines.map((line, index) => (
          // eslint-disable-next-line react/no-array-index-key -- lineas de un mismo SQL, orden estable
          <span key={index} className="flex">
            <span className="w-7 shrink-0 pr-3 text-right text-ink-400 select-none" aria-hidden="true">
              {index + 1}
            </span>
            <span className="whitespace-pre text-paper-300">{highlightSql(line)}</span>
          </span>
        ))}
      </code>
    </pre>
  )
}

interface ToolCallBlockProps {
  traced: TracedToolCall
  artifacts: AnalysisArtifact[]
  onExport: (queryIndex: number, format: 'csv' | 'json') => void
  exporting: boolean
}

// RNF-031: cada tool call es su propio bloque visualmente distinto (icono +
// estado propio) - nunca se mezclan SQL, resultado y error en un solo
// contenedor, aunque vengan del mismo tool call.
export function ToolCallBlock({ traced, artifacts, onExport, exporting }: ToolCallBlockProps) {
  const [expanded, setExpanded] = useState(traced.toolCall.status === 'ERROR')
  const { toolCall, result, resultIndex } = traced
  const isError = toolCall.status === 'ERROR'

  const chartArtifact =
    toolCall.tool === 'create_chart' && toolCall.output_summary
      ? artifacts.find((a) => a.id === toolCall.output_summary?.artifact_id)
      : undefined

  // Fragmento identificable aun colapsada - sin esto, varias "Consulta SQL"
  // seguidas son indistinguibles sin abrirlas una por una.
  let fragment = ''
  if (result) {
    fragment = summarizeSql(result.sql)
  } else if (toolCall.tool === 'inspect_schema' && isSchemaOutput(toolCall.output_summary)) {
    fragment = `columnas: ${toolCall.output_summary.columns.map((c) => c.name).join(', ')}`
  } else if (chartArtifact) {
    fragment = chartArtifact.spec.title
  }

  return (
    <div className="rounded-lg border border-ink-700 bg-ink-900/60">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <span className="shrink-0 font-body text-sm font-semibold text-paper-100">{toolLabel(toolCall.tool)}</span>
          <span
            className={`flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] ${
              isError
                ? 'border-danger-500/30 bg-danger-500/10 text-danger-500'
                : 'border-success-500/30 bg-success-500/10 text-success-500'
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${isError ? 'bg-danger-500' : 'bg-success-500'}`} aria-hidden="true" />
            {isError ? 'Error' : 'Completado'}
          </span>
          <span className="shrink-0 font-mono text-[11px] text-paper-400">{toolCall.duration_ms} ms</span>
          {fragment && (
            <span className="hidden truncate font-mono text-[11px] text-paper-400 sm:block">{fragment}</span>
          )}
        </div>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-paper-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>

      {expanded && (
        <div className="flex flex-col gap-3 border-t border-ink-700 p-4">
          {isError && (
            <p role="alert" className="font-mono text-xs text-danger-500">
              {toolCall.error_message}
            </p>
          )}

          {isSchemaOutput(toolCall.output_summary) && (
            <ul className="flex flex-col gap-1 font-mono text-xs text-paper-300">
              {toolCall.output_summary.columns.map((column) => (
                <li key={column.name} className="flex items-center gap-2">
                  <span className="text-paper-100">{column.name}</span>
                  <span className="text-ink-400">{column.type}</span>
                </li>
              ))}
            </ul>
          )}

          {result && (
            <>
              <SqlBlock sql={result.sql} />
              <ResultTable result={result} />
              {resultIndex !== undefined && (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => onExport(resultIndex, 'csv')}
                    disabled={exporting}
                    className="flex items-center gap-1.5 rounded-md border border-ink-600 px-2.5 py-1 font-mono text-[11px] text-paper-300 transition-colors hover:border-ink-400 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Download className="h-3 w-3" aria-hidden="true" />
                    Exportar CSV
                  </button>
                  <button
                    type="button"
                    onClick={() => onExport(resultIndex, 'json')}
                    disabled={exporting}
                    className="flex items-center gap-1.5 rounded-md border border-ink-600 px-2.5 py-1 font-mono text-[11px] text-paper-300 transition-colors hover:border-ink-400 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Download className="h-3 w-3" aria-hidden="true" />
                    Exportar JSON
                  </button>
                </div>
              )}
            </>
          )}

          {chartArtifact && <ChartArtifact artifact={chartArtifact} />}
        </div>
      )}
    </div>
  )
}
