import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { Search, Briefcase, Bookmark, Settings, Compass, GraduationCap } from 'lucide-react'
import { cn } from '../lib/cn'

const NAV = [
  { to: '/', label: 'Buscar', icon: Search, end: true, soon: false },
  { to: '/jobs', label: 'Vagas coletadas', icon: Briefcase, end: false, soon: false },
  { to: '/saved', label: 'Filtros salvos', icon: Bookmark, end: false, soon: false },
  { to: '/learn', label: 'LearnFinder', icon: GraduationCap, end: false, soon: false },
  { to: '/settings', label: 'Configurações', icon: Settings, end: false, soon: false },
]

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full min-h-screen bg-zinc-950">
      <aside className="sticky top-0 flex h-screen w-60 flex-shrink-0 flex-col border-r border-zinc-800 bg-zinc-950 px-3 py-5">
        <div className="mb-6 flex items-center gap-2 px-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/30">
            <Compass className="h-4 w-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-zinc-100">JobFinder</p>
            <p className="text-[10px] uppercase tracking-wider text-zinc-500">v0.6 · 8 fontes</p>
          </div>
        </div>

        <nav className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon, end, soon }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-zinc-800 text-zinc-100'
                    : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200',
                )
              }
            >
              <Icon className="h-4 w-4" />
              <span className="flex-1">{label}</span>
              {soon && (
                <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-zinc-500">
                  em breve
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
          <p className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
            Fontes ativas
          </p>
          <ul className="mt-2 space-y-1 text-xs text-zinc-400">
            <li>· Vagas.com · InfoJobs · Trampos</li>
            <li>· LinkedIn (público)</li>
            <li>· WWR · Remotive · Arbeitnow</li>
          </ul>
          <p className="mt-3 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
            Próximas etapas
          </p>
          <ul className="mt-2 space-y-1 text-xs text-zinc-400">
            <li>· Exportar CSV</li>
            <li>· Ordenação por relevância</li>
          </ul>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-5xl px-6 py-8">{children}</div>
      </main>
    </div>
  )
}
