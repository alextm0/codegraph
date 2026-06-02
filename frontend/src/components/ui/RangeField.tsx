interface RangeFieldProps {
  label: string
  value: number
  min: number
  max: number
  step?: number
  onChange: (value: number) => void
  formatValue?: (value: number) => string
  hint?: string
}

/** Labeled range control with value readout. */
export default function RangeField({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
  formatValue,
  hint,
}: RangeFieldProps) {
  const display = formatValue ? formatValue(value) : String(value)

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: 6,
          gap: 8,
        }}
      >
        <span style={{ fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.06em' }}>{label}</span>
        <span
          style={{
            fontSize: 11,
            color: 'var(--accent)',
            fontWeight: 600,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {display}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="lattice-range"
        style={{ width: '100%' }}
      />
      {hint && (
        <div style={{ marginTop: 4, fontSize: 9, color: 'var(--text-muted)', lineHeight: 1.4 }}>{hint}</div>
      )}
    </div>
  )
}
