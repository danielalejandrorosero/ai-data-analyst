import type { ReactNode } from 'react'

const KEYWORDS = [
  'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON',
  'GROUP BY', 'ORDER BY', 'LIMIT', 'AS', 'AND', 'OR', 'NOT', 'IN', 'BETWEEN',
  'LIKE', 'IS', 'NULL', 'DESC', 'ASC', 'SUM', 'COUNT', 'AVG', 'MIN', 'MAX',
  'DATE_TRUNC', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'DISTINCT', 'HAVING',
]

// Coloreado liviano por regex (mismo criterio visual que el bloque estatico
// de TerminalPreviewCard: keywords en `code-500`, strings/fechas en
// `success-500`) - suficiente para SQL generado por el agente, que ya paso
// por el validator y siempre es un SELECT bien formado.
const TOKEN_PATTERN = new RegExp(`('[^']*')|\\b(${KEYWORDS.join('|').replace(/ /g, '\\s+')})\\b`, 'gi')

export function highlightSql(sql: string): ReactNode[] {
  const nodes: ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null
  let key = 0

  TOKEN_PATTERN.lastIndex = 0
  while ((match = TOKEN_PATTERN.exec(sql)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(sql.slice(lastIndex, match.index))
    }
    const [full, stringLiteral] = match
    nodes.push(
      <span key={key++} className={stringLiteral ? 'text-success-500' : 'text-code-500'}>
        {full}
      </span>,
    )
    lastIndex = match.index + full.length
  }
  if (lastIndex < sql.length) nodes.push(sql.slice(lastIndex))

  return nodes
}

// El validador re-serializa el SQL en una sola linea (sqlglot .sql()) - para
// mostrarlo legible se insertan saltos antes de cada clausula mayor. Es solo
// presentacion: el SQL que se muestra sigue siendo caracter a caracter el
// que se ejecuto, con whitespace distinto.
const CLAUSE_BREAK = /\s+(FROM|WHERE|GROUP BY|ORDER BY|LIMIT|HAVING|((LEFT|RIGHT|INNER|OUTER|CROSS)\s+)?JOIN)\b/gi

export function formatSql(sql: string): string {
  if (sql.includes('\n')) return sql
  return sql.replace(CLAUSE_BREAK, (match) => `\n${match.trim()}`)
}

// Fragmento corto e identificable para el header colapsado de una consulta -
// sin esto, 5-6 cards seguidas dicen todas "Consulta SQL - Completado" y son
// indistinguibles sin abrirlas una por una.
export function summarizeSql(sql: string): string {
  if (sql.startsWith('[polars]')) {
    return sql.length > 64 ? `${sql.slice(0, 61)}…` : sql
  }

  const parts: string[] = []
  const agg = sql.match(/\b(SUM|AVG|COUNT|MIN|MAX)\s*\(\s*(DISTINCT\s+)?([\w."*]+)\s*\)/i)
  if (agg) parts.push(`${agg[1].toUpperCase()}(${agg[2] ? 'DISTINCT ' : ''}${agg[3]})`)

  const groupBy = sql.match(/\bGROUP BY\s+(.+?)(?=\s+(?:ORDER BY|LIMIT|HAVING)\b|$)/i)
  if (groupBy) parts.push(`por ${groupBy[1].trim()}`)

  if (parts.length > 0) {
    const summary = parts.join(' · ')
    return summary.length > 64 ? `${summary.slice(0, 61)}…` : summary
  }
  const compact = sql.replace(/\s+/g, ' ')
  return compact.length > 64 ? `${compact.slice(0, 61)}…` : compact
}
