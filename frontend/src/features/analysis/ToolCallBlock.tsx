import { useState } from 'react'
import { ChevronDown, CircleCheck, CircleX, Download } from 'lucide-react'
import type { AnalysisArtifact } from '../../api/analyses'
import { toolLabel, type TracedToolCall } from './toolTrace'
import { highlightSql } from './sqlHighlight'
import { ResultTable } from './ResultTable'
import { ChartArtifact } from './ChartArtifact'

interface SchemaColumn {
  name: string
  type: string
}

function isSchemaOutput(summary: Record<string, unknown> | null): summary is { columns: SchemaColumn[] } {
  return !!summary && Array.isArray((summary as { columns?: unknown }).columns)
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

  return (
    <div className="rounded-lg border border-ink-700 bg-ink-900/60">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2.5">
          <span className="font-body text-sm font-semibold text-paper-100">{toolLabel(toolCall.tool)}</span>
          <span
            className={`flex items-center gap-1 font-mono text-[11px] ${
              isError ? 'text-danger-500' : 'text-success-500'
            }`}
          >
            {isError ? <CircleX className="h-3 w-3" aria-hidden="true" /> : <CircleCheck className="h-3 w-3" aria-hidden="true" />}
            {isError ? 'Error' : 'Completado'} · {toolCall.duration_ms}ms
          </span>
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
              <pre className="overflow-x-auto rounded-md bg-ink-950 p-3 font-mono text-[11px] leading-relaxed">
                <code>{highlightSql(result.sql)}</code>
              </pre>
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
