import { Building2, MapPin, ExternalLink, Mail, Globe, Clock } from 'lucide-react'
import { JOB_TYPE_LABELS, SOURCE_LABELS, type Job } from '../api/types'
import { Badge } from './ui/Badge'
import { Button } from './ui/Button'

interface Props {
  job: Job
  onSendEmail?: (job: Job) => void
}

function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const diff = Date.now() - d.getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'agora'
  if (min < 60) return `há ${min} min`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `há ${hr}h`
  const dy = Math.floor(hr / 24)
  if (dy < 30) return `há ${dy}d`
  const mo = Math.floor(dy / 30)
  return `há ${mo}mo`
}

export function JobCard({ job, onSendEmail }: Props) {
  return (
    <article className="group relative rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 transition-colors hover:border-zinc-700 hover:bg-zinc-900">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {job.is_remote ? (
              <Badge variant="remote">
                <Globe className="h-3 w-3" /> Remoto
              </Badge>
            ) : (
              <Badge variant="onsite">
                <MapPin className="h-3 w-3" /> Presencial
              </Badge>
            )}
            {job.job_types.map((t) => (
              <Badge key={t} variant="info">
                {JOB_TYPE_LABELS[t]}
              </Badge>
            ))}
            <Badge variant="default" className="ml-auto">
              {SOURCE_LABELS[job.source] ?? job.source}
            </Badge>
          </div>

          <h3 className="mt-3 text-lg font-semibold text-zinc-100 line-clamp-2">
            {job.title}
          </h3>

          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-zinc-400">
            <span className="inline-flex items-center gap-1.5">
              <Building2 className="h-3.5 w-3.5" />
              {job.company || 'Empresa não informada'}
            </span>
            {job.location && (
              <span className="inline-flex items-center gap-1.5">
                <MapPin className="h-3.5 w-3.5" />
                {job.location}
              </span>
            )}
            {job.posted_at && (
              <span className="inline-flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5" />
                {timeAgo(job.posted_at)}
              </span>
            )}
            {job.salary_text && (
              <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-300">
                {job.salary_text}
              </span>
            )}
          </div>

          {job.description && (
            <p className="mt-3 text-sm text-zinc-400 line-clamp-3">{job.description}</p>
          )}

          {job.tags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {job.tags.slice(0, 8).map((t) => (
                <span
                  key={t}
                  className="rounded-md bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400"
                >
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-zinc-800 pt-4">
        <Button
          variant="primary"
          size="sm"
          onClick={() => window.open(job.url, '_blank', 'noopener,noreferrer')}
          rightIcon={<ExternalLink className="h-3.5 w-3.5" />}
        >
          Ver vaga original
        </Button>
        {onSendEmail && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onSendEmail(job)}
            leftIcon={<Mail className="h-3.5 w-3.5" />}
          >
            Enviar por e-mail
          </Button>
        )}
      </div>
    </article>
  )
}
