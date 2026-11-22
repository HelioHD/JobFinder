import { Inbox } from 'lucide-react'
import type { Course } from '../api/courseTypes'
import { CourseCard } from './CourseCard'

interface Props {
  courses: Course[]
  loading?: boolean
  emptyTitle?: string
  emptyDescription?: string
}

export function CourseList({
  courses,
  loading,
  emptyTitle = 'Nada encontrado',
  emptyDescription = 'Tente ajustar o tema, o tipo ou aumentar o teto de preço.',
}: Props) {
  if (loading) {
    return (
      <div className="grid gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-40 animate-pulse rounded-xl border border-zinc-800 bg-zinc-900/40"
          />
        ))}
      </div>
    )
  }

  if (courses.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-800 px-8 py-16 text-center">
        <Inbox className="h-10 w-10 text-zinc-600" />
        <p className="mt-4 text-base font-medium text-zinc-300">{emptyTitle}</p>
        <p className="mt-1 max-w-sm text-sm text-zinc-500">{emptyDescription}</p>
      </div>
    )
  }

  return (
    <div className="grid gap-3">
      {courses.map((c) => (
        <CourseCard key={c.id} course={c} />
      ))}
    </div>
  )
}
