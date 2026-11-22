import type { SelectHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...rest}
      className={cn(
        'h-10 w-full appearance-none rounded-lg border border-zinc-700 bg-zinc-900 px-3 pr-9 text-sm text-zinc-100',
        "bg-[length:1rem] bg-[right_0.5rem_center] bg-no-repeat bg-[url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%23a1a1aa' stroke-width='2'><polyline points='6 9 12 15 18 9'/></svg>\")]",
        'focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-400/30',
        className,
      )}
    >
      {children}
    </select>
  )
}
