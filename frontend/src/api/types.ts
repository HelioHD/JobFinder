// Tipos espelhados do backend Pydantic. Manter em sync com app/models/job.py.

export type JobType =
  | 'full_time'
  | 'part_time'
  | 'freelance'
  | 'contract'
  | 'internship'
  | 'temporary'
  | 'unknown'

export type LocationMode =
  | 'on_site_region'
  | 'hybrid_region'
  | 'remote_brazil'
  | 'remote_worldwide'
  | 'any'

export type Seniority =
  | 'intern'
  | 'junior'
  | 'mid'
  | 'senior'
  | 'lead'
  | 'unknown'

export type JobSource =
  | 'arbeitnow'
  | 'infojobs'
  | 'remotive'
  | 'linkedin'
  | 'google_jobs'
  | 'vagas_com'
  | 'trampos'
  | 'weworkremotely'
  | 'github_hn'
  | 'indeed'

export interface Job {
  id: string
  source: JobSource
  title: string
  company: string
  location: string
  is_remote: boolean
  job_types: JobType[]
  seniority: Seniority
  description: string
  description_html: string
  url: string
  tags: string[]
  salary_text: string | null
  posted_at: string | null
  scraped_at: string
}

export type KeywordMatch = 'any' | 'all'
export type KeywordScope = 'title_only' | 'title_or_short' | 'everywhere'

export interface JobFilter {
  keywords: string[]
  keyword_match: KeywordMatch
  keyword_scope: KeywordScope
  exclude_keywords: string[]
  job_types: JobType[]
  location_mode: LocationMode
  region: string | null
  seniorities: Seniority[]
  min_salary: number | null
  posted_within_days: number | null
  sources: JobSource[]
  sort_by: 'recent' | 'relevance'
  limit: number
}

export interface ScrapeResult {
  total_found: number
  new_jobs: number
  sources_used: JobSource[]
  jobs: Job[]
  errors: string[]
}

export interface SourceInfo {
  id: JobSource
  name: string
  description: string
  enabled: boolean
}

export interface JobsListResponse {
  total: number
  limit: number
  offset: number
  items: Job[]
}

// ----- Filtros salvos / alertas -----

export type AlertFrequency = 'hourly' | 'every_4h' | 'daily' | 'weekly'

export interface SavedFilter {
  id: string
  name: string
  filter: JobFilter
  alert_enabled: boolean
  alert_frequency: AlertFrequency
  recipient_email: string | null
  only_new: boolean
  last_run_at: string | null
  last_email_at: string | null
  last_run_status: string | null
  total_emails_sent: number
  created_at: string
  updated_at: string
}

export interface SavedFilterCreate {
  name: string
  filter: JobFilter
  alert_enabled: boolean
  alert_frequency: AlertFrequency
  recipient_email?: string | null
  only_new: boolean
}

export interface SavedFilterUpdate {
  name?: string
  filter?: JobFilter
  alert_enabled?: boolean
  alert_frequency?: AlertFrequency
  recipient_email?: string | null
  only_new?: boolean
}

export interface FilterRunResult {
  filter_id: string
  filter_name: string
  total_found: number
  new_jobs_for_filter: number
  emailed: boolean
  email_recipient: string | null
  errors: string[]
  ran_at: string
}

// ----- Settings -----

export interface SettingsStatus {
  email: {
    configured: boolean
    user: string
    masked_password: string
    default_recipient: string
    smtp_host: string
    smtp_port: number
  }
  scheduler: {
    running: boolean
    scheduled_jobs: { id: string; name: string; next_run_time: string | null }[]
  }
}

export const DEFAULT_FILTER: JobFilter = {
  keywords: [],
  keyword_match: 'any',
  keyword_scope: 'title_or_short',
  exclude_keywords: [],
  job_types: [],
  location_mode: 'any',
  region: null,
  seniorities: [],
  min_salary: null,
  posted_within_days: null,
  sources: [],
  sort_by: 'recent',
  limit: 50,
}

export const KEYWORD_MATCH_LABELS: Record<KeywordMatch, string> = {
  any: 'Qualquer uma das palavras',
  all: 'Todas as palavras',
}

export const KEYWORD_SCOPE_LABELS: Record<KeywordScope, string> = {
  title_only: 'Só no título e tags (estrito)',
  title_or_short: 'Título, tags e início da descrição',
  everywhere: 'Em qualquer parte da vaga (mais permissivo)',
}

// ----- Labels em português pra UI -----

export const JOB_TYPE_LABELS: Record<JobType, string> = {
  full_time: 'Full-time',
  part_time: 'Part-time',
  freelance: 'Freelancer',
  contract: 'Contrato / PJ',
  internship: 'Estágio',
  temporary: 'Temporário',
  unknown: 'Não informado',
}

export const LOCATION_MODE_LABELS: Record<LocationMode, string> = {
  any: 'Qualquer (sem filtro)',
  on_site_region: 'Presencial em região',
  hybrid_region: 'Híbrido em região',
  remote_brazil: 'Remoto (Brasil)',
  remote_worldwide: 'Remoto (Mundo)',
}

export const SENIORITY_LABELS: Record<Seniority, string> = {
  intern: 'Estagiário',
  junior: 'Júnior',
  mid: 'Pleno',
  senior: 'Sênior',
  lead: 'Lead / Staff',
  unknown: 'Não informado',
}

export const SOURCE_LABELS: Record<JobSource, string> = {
  arbeitnow: 'Arbeitnow',
  infojobs: 'InfoJobs',
  remotive: 'Remotive',
  linkedin: 'LinkedIn',
  google_jobs: 'Google Jobs',
  vagas_com: 'Vagas.com',
  trampos: 'Trampos.co',
  weworkremotely: 'We Work Remotely',
  github_hn: 'GitHub/HN',
  indeed: 'Indeed Brasil',
}

export const ALERT_FREQ_LABELS: Record<AlertFrequency, string> = {
  hourly: 'A cada hora',
  every_4h: 'A cada 4 horas',
  daily: 'Diariamente (manhã)',
  weekly: 'Semanalmente (segunda)',
}
