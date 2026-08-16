import { Database, Search, SlidersHorizontal, BarChart3, Wrench } from 'lucide-react'
import type { Analysis, QueryResult, ToolCall } from '../../api/analyses'

export const TOOL_LABELS: Record<string, string> = {
  inspect_schema: 'Inspeccionando esquema',
  execute_readonly_sql: 'Consulta SQL',
  run_analysis: 'Post-procesamiento',
  create_chart: 'Generando gráfico',
}

export const TOOL_ICONS: Record<string, typeof Search> = {
  inspect_schema: Search,
  execute_readonly_sql: Database,
  run_analysis: SlidersHorizontal,
  create_chart: BarChart3,
}

export function toolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? tool
}

export function toolIcon(tool: string) {
  return TOOL_ICONS[tool] ?? Wrench
}

// tool_calls no trae el SQL/las filas (backend/app/domain/agent/schemas.py:
// ToolCallOut no expone input_json) - pero cada execute_readonly_sql/
// run_analysis exitoso agrega, EN ORDEN, una entrada a Analysis.result_json
// (backend/app/domain/agent/tools.py: ctx.deps.results.append(...) solo en
// el camino de exito). Emparejar por posicion reconstruye, sin pedirle nada
// extra al backend, que evidencia corresponde a cada tool call.
export interface TracedToolCall {
  toolCall: ToolCall
  index: number
  result?: QueryResult
  resultIndex?: number
}

export function pairToolCallsWithResults(analysis: Analysis): TracedToolCall[] {
  const results = analysis.result ?? []
  let resultPointer = 0
  return analysis.tool_calls.map((toolCall, index) => {
    const producesResult =
      toolCall.status === 'SUCCESS' && (toolCall.tool === 'execute_readonly_sql' || toolCall.tool === 'run_analysis')
    if (producesResult) {
      const result = results[resultPointer]
      const resultIndex = resultPointer
      resultPointer += 1
      return { toolCall, index, result, resultIndex }
    }
    return { toolCall, index }
  })
}
