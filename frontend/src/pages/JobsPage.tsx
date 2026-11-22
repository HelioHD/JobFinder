import { useEffect, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { api, ApiError } from '../api/client'
import type { Job } from '../api/types'
import { JobList } from '../components/JobList'
import { Button } from '../components/ui/Button'

const PAGE_SIZE = 20

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async (newOffset: number) => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.listJobs(PAGE_SIZE, newOffset)
      setJobs(res.items)
      setTotal(res.total)
      setOffset(newOffset)
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.message}` : (e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(0)
  }, [])

  const hasPrev = offset > 0
  const hasNext = offset + PAGE_SIZE < total
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Vagas coletadas</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Tudo que já foi salvo nas buscas anteriores. {total > 0 && <span>Total: {total}</span>}
          </p>
        </div>
      </header>

      {error && (
        <div className="flex items-start gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      <JobList
        jobs={jobs}
        loading={loading}
        emptyTitle="Ainda não há vagas salvas"
        emptyDescription="Faça uma busca na página 'Buscar' para começar a popular sua lista."
      />

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => load(offset - PAGE_SIZE)}
            disabled={!hasPrev || loading}
          >
            Anterior
          </Button>
          <span className="text-sm text-zinc-500">
            Página {currentPage} de {totalPages}
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => load(offset + PAGE_SIZE)}
            disabled={!hasNext || loading}
          >
            Próxima
          </Button>
        </div>
      )}
    </div>
  )
}
