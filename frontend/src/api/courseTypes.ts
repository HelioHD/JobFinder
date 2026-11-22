// Tipos do domínio LearnFinder. Manter em sync com app/models/course.py.

export type CourseType = 'certification' | 'course' | 'postgrad' | 'college'

export type CourseSource = 'udemy' | 'curated' | 'web_search'

export interface Course {
  id: string
  source: CourseSource
  course_type: CourseType
  provider: string
  title: string
  description: string
  url: string
  theme_tags: string[]
  price: number | null
  currency: string
  has_certificate: boolean | null
  duration_text: string | null
  rating: number | null
  scraped_at: string
}

export type CourseKeywordMatch = 'any' | 'all'
export type CourseKeywordScope = 'title_only' | 'title_or_short' | 'everywhere'
export type CourseSortBy = 'relevance' | 'price_asc' | 'price_desc' | 'rating_desc'

export interface CourseFilter {
  keywords: string[]
  keyword_match: CourseKeywordMatch
  keyword_scope: CourseKeywordScope
  course_types: CourseType[]
  max_price: number | null
  require_certificate: boolean
  sources: CourseSource[]
  sort_by: CourseSortBy
  limit: number
}

export interface CourseScrapeResult {
  total_found: number
  new_courses: number
  sources_used: CourseSource[]
  courses: Course[]
  errors: string[]
}

export interface CourseSourceInfo {
  id: CourseSource
  name: string
  description: string
  enabled: boolean
}

export interface CoursesListResponse {
  total: number
  limit: number
  offset: number
  items: Course[]
}

export const DEFAULT_COURSE_FILTER: CourseFilter = {
  keywords: [],
  keyword_match: 'any',
  keyword_scope: 'title_or_short',
  course_types: [],
  max_price: 0,
  require_certificate: true,
  sources: [],
  sort_by: 'relevance',
  limit: 50,
}

export const COURSE_TYPE_LABELS: Record<CourseType, string> = {
  certification: 'Certificação',
  course: 'Curso',
  postgrad: 'Pós-graduação',
  college: 'Faculdade',
}

export const COURSE_SOURCE_LABELS: Record<CourseSource, string> = {
  udemy: 'Udemy',
  curated: 'Curado (certificações/pós)',
  web_search: 'Busca no Google',
}

export const COURSE_SORT_LABELS: Record<CourseSortBy, string> = {
  relevance: 'Relevância',
  price_asc: 'Menor preço',
  price_desc: 'Maior preço',
  rating_desc: 'Melhor avaliação',
}
