import { Building2, ExternalLink, Star, BadgeCheck } from 'lucide-react'
import { COURSE_SOURCE_LABELS, COURSE_TYPE_LABELS, type Course } from '../api/courseTypes'
import { Badge } from './ui/Badge'
import { Button } from './ui/Button'

interface Props {
  course: Course
}

function formatPrice(price: number, currency: string): string {
  if (price <= 0) return 'Grátis'
  try {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency }).format(price)
  } catch {
    return `${currency} ${price.toFixed(2)}`
  }
}

export function CourseCard({ course }: Props) {
  return (
    <article className="group relative rounded-xl border border-zinc-800 bg-zinc-900/60 p-5 transition-colors hover:border-zinc-700 hover:bg-zinc-900">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {course.price == null ? (
              <Badge variant="warning">Preço: verificar no site</Badge>
            ) : course.price <= 0 ? (
              <Badge variant="success">Grátis</Badge>
            ) : (
              <Badge variant="default">{formatPrice(course.price, course.currency)}</Badge>
            )}
            <Badge variant="info">{COURSE_TYPE_LABELS[course.course_type]}</Badge>
            {course.has_certificate === true && (
              <Badge variant="remote">
                <BadgeCheck className="h-3 w-3" /> Com certificado
              </Badge>
            )}
            {course.has_certificate == null && (
              <Badge variant="warning">Certificado: verificar no site</Badge>
            )}
            <Badge variant="default" className="ml-auto">
              {COURSE_SOURCE_LABELS[course.source] ?? course.source}
            </Badge>
          </div>

          <h3 className="mt-3 text-lg font-semibold text-zinc-100 line-clamp-2">
            {course.title}
          </h3>

          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-zinc-400">
            <span className="inline-flex items-center gap-1.5">
              <Building2 className="h-3.5 w-3.5" />
              {course.provider}
            </span>
            {course.rating != null && (
              <span className="inline-flex items-center gap-1.5">
                <Star className="h-3.5 w-3.5 text-amber-400" />
                {course.rating.toFixed(1)}
              </span>
            )}
            {course.duration_text && (
              <span className="text-xs text-zinc-500">{course.duration_text}</span>
            )}
          </div>

          {course.description && (
            <p className="mt-3 text-sm text-zinc-400 line-clamp-3">{course.description}</p>
          )}

          {course.theme_tags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {course.theme_tags.slice(0, 8).map((t) => (
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
          onClick={() => window.open(course.url, '_blank', 'noopener,noreferrer')}
          rightIcon={<ExternalLink className="h-3.5 w-3.5" />}
        >
          Ver curso
        </Button>
      </div>
    </article>
  )
}
