import { api } from './client'
import type { Alert, AlertEvent, AlertInput } from './types'
import type { NotificationStatus } from './types'

export type { NotificationStatus }

export async function fetchAlerts(): Promise<Alert[]> {
  const { data } = await api.get<Alert[]>('/api/alerts')
  return data
}

export async function fetchAlertEvents(limit = 30): Promise<AlertEvent[]> {
  const { data } = await api.get<AlertEvent[]>('/api/alerts/events', {
    params: { limit },
  })
  return data
}

export async function createAlert(input: AlertInput): Promise<Alert> {
  const { data } = await api.post<Alert>('/api/alerts', input)
  return data
}

export async function toggleAlert(id: number): Promise<Alert> {
  const { data } = await api.post<Alert>(`/api/alerts/${id}/toggle`)
  return data
}

export async function deleteAlert(id: number): Promise<void> {
  await api.delete(`/api/alerts/${id}`)
}

export async function fetchNotificationStatus(): Promise<NotificationStatus> {
  const { data } = await api.get<NotificationStatus>('/api/alerts/notifications')
  return data
}

export async function sendTestNotification(): Promise<NotificationStatus> {
  const { data } = await api.post<NotificationStatus>('/api/alerts/notifications/test')
  return data
}
