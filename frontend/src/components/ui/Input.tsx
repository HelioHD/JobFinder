import type { InputHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...rest}
      className={cn(
        'h-10 w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 text-sm text-zinc-100 placeholder:text-zinc-500',
        'focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-400/30',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
    />
  )
}
