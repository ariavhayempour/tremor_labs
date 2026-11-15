import type { CSSProperties } from 'react'
import './segmentedControl.css'

interface SegmentedControlProps<T extends string | number> {
  value: T
  options: readonly [{ value: T; label: string }, { value: T; label: string }, ...{ value: T; label: string }[]]
  onChange: (value: T) => void
  label: string
  disabled?: boolean
  className?: string
}

export function SegmentedControl<T extends string | number>({ value, options, onChange, label, disabled = false, className = '' }: SegmentedControlProps<T>) {
  const active = options.findIndex(option => option.value === value)
  const style = { '--options': options.length, '--active': Math.max(0, active) } as CSSProperties
  return <div className={`segmented-control ${className}`} role="group" aria-label={label} data-active-index={active} style={style}>
    {options.map(option => <button className="segmented-option" type="button" key={option.value} aria-pressed={value === option.value} disabled={disabled} onClick={() => onChange(option.value)}>{option.label}</button>)}
  </div>
}
