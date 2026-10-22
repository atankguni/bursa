import { api } from './client'
import type { DataHealth, HealthStatus, JobHealth } from './types'

export type { HealthStatus, JobHealth, DataHealth }

export async function fetchDataHealth(): Promise<DataHealth> {
  const { data } = await api.get<DataHealth>('/api/data-health', { timeout: 60_000 })
  return data
}
