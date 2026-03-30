import { useState, useEffect, useRef, useCallback } from 'react'

interface UseResizablePanelReturn {
  width: number
  handleMouseDown: (e: React.MouseEvent) => void
}

export function useResizablePanel(
  initialWidth = 280,
  minWidth = 200,
  maxWidth = 520,
): UseResizablePanelReturn {
  const [width, setWidth] = useState(initialWidth)
  const isResizing = useRef(false)
  const startX = useRef(0)
  const startWidth = useRef(0)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isResizing.current = true
    startX.current = e.clientX
    startWidth.current = width
    e.preventDefault()
  }, [width])

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isResizing.current) return
      const delta = e.clientX - startX.current
      setWidth(Math.max(minWidth, Math.min(maxWidth, startWidth.current + delta)))
    }
    const onUp = () => {
      isResizing.current = false
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [minWidth, maxWidth])

  return { width, handleMouseDown }
}
