import { Inbox } from 'lucide-react'
import type { Job } from '../api/types'
import { JobCard } from './JobCard'

interface Props {
  jobs: Job[]
  loading?: boolean
  emptyTitle?: string
  emptyDescription?: string
  onSendEmail?: (job: Job) => void
}

export function JobList({
  jobs,
  loading,
  emptyTitle = 'Nenhuma vaga encontrada',
  emptyDescription = 'Tente ajustar os filtros ou usar palavras-chave diferentes.',
  onSendEmail,
}: Props) {
  if (loading) {
    return (
      <div className="grid gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-40 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/40"
          />
        ))}
      </div>
    )
  }

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-800 px-8 py-16 text-center">
        <Inbox className="h-10 w-10 text-zinc-600" />
        <p className="mt-4 text-base font-medium text-zinc-300">{emptyTitle}</p>
        <p className="mt-1 max-w-sm text-sm text-zinc-500">{emptyDescription}</p>
      </div>
    )
  }

  return (
    <div className="grid gap-3">
      {jobs.map((j) => (
        <JobCard key={j.id} job={j} onSendEmail={onSendEmail} />
      ))}
    </div>
  )
}
