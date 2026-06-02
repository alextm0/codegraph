interface GraphControlsProps {
  onZoomIn: () => void
  onZoomOut: () => void
  onFitView: () => void
}

export default function GraphControls({
  onZoomIn,
  onZoomOut,
  onFitView,
}: GraphControlsProps) {
  return (
    <div
      style={{
        position: 'absolute',
        top: 12,
        left: 12,
        zIndex: 18,
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        pointerEvents: 'auto',
      }}
    >
      <div className="surface-elevated" style={{ display: 'flex', flexDirection: 'column', padding: 4, gap: 2 }}>
        <ControlBtn title="Zoom in" onClick={onZoomIn}>+</ControlBtn>
        <ControlBtn title="Fit graph to view" onClick={onFitView}>◎</ControlBtn>
        <ControlBtn title="Zoom out" onClick={onZoomOut}>−</ControlBtn>
      </div>
    </div>
  )
}

function ControlBtn({
  children,
  title,
  onClick,
}: {
  children: React.ReactNode
  title: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      title={title}
      className="focus-ring"
      onClick={onClick}
      style={{
        width: 32,
        height: 32,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'transparent',
        border: 'none',
        borderRadius: 'var(--radius-sm)',
        color: 'var(--text)',
        fontSize: 16,
        fontWeight: 500,
        cursor: 'pointer',
        transition: 'background var(--dur-fast), color var(--dur-fast)',
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = 'var(--surface2)'
        e.currentTarget.style.color = 'var(--accent)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = 'transparent'
        e.currentTarget.style.color = 'var(--text)'
      }}
    >
      {children}
    </button>
  )
}
