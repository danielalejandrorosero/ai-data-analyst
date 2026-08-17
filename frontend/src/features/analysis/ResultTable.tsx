import type { QueryResult } from '../../api/analyses'

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return value.toLocaleString('es-AR')
  return String(value)
}

interface ResultTableProps {
  result: QueryResult
}

export function ResultTable({ result }: ResultTableProps) {
  return (
    <div>
      <div className="overflow-x-auto rounded-md border border-ink-700">
        <table className="w-full min-w-[280px] font-mono text-[11px] whitespace-nowrap">
          <thead>
            <tr className="border-b border-ink-700 bg-ink-800 text-paper-400">
              {result.columns.map((column) => (
                <th key={column} className="px-2 py-1.5 text-left font-medium">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, rowIndex) => (
              // eslint-disable-next-line react/no-array-index-key -- filas sin id propio, el orden es estable dentro de un mismo resultado
              <tr key={rowIndex} className="border-b border-ink-800 text-paper-300">
                {row.map((cell, cellIndex) => (
                  // eslint-disable-next-line react/no-array-index-key
                  <td key={cellIndex} className="px-2 py-1.5">
                    {formatCell(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 font-mono text-xs text-ink-400">
        {result.row_count.toLocaleString('es-AR')} fila{result.row_count === 1 ? '' : 's'}
        {result.truncated && ' · resultado truncado por el límite de filas del agente'}
        {result.evidence_truncated && !result.truncated && ' · vista parcial (evidencia acotada)'}
      </p>
    </div>
  )
}
