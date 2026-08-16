import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  Pie,
  PieChart,
  Scatter,
  ScatterChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useState } from 'react'
import { ChevronDown, Code2 } from 'lucide-react'
import type { AnalysisArtifact } from '../../api/analyses'
import { highlightSql } from './sqlHighlight'

function formatValue(value: unknown): string {
  return typeof value === 'number' ? value.toLocaleString('es-AR') : String(value ?? '')
}

// Paleta de datos derivada del acento ambar de la marca (ver
// frontend/src/index.css) - signal-500 es la serie principal, el resto solo
// entra en juego para graficos con varias categorias (pie).
const PALETTE = ['#e8a33d', '#7aa2e8', '#5fae7a', '#e2634f', '#f0b45c', '#c4841f']

const AXIS_STYLE = { fontSize: 11, fontFamily: 'IBM Plex Mono, monospace', fill: '#8a93a1' }
const TOOLTIP_STYLE = {
  background: '#171b21',
  border: '1px solid #20252d',
  borderRadius: 8,
  fontSize: 12,
  fontFamily: 'IBM Plex Mono, monospace',
  color: '#edeff2',
}

interface ChartArtifactProps {
  artifact: AnalysisArtifact
}

export function ChartArtifact({ artifact }: ChartArtifactProps) {
  const { chart_type, x_field, y_field, data, data_truncated } = artifact.spec
  const [showSql, setShowSql] = useState(false)

  return (
    <div className="rounded-lg border border-ink-700 bg-ink-900/60 p-4">
      <p className="mb-3 font-body text-sm font-semibold text-paper-100">{artifact.spec.title}</p>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {chart_type === 'line' ? (
            <LineChart data={data}>
              <CartesianGrid stroke="#20252d" strokeDasharray="3 3" />
              <XAxis dataKey={x_field} tick={AXIS_STYLE} stroke="#20252d" />
              <YAxis tick={AXIS_STYLE} stroke="#20252d" />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Line type="monotone" dataKey={y_field} stroke={PALETTE[0]} strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          ) : chart_type === 'scatter' ? (
            <ScatterChart>
              <CartesianGrid stroke="#20252d" strokeDasharray="3 3" />
              <XAxis dataKey={x_field} tick={AXIS_STYLE} stroke="#20252d" name={x_field} />
              <YAxis dataKey={y_field} tick={AXIS_STYLE} stroke="#20252d" name={y_field} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ strokeDasharray: '3 3' }} />
              <Scatter data={data} fill={PALETTE[0]} />
            </ScatterChart>
          ) : chart_type === 'pie' ? (
            <PieChart>
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Pie data={data} dataKey={y_field} nameKey={x_field} outerRadius={90} label>
                {data.map((_, index) => (
                  // eslint-disable-next-line react/no-array-index-key -- slices sin id propio
                  <Cell key={index} fill={PALETTE[index % PALETTE.length]} />
                ))}
              </Pie>
            </PieChart>
          ) : (
            <BarChart data={data} margin={{ top: 24 }}>
              <CartesianGrid stroke="#20252d" strokeDasharray="3 3" />
              <XAxis dataKey={x_field} tick={AXIS_STYLE} stroke="#20252d" />
              <YAxis tick={AXIS_STYLE} stroke="#20252d" tickFormatter={(v: number) => v.toLocaleString('es-AR')} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: '#20252d' }} formatter={formatValue} />
              <Bar dataKey={y_field} fill={PALETTE[0]} radius={[3, 3, 0, 0]}>
                <LabelList dataKey={y_field} position="top" formatter={formatValue} fill="#edeff2" fontSize={11} fontFamily="IBM Plex Mono, monospace" />
              </Bar>
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      <p className="mt-2 font-mono text-xs text-ink-400">
        eje X: {x_field} · eje Y: {y_field}
        {data_truncated && ' · muestra parcial de los datos'}
      </p>

      {/* RF-042: el usuario tiene que poder ver la consulta origen del
          grafico, no solo los datos ya agregados. */}
      <button
        type="button"
        onClick={() => setShowSql((v) => !v)}
        className="mt-2 flex items-center gap-1.5 font-mono text-[11px] text-paper-400 hover:text-paper-100"
      >
        <Code2 className="h-3 w-3" aria-hidden="true" />
        Consulta origen
        <ChevronDown className={`h-3 w-3 transition-transform ${showSql ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>
      {showSql && (
        <pre className="mt-2 overflow-x-auto rounded-md bg-ink-950 p-3 font-mono text-[11px] leading-relaxed">
          <code>{highlightSql(artifact.source_sql)}</code>
        </pre>
      )}
    </div>
  )
}
