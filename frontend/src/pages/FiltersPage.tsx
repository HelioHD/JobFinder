import { useEffect, useState } from 'react'
import {
  AlertCircle,
  Bell,
  BellOff,
  Bookmark,
  CheckCircle2,
  Clock,
  Mail,
  Pencil,
  Play,
  RefreshCcw,
  Trash2,
} from 'lucide-react'
import { api, ApiError } from '../api/client'
import {
  ALERT_FREQ_LABELS,
  type FilterRunResult,
  type SavedFilter,
} from '../api/types'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { SaveFilterModal } from '../components/SaveFilterModal'

type Toast = { kind: 'ok' | 'err' | 'info'; msg: string }

function formatRelative(iso: string | null): string {
  if (!iso) return 'nunca'
  const date = new Date(iso)
  const diff = Date.now() - date.getTime()
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return 'agora'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}min atrás`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h atrás`
  const days = Math.floor(hr / 24)
  if (days < 30) return `${days}d atrás`
  return date.toLocaleDateString('pt-BR')
}

export function FiltersPage() {
  const [filters, setFilters] = useState<SavedFilter[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<Toast | null>(null)
  const [running, setRunning] = useState<string | null>(null)
  const [editing, setEditing] = useState<SavedFilter | null>(null)

  const showToast = (kind: Toast['kind'], msg: string) => {
    setToast({ kind, msg })
    setTimeout(() => setToast(null), 6000)
  }

  const refresh = async () => {
    setLoading(true)
    try {
      const data = await api.listFilters()
      setFilters(data)
      setError(null)
    } catch (e) {
      const msg = e instanceof ApiError ? `${e.status}: ${e.message}` : (e as Error).message
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const handleToggle = async (sf: SavedFilter) => {
    try {
      const updated = await api.updateFilter(sf.id, { alert_enabled: !sf.alert_enabled })
      setFilters((arr) => arr.map((f) => (f.id === sf.id ? updated : f)))
      showToast('ok', `Alerta ${updated.alert_enabled ? 'ativado' : 'pausado'}`)
    } catch (e) {
      showToast('err', (e as Error).message)
    }
  }

  const handleRunNow = async (sf: SavedFilter) => {
    setRunning(sf.id)
    try {
      const res: FilterRunResult = await api.runFilterNow(sf.id)
      const parts: string[] = []
      parts.push(`${res.total_found} vaga${res.total_found === 1 ? '' : 's'}`)
      parts.push(`${res.new_jobs_for_filter} nova${res.new_jobs_for_filter === 1 ? '' : 's'}`)
      if (res.emailed) parts.push(`e-mail enviado pra ${res.email_recipient}`)
      else if (res.errors.length) parts.push(`erro: ${res.errors[0]}`)
      else parts.push('sem e-mail')
      showToast(res.errors.length ? 'err' : 'ok', `${sf.name}: ${parts.join(' · ')}`)
      await refresh()
    } catch (e) {
      showToast('err', (e as Error).message)
    } finally {
      setRunning(null)
    }
  }

  const handleResetSent = async (sf: SavedFilter) => {
    if (!window.confirm(`Resetar histórico de envios de "${sf.name}"? O próximo run vai considerar todas as vagas como novas.`)) return
    try {
      await api.resetFilterSent(sf.id)
      showToast('ok', `Histórico de "${sf.name}" resetado.`)
    } catch (e) {
      showToast('err', (e as Error).message)
    }
  }

  const handleDelete = async (sf: SavedFilter) => {
    if (!window.confirm(`Apagar o filtro "${sf.name}"? Essa ação não pode ser desfeita.`)) return
    try {
      await api.deleteFilter(sf.id)
      setFilters((arr) => arr.filter((f) => f.id !== sf.id))
      showToast('ok', `Filtro "${sf.name}" removido`)
    } catch (e) {
      showToast('err', (e as Error).message)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Filtros salvos</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Suas buscas favoritas com alertas automáticos por e-mail.
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          leftIcon={<RefreshCcw className="h-4 w-4" />}
          onClick={refresh}
          loading={loading}
        >
          Atualizar
        </Button>
      </header>

      {toast && (
        <div
          className={`flex items-start gap-3 rounded-lg border p-4 text-sm ${
            toast.kind === 'ok'
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
              : toast.kind === 'err'
              ? 'border-red-500/30 bg-red-500/10 text-red-200'
              : 'border-zinc-700 bg-zinc-900 text-zinc-200'
          }`}
        >
          {toast.kind === 'ok' ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 flex-shrink-0" />
          ) : (
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          )}
          <span>{toast.msg}</span>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {!loading && filters.length === 0 && !error && (
        <div className="rounded-xl border border-dashed border-zinc-800 px-8 py-16 text-center">
          <Bookmark className="mx-auto h-8 w-8 text-zinc-700" />
          <p className="mt-4 text-base font-medium text-zinc-300">Nenhum filtro salvo ainda</p>
          <p className="mt-1 text-sm text-zinc-500">
            Vá em "Buscar" → configure seus filtros → clique em "Salvar como alerta".
          </p>
        </div>
      )}

      {filters.map((sf) => (
        <Card key={sf.id}>
          <CardHeader className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h3 className="text-base font-semibold text-zinc-100">{sf.name}</h3>
                {sf.alert_enabled ? (
                  <Badge variant="info">
                    <Bell className="h-3 w-3" />
                    {ALERT_FREQ_LABELS[sf.alert_frequency]}
                  </Badge>
                ) : (
                  <Badge variant="default">
                    <BellOff className="h-3 w-3" />
                    pausado
                  </Badge>
                )}
              </div>
              <p className="mt-1 text-xs text-zinc-500">
                <Mail className="mr-1 inline h-3 w-3" />
                {sf.recipient_email || 'destinatário padrão (.env)'} ·{' '}
                <Clock className="mr-1 inline h-3 w-3" />
                último run: {formatRelative(sf.last_run_at)} · {sf.total_emails_sent} e-mail
                {sf.total_emails_sent === 1 ? '' : 's'} enviado{sf.total_emails_sent === 1 ? '' : 's'}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => handleToggle(sf)}
                leftIcon={sf.alert_enabled ? <BellOff className="h-3.5 w-3.5" /> : <Bell className="h-3.5 w-3.5" />}
              >
                {sf.alert_enabled ? 'Pausar' : 'Ativar'}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => handleRunNow(sf)}
                loading={running === sf.id}
                leftIcon={<Play className="h-3.5 w-3.5" />}
              >
                Rodar agora
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setEditing(sf)}
                leftIcon={<Pencil className="h-3.5 w-3.5" />}
              >
                Editar
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => handleResetSent(sf)}
                leftIcon={<RefreshCcw className="h-3.5 w-3.5" />}
              >
                Resetar
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={() => handleDelete(sf)}
                leftIcon={<Trash2 className="h-3.5 w-3.5" />}
              >
                Apagar
              </Button>
            </div>
          </CardHeader>
          <CardBody className="space-y-2">
            <div className="flex flex-wrap gap-2">
              {sf.filter.keywords.length > 0 && (
                <Badge variant="info">keywords: {sf.filter.keywords.join(', ')}</Badge>
              )}
              {sf.filter.exclude_keywords.length > 0 && (
                <Badge variant="warning">exclui: {sf.filter.exclude_keywords.join(', ')}</Badge>
              )}
              {sf.filter.location_mode !== 'any' && (
                <Badge variant="default">
                  {sf.filter.location_mode}
                  {sf.filter.region ? ` · ${sf.filter.region}` : ''}
                </Badge>
              )}
              {sf.filter.posted_within_days && (
                <Badge variant="default">últimos {sf.filter.posted_within_days}d</Badge>
              )}
              {sf.filter.sources.length > 0 && (
                <Badge variant="default">fontes: {sf.filter.sources.join(', ')}</Badge>
              )}
              <Badge variant="default">limite: {sf.filter.limit}</Badge>
            </div>
            {sf.last_run_status && (
              <p className="text-xs text-zinc-500">
                <span className="text-zinc-600">Status:</span> {sf.last_run_status}
              </p>
            )}
          </CardBody>
        </Card>
      ))}

      <SaveFilterModal
        open={!!editing}
        onClose={() => setEditing(null)}
        filter={editing?.filter ?? ({} as never)}
        editing={editing}
        onSaved={(sf) => {
          setFilters((arr) => arr.map((f) => (f.id === sf.id ? sf : f)))
          showToast('ok', `Filtro "${sf.name}" atualizado`)
        }}
      />
    </div>
  )
}
