// Helper minimalista pra mesclar classes condicionais sem dep externa.
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}
