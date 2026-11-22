import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

type Variant = 'default' | 'remote' | 'onsite' | 'success' | 'warning' | 'info'

const variants: Record<Variant, string> = {
  default: 'bg-zinc-800 text-zinc-300 border-zinc-700',
  remote: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
  onsite: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
  success: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
  warning: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
  info: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30',
}

export function Badge({
  children,
  variant = 'default',
  className,
}: {
  children: ReactNode
  variant?: Variant
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium',
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}
