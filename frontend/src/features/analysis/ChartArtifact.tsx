import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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
import type { AnalysisArtifact } from '../../api/analyses'

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
            <BarChart data={data}>
              <CartesianGrid stroke="#20252d" strokeDasharray="3 3" />
              <XAxis dataKey={x_field} tick={AXIS_STYLE} stroke="#20252d" />
              <YAxis tick={AXIS_STYLE} stroke="#20252d" />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: '#20252d' }} />
              <Bar dataKey={y_field} fill={PALETTE[0]} radius={[3, 3, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      <p className="mt-2 font-mono text-xs text-ink-400">
        eje X: {x_field} · eje Y: {y_field}
        {data_truncated && ' · muestra parcial de los datos'}
      </p>
    </div>
  )
}
