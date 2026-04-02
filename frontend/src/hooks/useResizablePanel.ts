import { useState, useEffect, useRef, useCallback } from 'react'

interface UseResizablePanelReturn {
  width: number
  handleMouseDown: (e: React.MouseEvent) => void
}

export function useResizablePanel(
  initialWidth = 280,
  minWidth = 200,
  maxWidth = 520,
  direction: 'left' | 'right' = 'right'
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
      const deltaX = e.clientX - startX.current
      const delta = direction === 'right' ? deltaX : -deltaX
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
  }, [minWidth, maxWidth, direction])

  return { width, handleMouseDown }
}
