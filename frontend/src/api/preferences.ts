import { api } from './client'
import type { Preferences } from './types'

export async function fetchPreferences(): Promise<Preferences> {
  const { data } = await api.get<Preferences>('/api/preferences')
  return data
}

/** Partial update: only the fields sent change. */
export async function updatePreferences(
  prefs: Partial<Preferences>,
): Promise<Preferences> {
  const { data } = await api.put<Preferences>('/api/preferences', prefs)
  return data
}
