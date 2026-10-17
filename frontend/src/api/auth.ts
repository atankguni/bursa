import { api } from './client'

export type Role = 'user' | 'admin'

export interface Me {
  id: number
  email: string
  name: string
  role: Role
}

export interface AuthOptions {
  password_reset_by_email: boolean
  password_min_length: number
}

export interface InviteInfo {
  /** null = setup invite: the first admin chooses their email. */
  email: string | null
  role: Role
}

/** The signed-in user, or null when signed out. */
export async function fetchMe(): Promise<Me | null> {
  try {
    const { data } = await api.get<Me>('/api/auth/me')
    return data
  } catch (error) {
    if ((error as { response?: { status?: number } })?.response?.status === 401) return null
    throw error
  }
}

export async function fetchAuthOptions(): Promise<AuthOptions> {
  const { data } = await api.get<AuthOptions>('/api/auth/options')
  return data
}

export async function login(email: string, password: string): Promise<Me> {
  const { data } = await api.post<Me>('/api/auth/login', { email, password })
  return data
}

export async function logout(): Promise<void> {
  await api.post('/api/auth/logout')
}

export async function changePassword(current: string, next: string): Promise<void> {
  await api.post('/api/auth/password', { current_password: current, new_password: next })
}

export async function fetchInvite(token: string): Promise<InviteInfo> {
  const { data } = await api.get<InviteInfo>(`/api/auth/invites/${encodeURIComponent(token)}`)
  return data
}

export async function acceptInvite(
  token: string,
  body: { name: string; password: string; email?: string },
): Promise<Me> {
  const { data } = await api.post<Me>(
    `/api/auth/invites/${encodeURIComponent(token)}/accept`,
    body,
  )
  return data
}

export async function requestPasswordReset(email: string): Promise<void> {
  await api.post('/api/auth/password-reset', { email })
}

export async function checkResetToken(token: string): Promise<void> {
  await api.get(`/api/auth/password-reset/${encodeURIComponent(token)}`)
}

export async function resetPassword(token: string, password: string): Promise<void> {
  await api.post(`/api/auth/password-reset/${encodeURIComponent(token)}`, { password })
}
