import type {
  FilterRunResult,
  JobFilter,
  JobsListResponse,
  SavedFilter,
  SavedFilterCreate,
  SavedFilterUpdate,
  ScrapeResult,
  SettingsStatus,
  SourceInfo,
} from './types'
import type {
  CourseFilter,
  CourseScrapeResult,
  CourseSourceInfo,
  CoursesListResponse,
} from './courseTypes'

// Em dev passamos pelo proxy do Vite (/api -> http://127.0.0.1:8765).
// Em prod, define VITE_API_BASE_URL no .env.
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body?.detail ?? JSON.stringify(body)
    } catch {
      // fica com statusText
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; registered_sources: string[] }>('/health'),
  listSources: () => request<SourceInfo[]>('/sources'),
  scrape: (filter: JobFilter) =>
    request<ScrapeResult>('/scrape', {
      method: 'POST',
      body: JSON.stringify(filter),
    }),
  searchExisting: (filter: JobFilter) =>
    request<ScrapeResult>('/jobs/search', {
      method: 'POST',
      body: JSON.stringify(filter),
    }),
  listJobs: (limit = 50, offset = 0) =>
    request<JobsListResponse>(`/jobs?limit=${limit}&offset=${offset}`),

  // ----- Settings -----
  getSettings: () => request<SettingsStatus>('/settings'),
  testEmail: (to?: string) =>
    request<{ sent: boolean; to: string; at: string }>('/filters/test-email', {
      method: 'POST',
      body: JSON.stringify(to ? { to } : {}),
    }),

  // ----- Filtros salvos -----
  listFilters: () => request<SavedFilter[]>('/filters'),
  getFilter: (id: string) => request<SavedFilter>(`/filters/${id}`),
  createFilter: (payload: SavedFilterCreate) =>
    request<SavedFilter>('/filters', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateFilter: (id: string, payload: SavedFilterUpdate) =>
    request<SavedFilter>(`/filters/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteFilter: (id: string) =>
    request<{ deleted: string }>(`/filters/${id}`, { method: 'DELETE' }),
  runFilterNow: (id: string) =>
    request<FilterRunResult>(`/filters/${id}/run-now`, { method: 'POST' }),
  resetFilterSent: (id: string) =>
    request<{ reset: string }>(`/filters/${id}/reset-sent`, { method: 'POST' }),
}

// ----- LearnFinder (certificações/cursos/pós/faculdade) -----

export const courseApi = {
  listSources: () => request<CourseSourceInfo[]>('/course-sources'),
  scrape: (filter: CourseFilter) =>
    request<CourseScrapeResult>('/courses/scrape', {
      method: 'POST',
      body: JSON.stringify(filter),
    }),
  searchExisting: (filter: CourseFilter) =>
    request<CourseScrapeResult>('/courses/search', {
      method: 'POST',
      body: JSON.stringify(filter),
    }),
  listCourses: (limit = 50, offset = 0) =>
    request<CoursesListResponse>(`/courses?limit=${limit}&offset=${offset}`),
}

export { ApiError }
