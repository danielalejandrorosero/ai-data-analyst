import { CircleDot, TerminalSquare } from 'lucide-react'

// Ilustracion estatica de como se ve una consulta real del agente - no es
// data en vivo, es contenido de ejemplo para el panel de login.
const RESULT_ROWS = [
  { segmento: 'PyME', mes: '2024-01-01', total_ventas: '1.234.567,00' },
  { segmento: 'Enterprise', mes: '2024-01-01', total_ventas: '2.345.678,00' },
  { segmento: 'PyME', mes: '2024-02-01', total_ventas: '1.345.890,00' },
]

export function TerminalPreviewCard() {
  return (
    <div className="overflow-hidden rounded-lg border border-ink-700 bg-ink-900">
      <div className="flex items-center justify-between border-b border-ink-700 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5" aria-hidden="true">
            <span className="h-2.5 w-2.5 rounded-full bg-ink-600" />
            <span className="h-2.5 w-2.5 rounded-full bg-ink-600" />
            <span className="h-2.5 w-2.5 rounded-full bg-ink-600" />
          </div>
          <span className="flex items-center gap-1.5 font-mono text-xs text-paper-400">
            <TerminalSquare className="h-3.5 w-3.5" aria-hidden="true" />
            Consulta del agente
          </span>
        </div>
        <span className="flex items-center gap-1.5 font-mono text-xs text-success-500">
          <CircleDot className="h-3 w-3" aria-hidden="true" />
          Completada en 1.42s
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 p-4 min-[1600px]:grid-cols-[minmax(300px,1.3fr)_minmax(280px,1fr)] min-[1600px]:gap-4">
        <pre className="overflow-x-auto font-mono text-[11px] leading-relaxed text-paper-300 sm:text-xs">
          <code>
            <span className="text-success-500 italic"># Esquema inspeccionado</span>
            {'\n'}
            <span className="text-paper-400">tables: ventas, clientes, productos, fechas</span>
            {'\n\n'}
            <span className="text-success-500 italic"># SQL generado por el agente</span>
            {'\n'}
            <span className="text-code-500">SELECT</span>
            {'\n  c.segmento,\n  '}
            <span className="text-code-500">DATE_TRUNC</span>
            {'('}
            <span className="text-success-500">'month'</span>
            {', v.fecha) '}
            <span className="text-code-500">AS</span>
            {' mes,\n  '}
            <span className="text-code-500">SUM</span>
            {'(v.total) '}
            <span className="text-code-500">AS</span>
            {' total_ventas\n'}
            <span className="text-code-500">FROM</span>
            {' ventas v\n'}
            <span className="text-code-500">JOIN</span>
            {' clientes c '}
            <span className="text-code-500">ON</span>
            {' c.id = v.cliente_id\n'}
            <span className="text-code-500">WHERE</span>
            {' v.fecha >= '}
            <span className="text-success-500">DATE '2024-01-01'</span>
            {'\n'}
            <span className="text-code-500">GROUP BY</span>
            {' 1, 2\n'}
            <span className="text-code-500">ORDER BY</span>
            {' 2, 1;'}
          </code>
        </pre>

        <div className="min-[1600px]:mt-20 min-[1600px]:border-l min-[1600px]:border-ink-700 min-[1600px]:pl-4">
          <p className="mb-2 font-mono text-xs text-paper-400">Vista previa de resultados</p>
          <div className="overflow-x-auto rounded-md border border-ink-700">
            <table className="w-full min-w-[280px] font-mono text-[11px] whitespace-nowrap">
              <thead>
                <tr className="border-b border-ink-700 bg-ink-800 text-paper-400">
                  <th className="px-2 py-1.5 text-left font-medium">segmento</th>
                  <th className="px-2 py-1.5 text-left font-medium">mes</th>
                  <th className="px-2 py-1.5 text-right font-medium">total_ventas</th>
                </tr>
              </thead>
              <tbody>
                {RESULT_ROWS.map((row) => (
                  <tr key={`${row.segmento}-${row.mes}`} className="border-b border-ink-800 text-paper-300">
                    <td className="px-2 py-1.5">{row.segmento}</td>
                    <td className="px-2 py-1.5">{row.mes}</td>
                    <td className="px-2 py-1.5 text-right">{row.total_ventas}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 font-mono text-xs text-ink-400">+ 28 filas</p>
        </div>
      </div>
    </div>
  )
}
