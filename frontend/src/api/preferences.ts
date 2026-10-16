import { api } from './client'
import type { Preferences } from './types'

export async function fetchPreferences(): Promise<Preferences> {
  const { data } = await api.get<Preferences>('/api/preferences')
  return data
}

export async function updatePreferences(prefs: Preferences): Promise<Preferences> {
  const { data } = await api.put<Preferences>('/api/preferences', prefs)
  return data
}
