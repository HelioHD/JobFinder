import { useEffect, useState } from 'react'
import { AlertCircle, CheckCircle2, Mail, RefreshCcw, Send, Server } from 'lucide-react'
import { api, ApiError } from '../api/client'
import type { SettingsStatus } from '../api/types'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Field } from '../components/ui/Field'
import { Badge } from '../components/ui/Badge'

type Toast = { kind: 'ok' | 'err'; msg: string }

export function SettingsPage() {
  const [status, setStatus] = useState<SettingsStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [testTo, setTestTo] = useState('')
  const [sendingTest, setSendingTest] = useState(false)
  const [toast, setToast] = useState<Toast | null>(null)

  const showToast = (kind: Toast['kind'], msg: string) => {
    setToast({ kind, msg })
    setTimeout(() => setToast(null), 8000)
  }

  const refresh = async () => {
    setLoading(true)
    try {
      const s = await api.getSettings()
      setStatus(s)
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

  const handleTest = async () => {
    setSendingTest(true)
    try {
      const res = await api.testEmail(testTo || undefined)
      showToast('ok', `E-mail de teste enviado pra ${res.to}. Confere a caixa de entrada.`)
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : (e as Error).message
      showToast('err', `Falhou: ${msg}`)
    } finally {
      setSendingTest(false)
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Configurações</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Status do servidor SMTP e do scheduler de alertas.
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
              : 'border-red-500/30 bg-red-500/10 text-red-200'
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

      {/* SMTP / E-mail */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-zinc-100">
              <Mail className="mr-2 inline h-4 w-4 text-zinc-400" />
              SMTP / Gmail
            </h2>
            <p className="mt-0.5 text-xs text-zinc-500">
              Credenciais lidas do arquivo <code className="text-zinc-400">backend/.env</code>.
            </p>
          </div>
          {status?.email.configured ? (
            <Badge variant="success">configurado</Badge>
          ) : (
            <Badge variant="warning">não configurado</Badge>
          )}
        </CardHeader>
        <CardBody className="space-y-4">
          {status && (
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs uppercase tracking-wide text-zinc-500">Servidor</dt>
                <dd className="text-zinc-200">
                  {status.email.smtp_host}:{status.email.smtp_port}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-zinc-500">Conta</dt>
                <dd className="text-zinc-200">{status.email.user || '— vazio —'}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-zinc-500">App password</dt>
                <dd className="font-mono text-zinc-200">{status.email.masked_password || '— vazio —'}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-zinc-500">Destinatário padrão</dt>
                <dd className="text-zinc-200">{status.email.default_recipient || '— vazio —'}</dd>
              </div>
            </dl>
          )}

          <div className="border-t border-zinc-800 pt-4">
            <p className="mb-3 text-sm font-medium text-zinc-200">Enviar e-mail de teste</p>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <Field label="Destinatário (em branco usa o padrão)" className="flex-1">
                <Input
                  type="email"
                  value={testTo}
                  onChange={(e) => setTestTo(e.target.value)}
                  placeholder={status?.email.default_recipient || 'voce@email.com'}
                />
              </Field>
              <Button
                onClick={handleTest}
                loading={sendingTest}
                disabled={!status?.email.configured}
                leftIcon={<Send className="h-4 w-4" />}
              >
                Enviar teste
              </Button>
            </div>
          </div>

          {!status?.email.configured && (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
              Pra ativar e-mail, edite o <code>backend/.env</code> com suas credenciais Gmail e
              reinicie o backend. Se ainda não tem App Password do Gmail, gere em{' '}
              <a
                href="https://myaccount.google.com/apppasswords"
                target="_blank"
                rel="noreferrer"
                className="underline"
              >
                myaccount.google.com/apppasswords
              </a>
              .
            </div>
          )}
        </CardBody>
      </Card>

      {/* Scheduler */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-zinc-100">
              <Server className="mr-2 inline h-4 w-4 text-zinc-400" />
              Scheduler de alertas
            </h2>
            <p className="mt-0.5 text-xs text-zinc-500">
              Cada filtro com alerta ativo aparece como um job agendado.
            </p>
          </div>
          {status?.scheduler.running ? (
            <Badge variant="success">rodando</Badge>
          ) : (
            <Badge variant="warning">parado</Badge>
          )}
        </CardHeader>
        <CardBody>
          {status && status.scheduler.scheduled_jobs.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-xs uppercase tracking-wide text-zinc-500">
                  <th className="py-2 text-left font-medium">Job</th>
                  <th className="py-2 text-right font-medium">Próxima execução</th>
                </tr>
              </thead>
              <tbody>
                {status.scheduler.scheduled_jobs.map((j) => (
                  <tr key={j.id} className="border-b border-zinc-900">
                    <td className="py-3 text-zinc-200">{j.name}</td>
                    <td className="py-3 text-right text-zinc-400">
                      {j.next_run_time
                        ? new Date(j.next_run_time).toLocaleString('pt-BR')
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-zinc-500">
              Nenhum job agendado. Crie um filtro com alerta ativo na página "Filtros salvos".
            </p>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
