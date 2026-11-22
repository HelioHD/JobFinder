import { useEffect, useState } from 'react'
import { AlertCircle, BookmarkPlus, CheckCircle2, Sparkles } from 'lucide-react'
import { api, ApiError } from '../api/client'
import { DEFAULT_FILTER, type JobFilter, type Job, type SourceInfo } from '../api/types'
import { FilterForm } from '../components/FilterForm'
import { JobList } from '../components/JobList'
import { SaveFilterModal } from '../components/SaveFilterModal'
import { Button } from '../components/ui/Button'

export function SearchPage() {
  const [filter, setFilter] = useState<JobFilter>(DEFAULT_FILTER)
  const [sources, setSources] = useState<SourceInfo[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [meta, setMeta] = useState<{ total: number; new: number; sources: string[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [saveOpen, setSaveOpen] = useState(false)
  const [savedToast, setSavedToast] = useState<string | null>(null)

  useEffect(() => {
    api.listSources().then(setSources).catch(() => setSources([]))
  }, [])

  const onSubmit = async () => {
    setLoading(true)
    setError(null)
    setWarnings([])
    try {
      const res = await api.scrape(filter)
      setJobs(res.jobs)
      setMeta({
        total: res.total_found,
        new: res.new_jobs,
        sources: res.sources_used,
      })
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
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Buscar vagas</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Configure os filtros como quiser e busque ao vivo nas fontes habilitadas.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<BookmarkPlus className="h-4 w-4" />}
          onClick={() => setSaveOpen(true)}
        >
          Salvar como alerta
        </Button>
      </header>

      <FilterForm
        value={filter}
        onChange={setFilter}
        onSubmit={onSubmit}
        loading={loading}
        sources={sources}
      />

      <SaveFilterModal
        open={saveOpen}
        onClose={() => setSaveOpen(false)}
        filter={filter}
        onSaved={(sf) => {
          setSavedToast(`Filtro "${sf.name}" salvo com sucesso. Acesse "Filtros salvos" pra gerenciar.`)
          setTimeout(() => setSavedToast(null), 6000)
        }}
      />

      {savedToast && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-200">
          {savedToast}
        </div>
      )}

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
            <strong>{meta.total}</strong> vaga{meta.total === 1 ? '' : 's'} encontrada
            {meta.total === 1 ? '' : 's'} ·{' '}
            <strong>{meta.new}</strong> nova{meta.new === 1 ? '' : 's'}
          </span>
          {meta.sources.length > 0 && (
            <span className="ml-auto inline-flex items-center gap-1.5 text-xs text-emerald-300/80">
              <Sparkles className="h-3 w-3" />
              fontes: {meta.sources.join(', ')}
            </span>
          )}
        </div>
      )}

      {hasSearched && (
        <JobList
          jobs={jobs}
          loading={loading}
          emptyTitle="Nenhuma vaga bateu com seus filtros"
          emptyDescription="Tente afrouxar os critérios — menos keywords, modo de localização 'Qualquer', ou aumente o limite."
        />
      )}

      {!hasSearched && !loading && (
        <div className="rounded-xl border border-dashed border-zinc-800 px-8 py-16 text-center">
          <Sparkles className="mx-auto h-8 w-8 text-zinc-700" />
          <p className="mt-4 text-base font-medium text-zinc-300">Pronto pra começar?</p>
          <p className="mt-1 text-sm text-zinc-500">
            Configure os filtros acima e clique em "Buscar vagas".
          </p>
        </div>
      )}
    </div>
  )
}
