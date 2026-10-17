import { api } from './client'
import type { Role } from './auth'

export interface AdminUser {
  id: number
  email: string
  name: string
  role: Role
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface PendingInvite {
  id: number
  email: string
  role: Role
  created_at: string
  expires_at: string
}

/** A one-time link, shown once (the server keeps only its hash). */
export interface OneTimeLink {
  link: string
  emailed: boolean
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
