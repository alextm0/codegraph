import type { InputHTMLAttributes } from 'react'

interface LatticeInputProps extends InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean
}

export default function LatticeInput({ mono = false, style, className, ...props }: LatticeInputProps) {
  return (
    <input
      className={`focus-ring ${mono ? 'font-mono' : ''} ${className ?? ''}`.trim()}
      style={{
        width: '100%',
        padding: '8px 12px',
        background: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-sm)',
        color: 'var(--text)',
        fontSize: 12,
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-body)',
        outline: 'none',
        transition: 'border-color var(--dur-fast), box-shadow var(--dur-fast)',
        ...style,
      }}
      onFocus={e => {
        e.currentTarget.style.borderColor = 'color-mix(in oklch, var(--accent) 50%, var(--border))'
        e.currentTarget.style.boxShadow = '0 0 0 2px color-mix(in oklch, var(--accent) 20%, transparent)'
      }}
      onBlur={e => {
        e.currentTarget.style.borderColor = 'var(--border)'
        e.currentTarget.style.boxShadow = 'none'
      }}
      {...props}
    />
  )
}
