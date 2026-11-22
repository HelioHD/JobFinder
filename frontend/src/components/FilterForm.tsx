import { Search, RotateCcw } from 'lucide-react'
import {
  DEFAULT_FILTER,
  JOB_TYPE_LABELS,
  KEYWORD_MATCH_LABELS,
  KEYWORD_SCOPE_LABELS,
  LOCATION_MODE_LABELS,
  SENIORITY_LABELS,
  type JobFilter,
  type JobSource,
  type JobType,
  type KeywordMatch,
  type KeywordScope,
  type LocationMode,
  type Seniority,
  type SourceInfo,
} from '../api/types'
import { Field } from './ui/Field'
import { Input } from './ui/Input'
import { Select } from './ui/Select'
import { Button } from './ui/Button'
import { TagInput } from './ui/TagInput'
import { CheckboxGroup } from './ui/CheckboxGroup'
import { Card, CardBody, CardHeader } from './ui/Card'

interface Props {
  value: JobFilter
  onChange: (next: JobFilter) => void
  onSubmit: () => void
  loading?: boolean
  sources: SourceInfo[]
}

const JOB_TYPE_OPTIONS: { value: JobType; label: string }[] = (
  ['full_time', 'part_time', 'freelance', 'contract', 'internship', 'temporary'] as JobType[]
).map((v) => ({ value: v, label: JOB_TYPE_LABELS[v] }))

const SENIORITY_OPTIONS: { value: Seniority; label: string }[] = (
  ['intern', 'junior', 'mid', 'senior', 'lead'] as Seniority[]
).map((v) => ({ value: v, label: SENIORITY_LABELS[v] }))

const LOCATION_OPTIONS: { value: LocationMode; label: string }[] = (
  ['any', 'on_site_region', 'hybrid_region', 'remote_brazil', 'remote_worldwide'] as LocationMode[]
).map((v) => ({ value: v, label: LOCATION_MODE_LABELS[v] }))

export function FilterForm({ value, onChange, onSubmit, loading, sources }: Props) {
  const set = <K extends keyof JobFilter>(key: K, v: JobFilter[K]) =>
    onChange({ ...value, [key]: v })

  const needsRegion =
    value.location_mode === 'on_site_region' || value.location_mode === 'hybrid_region'

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">Buscar vagas</h2>
          <p className="text-xs text-zinc-500">
            Personalize os filtros e clique em buscar.
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onChange(DEFAULT_FILTER)}
          leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
        >
          Limpar
        </Button>
      </CardHeader>
      <CardBody className="space-y-5">
        <div className="grid gap-4 md:grid-cols-2">
          <Field
            label="Palavras-chave"
            hint="Pressione Enter ou vírgula. Reconhece NodeJS↔Node.js, JS↔JavaScript, etc."
          >
            <TagInput
              value={value.keywords}
              onChange={(v) => set('keywords', v)}
              placeholder="adicionar termo..."
            />
          </Field>
          <Field
            label="Excluir palavras"
            hint="Vagas com esses termos serão descartadas."
          >
            <TagInput
              value={value.exclude_keywords}
              onChange={(v) => set('exclude_keywords', v)}
              placeholder="ex.: senior, php"
            />
          </Field>
        </div>

        {value.keywords.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 rounded-lg border border-zinc-800/60 bg-zinc-900/40 p-3">
            <Field label="Como combinar palavras-chave">
              <Select
                value={value.keyword_match}
                onChange={(e) => set('keyword_match', e.target.value as KeywordMatch)}
              >
                {(Object.keys(KEYWORD_MATCH_LABELS) as KeywordMatch[]).map((k) => (
                  <option key={k} value={k}>
                    {KEYWORD_MATCH_LABELS[k]}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Onde procurar">
              <Select
                value={value.keyword_scope}
                onChange={(e) => set('keyword_scope', e.target.value as KeywordScope)}
              >
                {(Object.keys(KEYWORD_SCOPE_LABELS) as KeywordScope[]).map((k) => (
                  <option key={k} value={k}>
                    {KEYWORD_SCOPE_LABELS[k]}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        )}

        <Field label="Tipo de contrato" hint="Vazio = qualquer tipo">
          <CheckboxGroup
            options={JOB_TYPE_OPTIONS}
            selected={value.job_types}
            onChange={(v) => set('job_types', v)}
            columns={3}
          />
        </Field>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Localização">
            <Select
              value={value.location_mode}
              onChange={(e) => set('location_mode', e.target.value as LocationMode)}
            >
              {LOCATION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
          </Field>
          {needsRegion && (
            <Field label="Região / cidade" required hint="Ex.: Brasília-DF, São Paulo-SP">
              <Input
                value={value.region ?? ''}
                onChange={(e) => set('region', e.target.value || null)}
                placeholder="Brasília-DF"
              />
            </Field>
          )}
        </div>

        <Field label="Senioridade" hint="Vazio = qualquer">
          <CheckboxGroup
            options={SENIORITY_OPTIONS}
            selected={value.seniorities}
            onChange={(v) => set('seniorities', v)}
            columns={3}
          />
        </Field>

        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Salário mínimo (R$)" hint="Opcional">
            <Input
              type="number"
              min={0}
              step={500}
              value={value.min_salary ?? ''}
              onChange={(e) =>
                set('min_salary', e.target.value ? Number(e.target.value) : null)
              }
              placeholder="ex.: 5000"
            />
          </Field>
          <Field label="Postada nos últimos">
            <Select
              value={value.posted_within_days ?? ''}
              onChange={(e) =>
                set('posted_within_days', e.target.value ? Number(e.target.value) : null)
              }
            >
              <option value="">Qualquer data</option>
              <option value="1">24 horas</option>
              <option value="3">3 dias</option>
              <option value="7">7 dias</option>
              <option value="30">30 dias</option>
            </Select>
          </Field>
          <Field label="Quantidade máxima">
            <Select
              value={value.limit}
              onChange={(e) => set('limit', Number(e.target.value))}
            >
              <option value={10}>10 vagas</option>
              <option value={25}>25 vagas</option>
              <option value={50}>50 vagas</option>
              <option value={100}>100 vagas</option>
              <option value={200}>200 vagas</option>
            </Select>
          </Field>
        </div>

        {sources.length > 0 && (() => {
          const enabledSources = sources.filter((s) => s.enabled)
          const disabledSources = sources.filter((s) => !s.enabled)
          return (
            <Field label="Fontes" hint="Vazio = todas as ativas">
              <CheckboxGroup
                options={enabledSources.map((s) => ({ value: s.id, label: s.name }))}
                selected={value.sources}
                onChange={(v) => set('sources', v as JobSource[])}
                columns={3}
              />
              {disabledSources.length > 0 && (
                <p className="mt-2 text-[11px] text-zinc-500">
                  Desabilitadas:{' '}
                  {disabledSources.map((s) => s.name).join(', ')} — ative no
                  código (`enabled = True` no scraper) se quiser experimentar.
                </p>
              )}
            </Field>
          )
        })()}

        <div className="flex justify-end pt-2">
          <Button
            onClick={onSubmit}
            loading={loading}
            size="lg"
            leftIcon={<Search className="h-4 w-4" />}
          >
            Buscar vagas
          </Button>
        </div>
      </CardBody>
    </Card>
  )
}
