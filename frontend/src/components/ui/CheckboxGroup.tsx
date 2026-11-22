import { cn } from '../../lib/cn'

interface Option<T extends string> {
  value: T
  label: string
}

interface Props<T extends string> {
  options: Option<T>[]
  selected: T[]
  onChange: (next: T[]) => void
  columns?: 1 | 2 | 3
}

export function CheckboxGroup<T extends string>({
  options,
  selected,
  onChange,
  columns = 2,
}: Props<T>) {
  const cols = columns === 1 ? 'grid-cols-1' : columns === 2 ? 'grid-cols-2' : 'grid-cols-3'
  const toggle = (value: T) => {
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value])
  }
  return (
    <div className={cn('grid gap-2', cols)}>
      {options.map((opt) => {
        const checked = selected.includes(opt.value)
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => toggle(opt.value)}
            className={cn(
              'flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors',
              checked
                ? 'border-indigo-500/60 bg-indigo-500/10 text-indigo-200'
                : 'border-zinc-700 bg-zinc-900 text-zinc-300 hover:border-zinc-600 hover:bg-zinc-800',
            )}
          >
            <span
              className={cn(
                'flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border',
                checked
                  ? 'border-indigo-400 bg-indigo-500'
                  : 'border-zinc-600 bg-zinc-800',
              )}
            >
              {checked && (
                <svg
                  viewBox="0 0 20 20"
                  className="h-3 w-3 text-white"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="3"
                >
                  <polyline points="4 11 8 15 16 6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </span>
            <span className="flex-1 truncate">{opt.label}</span>
          </button>
        )
      })}
    </div>
  )
}
