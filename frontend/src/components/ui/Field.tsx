import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface Props {
  label: string
  hint?: string
  error?: string
  required?: boolean
  className?: string
  children: ReactNode
}

export function Field({ label, hint, error, required, className, children }: Props) {
  return (
    <label className={cn('flex flex-col gap-1.5', className)}>
      <span className="text-xs font-medium uppercase tracking-wide text-zinc-400">
        {label}
        {required && <span className="ml-1 text-red-400">*</span>}
      </span>
      {children}
      {hint && !error && <span className="text-xs text-zinc-500">{hint}</span>}
      {error && <span className="text-xs text-red-400">{error}</span>}
    </label>
  )
}
