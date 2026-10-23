import { api } from './client'
import type {
  AdminSecurityEvent,
  AdminUser,
  OneTimeLink,
  PendingInvite,
  Role,
} from './types'

export type { AdminUser, PendingInvite, OneTimeLink, AdminSecurityEvent }

/** Everyone's latest account activity. */
export async function fetchSecurityLog(): Promise<AdminSecurityEvent[]> {
  const { data } = await api.get<AdminSecurityEvent[]>('/api/admin/security-log')
  return data
}

export async function fetchUsers(): Promise<AdminUser[]> {
  const { data } = await api.get<AdminUser[]>('/api/admin/users')
  return data
}

export async function updateUser(
  id: number,
  patch: Partial<Pick<AdminUser, 'role' | 'is_active'>>,
): Promise<AdminUser> {
  const { data } = await api.patch<AdminUser>(`/api/admin/users/${id}`, patch)
  return data
}

export async function deleteUser(id: number): Promise<void> {
  await api.delete(`/api/admin/users/${id}`)
}

export async function createResetLink(id: number): Promise<OneTimeLink> {
  const { data } = await api.post<OneTimeLink>(`/api/admin/users/${id}/reset-link`)
  return data
}

/** Turn off a user's 2FA (they lost their phone and recovery codes). */
export async function resetTwoFactor(id: number): Promise<AdminUser> {
  const { data } = await api.post<AdminUser>(`/api/admin/users/${id}/reset-2fa`)
  return data
}

export async function fetchInvites(): Promise<PendingInvite[]> {
  const { data } = await api.get<PendingInvite[]>('/api/admin/invites')
  return data
}

export async function createInvite(email: string, role: Role): Promise<OneTimeLink> {
  const { data } = await api.post<OneTimeLink>('/api/admin/invites', { email, role })
  return data
}

export async function revokeInvite(id: number): Promise<void> {
  await api.delete(`/api/admin/invites/${id}`)
}
