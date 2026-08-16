import { useEffect, useState } from 'react'

export function useTypewriterProgress(totalLength: number, speedMs: number, holdMs: number): number {
  const [revealed, setRevealed] = useState(0)

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>

    function step(count: number) {
      setRevealed(count)
      timer = setTimeout(() => step(count < totalLength ? count + 1 : 0), count < totalLength ? speedMs : holdMs)
    }

    step(0)
    return () => clearTimeout(timer)
  }, [totalLength, speedMs, holdMs])

  return revealed
}
