import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
}

export default function IconButton({ children, style, ...props }: IconButtonProps) {
  return (
    <button
      type="button"
      className="focus-ring"
      style={{
        background: 'transparent',
        border: 'none',
        borderRadius: 'var(--radius-sm)',
        color: 'var(--text-dim)',
        cursor: 'pointer',
        fontSize: 14,
        padding: '4px 6px',
        lineHeight: 1,
        transition: 'color var(--dur-fast), background var(--dur-fast)',
        fontFamily: 'var(--font-body)',
        ...style,
      }}
      onMouseEnter={e => {
        e.currentTarget.style.color = 'var(--text)'
        e.currentTarget.style.background = 'var(--surface2)'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.color = 'var(--text-dim)'
        e.currentTarget.style.background = 'transparent'
      }}
      {...props}
    >
      {children}
    </button>
  )
}
