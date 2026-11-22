import { Search, RotateCcw } from 'lucide-react'
import {
  COURSE_SORT_LABELS,
  COURSE_TYPE_LABELS,
  DEFAULT_COURSE_FILTER,
  type CourseFilter,
  type CourseSortBy,
  type CourseSource,
  type CourseSourceInfo,
  type CourseType,
} from '../api/courseTypes'
import { Field } from './ui/Field'
import { Input } from './ui/Input'
import { Select } from './ui/Select'
import { Button } from './ui/Button'
import { TagInput } from './ui/TagInput'
import { CheckboxGroup } from './ui/CheckboxGroup'
import { Card, CardBody, CardHeader } from './ui/Card'

interface Props {
  value: CourseFilter
  onChange: (next: CourseFilter) => void
  onSubmit: () => void
  loading?: boolean
  sources: CourseSourceInfo[]
}

const COURSE_TYPE_OPTIONS: { value: CourseType; label: string }[] = (
  ['certification', 'course', 'postgrad', 'college'] as CourseType[]
).map((v) => ({ value: v, label: COURSE_TYPE_LABELS[v] }))

export function CourseFilterForm({ value, onChange, onSubmit, loading, sources }: Props) {
  const set = <K extends keyof CourseFilter>(key: K, v: CourseFilter[K]) =>
    onChange({ ...value, [key]: v })

  const isFreeOnly = value.max_price === 0

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-100">Buscar certificações e cursos</h2>
          <p className="text-xs text-zinc-500">
            Digite um tema (ex.: "red team", "pentest") e ajuste tipo/preço.
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onChange(DEFAULT_COURSE_FILTER)}
          leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
        >
          Limpar
        </Button>
      </CardHeader>
      <CardBody className="space-y-5">
        <Field label="Tema" hint="Pressione Enter ou vírgula. Ex.: red team, pentest, comptia">
          <TagInput
            value={value.keywords}
            onChange={(v) => set('keywords', v)}
            placeholder="adicionar tema..."
          />
        </Field>

        <Field label="Tipo" hint="Vazio = qualquer tipo">
          <CheckboxGroup
            options={COURSE_TYPE_OPTIONS}
            selected={value.course_types}
            onChange={(v) => set('course_types', v)}
            columns={2}
          />
        </Field>

        <div className="grid gap-4 md:grid-cols-2">
          <Field
            label="Preço máximo (R$)"
            hint="0 = só gratuito. Deixe em branco pra não ter teto."
          >
            <div className="flex gap-2">
              <Input
                type="number"
                min={0}
                step={50}
                value={value.max_price ?? ''}
                onChange={(e) =>
                  set('max_price', e.target.value === '' ? null : Number(e.target.value))
                }
                placeholder="sem teto"
              />
              <Button
                type="button"
                variant={isFreeOnly ? 'primary' : 'secondary'}
                size="md"
                onClick={() => set('max_price', 0)}
              >
                Grátis
              </Button>
            </div>
          </Field>
          <Field label="Ordenar por">
            <Select
              value={value.sort_by}
              onChange={(e) => set('sort_by', e.target.value as CourseSortBy)}
            >
              {(Object.keys(COURSE_SORT_LABELS) as CourseSortBy[]).map((k) => (
                <option key={k} value={k}>
                  {COURSE_SORT_LABELS[k]}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <Field label="Certificado" hint="Só mostrar itens que emitem certificado">
          <CheckboxGroup
            options={[{ value: 'require_certificate', label: 'Exigir certificado' }]}
            selected={value.require_certificate ? ['require_certificate'] : []}
            onChange={(v) => set('require_certificate', v.includes('require_certificate'))}
            columns={1}
          />
        </Field>

        {sources.length > 0 && (() => {
          const enabledSources = sources.filter((s) => s.enabled)
          const disabledSources = sources.filter((s) => !s.enabled)
          return (
            <Field label="Fontes" hint="Vazio = todas as ativas (dados curados já ficam incluídos automaticamente)">
              <CheckboxGroup
                options={enabledSources.map((s) => ({ value: s.id, label: s.name }))}
                selected={value.sources}
                onChange={(v) => set('sources', v as CourseSource[])}
                columns={2}
              />
              {disabledSources.length > 0 && (
                <p className="mt-2 text-[11px] text-zinc-500">
                  {disabledSources.map((s) => s.name).join(', ')} — sem scraping ao vivo, dados já
                  incluídos no acervo.
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
            Buscar
          </Button>
        </div>
      </CardBody>
    </Card>
  )
}
