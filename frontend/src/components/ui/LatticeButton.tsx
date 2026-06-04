import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'bracket'

interface LatticeButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  active?: boolean
  children: ReactNode
}

const LatticeButton = forwardRef<HTMLButtonElement, LatticeButtonProps>(function LatticeButton(
  { variant = 'secondary', active = false, children, style, ...props },
  ref,
) {
  const isBracket = variant === 'bracket'
  const base: React.CSSProperties = {
    fontFamily: isBracket ? 'var(--font-mono)' : 'var(--font-body)',
    fontSize: isBracket ? 10 : 12,
    fontWeight: variant === 'primary' ? 600 : 500,
    letterSpacing: isBracket ? '0.08em' : '0.02em',
    textTransform: isBracket ? 'uppercase' : 'none',
    borderRadius: isBracket ? 0 : 'var(--radius-sm)',
    cursor: props.disabled ? 'not-allowed' : 'pointer',
    transition: 'background var(--dur-fast), color var(--dur-fast), border-color var(--dur-fast), box-shadow var(--dur-fast)',
    border: '1px solid var(--border)',
    padding: isBracket ? '0 10px' : '6px 14px',
    opacity: props.disabled ? 0.45 : 1,
  }

  const variants: Record<Variant, React.CSSProperties> = {
    primary: {
      background: 'var(--accent)',
      color: 'var(--bg)',
      borderColor: 'var(--accent)',
    },
    secondary: {
      background: active ? 'color-mix(in oklch, var(--accent) 14%, transparent)' : 'var(--surface2)',
      color: active ? 'var(--accent)' : 'var(--text)',
      borderColor: active ? 'color-mix(in oklch, var(--accent) 40%, var(--border))' : 'var(--border)',
    },
    ghost: {
      background: 'transparent',
      color: 'var(--text-muted)',
      border: 'none',
    },
    bracket: {
      background: active ? 'color-mix(in oklch, var(--accent) 12%, transparent)' : 'transparent',
      color: active ? 'var(--accent)' : 'var(--text-muted)',
      border: 'none',
      height: '100%',
    },
  }

  return (
    <button ref={ref} type="button" className="focus-ring" style={{ ...base, ...variants[variant], ...style }} {...props}>
      {children}
    </button>
  )
})

export default LatticeButton
