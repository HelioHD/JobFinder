import { useEffect, useState } from 'react'
import { Save } from 'lucide-react'
import { api, ApiError } from '../api/client'
import {
  ALERT_FREQ_LABELS,
  type AlertFrequency,
  type JobFilter,
  type SavedFilter,
  type SettingsStatus,
} from '../api/types'
import { Modal } from './ui/Modal'
import { Field } from './ui/Field'
import { Input } from './ui/Input'
import { Select } from './ui/Select'
import { Button } from './ui/Button'

interface Props {
  open: boolean
  onClose: () => void
  filter: JobFilter
  /** Se passado, edita o filtro existente em vez de criar um novo. */
  editing?: SavedFilter | null
  onSaved: (saved: SavedFilter) => void
}

export function SaveFilterModal({ open, onClose, filter, editing, onSaved }: Props) {
  const isEdit = Boolean(editing)
  const [name, setName] = useState('')
  const [recipient, setRecipient] = useState('')
  const [frequency, setFrequency] = useState<AlertFrequency>('daily')
  const [alertEnabled, setAlertEnabled] = useState(true)
  const [onlyNew, setOnlyNew] = useState(true)
  const [defaultRecipient, setDefaultRecipient] = useState('')
  const [emailConfigured, setEmailConfigured] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setError(null)
    if (editing) {
      setName(editing.name)
      setRecipient(editing.recipient_email ?? '')
      setFrequency(editing.alert_frequency)
      setAlertEnabled(editing.alert_enabled)
      setOnlyNew(editing.only_new)
    } else {
      setName('')
      setRecipient('')
      setFrequency('daily')
      setAlertEnabled(true)
      setOnlyNew(true)
    }
    api
      .getSettings()
      .then((s) => {
        setDefaultRecipient(s.email.default_recipient)
        setEmailConfigured(s.email.configured)
      })
      .catch(() => {
        setEmailConfigured(false)
      })
  }, [open, editing])

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Dê um nome pro filtro.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      let saved: SavedFilter
      if (isEdit && editing) {
        saved = await api.updateFilter(editing.id, {
          name: name.trim(),
          filter,
          alert_enabled: alertEnabled,
          alert_frequency: frequency,
          recipient_email: recipient.trim() || null,
          only_new: onlyNew,
        })
      } else {
        saved = await api.createFilter({
          name: name.trim(),
          filter,
          alert_enabled: alertEnabled,
          alert_frequency: frequency,
          recipient_email: recipient.trim() || null,
          only_new: onlyNew,
        })
      }
      onSaved(saved)
      onClose()
    } catch (e) {
      const msg = e instanceof ApiError ? `${e.status}: ${e.message}` : (e as Error).message
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => !saving && onClose()}
      title={isEdit ? 'Editar filtro salvo' : 'Salvar filtro'}
      description={
        isEdit
          ? 'Atualize o nome ou as configurações de alerta deste filtro.'
          : 'Dê um nome pro filtro atual e configure como receber alertas.'
      }
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancelar
          </Button>
          <Button onClick={handleSave} loading={saving} leftIcon={<Save className="h-4 w-4" />}>
            {isEdit ? 'Salvar alterações' : 'Salvar filtro'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Nome do filtro" required>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ex.: Vagas JS/TS Brasília"
            autoFocus
          />
        </Field>

        <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-zinc-200">Alerta automático por e-mail</p>
              <p className="mt-0.5 text-xs text-zinc-500">
                O sistema vai rodar este filtro periodicamente e te avisar quando aparecer vaga nova.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setAlertEnabled((v) => !v)}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${
                alertEnabled ? 'bg-indigo-500' : 'bg-zinc-700'
              }`}
              aria-pressed={alertEnabled}
              aria-label="Ativar alerta"
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  alertEnabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {alertEnabled && (
            <div className="space-y-3">
              <Field label="Frequência">
                <Select
                  value={frequency}
                  onChange={(e) => setFrequency(e.target.value as AlertFrequency)}
                >
                  {(Object.keys(ALERT_FREQ_LABELS) as AlertFrequency[]).map((k) => (
                    <option key={k} value={k}>
                      {ALERT_FREQ_LABELS[k]}
                    </option>
                  ))}
                </Select>
              </Field>

              <Field
                label="E-mail destinatário"
                hint={
                  defaultRecipient
                    ? `Em branco usa o padrão: ${defaultRecipient}`
                    : 'Em branco usa DEFAULT_RECIPIENT do .env'
                }
              >
                <Input
                  type="email"
                  value={recipient}
                  onChange={(e) => setRecipient(e.target.value)}
                  placeholder={defaultRecipient || 'voce@email.com'}
                />
              </Field>

              <label className="flex cursor-pointer items-start gap-3 rounded-md p-2 hover:bg-zinc-900">
                <input
                  type="checkbox"
                  checked={onlyNew}
                  onChange={(e) => setOnlyNew(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-indigo-500 focus:ring-indigo-400"
                />
                <div>
                  <p className="text-sm text-zinc-200">Só notificar quando houver vagas novas</p>
                  <p className="mt-0.5 text-xs text-zinc-500">
                    (recomendado) Evita spam — só manda e-mail se aparecer vaga que ainda não foi enviada pra esse filtro.
                  </p>
                </div>
              </label>

              {!emailConfigured && (
                <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
                  Atenção: o servidor SMTP do Gmail ainda não está configurado. O filtro será salvo, mas
                  os e-mails só serão enviados depois de configurar <code>GMAIL_USER</code> e{' '}
                  <code>GMAIL_APP_PASSWORD</code> no <code>.env</code>.
                </div>
              )}
            </div>
          )}
        </div>

        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
            {error}
          </div>
        )}
      </div>
    </Modal>
  )
}
