import { useState, type MouseEvent } from 'react'

interface ResizeHandleProps {
  onMouseDown: (e: MouseEvent<HTMLDivElement>) => void
}

export default function ResizeHandle({ onMouseDown }: ResizeHandleProps) {
  const [dragging, setDragging] = useState(false)

  const handleMouseDown = (e: MouseEvent<HTMLDivElement>) => {
    setDragging(true)
    onMouseDown(e)

    const onUp = () => {
      setDragging(false)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mouseup', onUp)
  }

  return (
    <div
      onMouseDown={handleMouseDown}
      style={{
        width: 4,
        flexShrink: 0,
        cursor: 'col-resize',
        background: dragging ? 'var(--accent)' : 'var(--border)',
        transition: 'background 150ms ease',
      }}
      onMouseEnter={(e) => {
        if (!dragging) (e.currentTarget as HTMLDivElement).style.background = 'var(--accent)'
      }}
      onMouseLeave={(e) => {
        if (!dragging) (e.currentTarget as HTMLDivElement).style.background = 'var(--border)'
      }}
    />
  )
}
