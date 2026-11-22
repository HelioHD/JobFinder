import { useEffect, useState } from 'react'
import { AlertCircle, CheckCircle2, Sparkles } from 'lucide-react'
import { courseApi, ApiError } from '../api/client'
import {
  DEFAULT_COURSE_FILTER,
  type Course,
  type CourseFilter,
  type CourseSourceInfo,
} from '../api/courseTypes'
import { CourseFilterForm } from '../components/CourseFilterForm'
import { CourseList } from '../components/CourseList'

export function LearnFinderPage() {
  const [filter, setFilter] = useState<CourseFilter>(DEFAULT_COURSE_FILTER)
  const [sources, setSources] = useState<CourseSourceInfo[]>([])
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [meta, setMeta] = useState<{ total: number; sources: string[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])

  useEffect(() => {
    courseApi.listSources().then(setSources).catch(() => setSources([]))
  }, [])

  const onSubmit = async () => {
    setLoading(true)
    setError(null)
    setWarnings([])
    try {
      const res = await courseApi.scrape(filter)
      setCourses(res.courses)
      setMeta({ total: res.total_found, sources: res.sources_used })
      setWarnings(res.errors)
      setHasSearched(true)
    } catch (e) {
      const msg = e instanceof ApiError ? `${e.status}: ${e.message}` : (e as Error).message
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-zinc-100">LearnFinder</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Ache certificações, cursos, pós-graduação e faculdade por tema, tipo e preço.
        </p>
      </header>

      <CourseFilterForm
        value={filter}
        onChange={setFilter}
        onSubmit={onSubmit}
        loading={loading}
        sources={sources}
      />

      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <div>
            <p className="font-medium">Erro ao buscar</p>
            <p className="mt-0.5 text-red-200/80">{error}</p>
          </div>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
          <p className="font-medium">Algumas fontes falharam:</p>
          <ul className="mt-1 list-disc pl-5 text-amber-200/80">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {meta && !error && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm text-emerald-200">
          <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
          <span>
            <strong>{meta.total}</strong> resultado{meta.total === 1 ? '' : 's'} encontrado
            {meta.total === 1 ? '' : 's'}
          </span>
          {meta.sources.length > 0 && (
            <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-emerald-300/80">
              <Sparkles className="h-3 w-3" />
              fontes ao vivo: {meta.sources.join(', ')}
            </span>
          )}
        </div>
      )}

      {hasSearched && (
        <CourseList
          courses={courses}
          loading={loading}
          emptyTitle="Nada bateu com seus filtros"
          emptyDescription="Tente afrouxar os critérios — menos temas, tipo 'qualquer' ou aumente o teto de preço."
        />
      )}

      {!hasSearched && !loading && (
        <div className="rounded-xl border border-dashed border-zinc-800 px-8 py-16 text-center">
          <Sparkles className="mx-auto h-8 w-8 text-zinc-700" />
          <p className="mt-4 text-base font-medium text-zinc-300">Pronto pra começar?</p>
          <p className="mt-1 text-sm text-zinc-500">
            Digite um tema (ex.: "red team") e clique em "Buscar".
          </p>
        </div>
      )}
    </div>
  )
}
