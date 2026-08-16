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
