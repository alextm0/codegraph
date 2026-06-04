import type { TextareaHTMLAttributes } from 'react'

interface LatticeTextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  mono?: boolean
}

export default function LatticeTextarea({ mono = false, style, className, ...props }: LatticeTextareaProps) {
  return (
    <textarea
      className={`focus-ring ${mono ? 'font-mono' : ''} ${className ?? ''}`.trim()}
      style={{
        width: '100%',
        padding: '10px 12px',
        background: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-sm)',
        color: 'var(--text)',
        fontSize: 13,
        lineHeight: 1.55,
        fontFamily: mono ? 'var(--font-mono)' : 'var(--font-body)',
        resize: 'none',
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
