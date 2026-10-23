import { api, errorStatus } from './client'
import type {
  AuthOptions,
  InviteInfo,
  LoginResult,
  Me,
  Role,
  SecurityEvent,
  SignedInSession,
  TotpSetup,
  TwoFactorChallenge,
  TwoFactorMethod,
  TwoFactorStatus,
} from './types'

export type {
  Role,
  Me,
  TwoFactorMethod,
  TwoFactorChallenge,
  LoginResult,
  TwoFactorStatus,
  TotpSetup,
  AuthOptions,
  InviteInfo,
  SignedInSession,
  SecurityEvent,
}

/** The signed-in user, or null when signed out. */
export async function fetchMe(): Promise<Me | null> {
  try {
    const { data } = await api.get<Me>('/api/auth/me')
    return data
  } catch (error) {
    if (errorStatus(error) === 401) return null
    throw error
  }
}

export async function fetchAuthOptions(): Promise<AuthOptions> {
  const { data } = await api.get<AuthOptions>('/api/auth/options')
  return data
}

export async function login(email: string, password: string): Promise<LoginResult> {
  const { data } = await api.post<LoginResult>('/api/auth/login', { email, password })
  return data
}

export async function verifyTwoFactor(body: {
  token: string
  method: TwoFactorMethod
  code: string
  remember_device: boolean
}): Promise<Me> {
  const { data } = await api.post<Me>('/api/auth/2fa/verify', body)
  return data
}

export async function resendTwoFactorEmail(token: string): Promise<void> {
  await api.post('/api/auth/2fa/resend', { token })
}

export async function fetchTwoFactorStatus(): Promise<TwoFactorStatus> {
  const { data } = await api.get<TwoFactorStatus>('/api/auth/2fa')
  return data
}

export async function startTotpSetup(): Promise<TotpSetup> {
  const { data } = await api.post<TotpSetup>('/api/auth/2fa/totp')
  return data
}

/** Returns new recovery codes when 2FA was off before (shown once). */
export async function confirmTotp(code: string): Promise<string[] | null> {
  const { data } = await api.post<{ recovery_codes: string[] | null }>(
    '/api/auth/2fa/totp/confirm',
    { code },
  )
  return data.recovery_codes
}

export async function startEmailSetup(): Promise<void> {
  await api.post('/api/auth/2fa/email')
}

export async function confirmEmail(code: string): Promise<string[] | null> {
  const { data } = await api.post<{ recovery_codes: string[] | null }>(
    '/api/auth/2fa/email/confirm',
    { code },
  )
  return data.recovery_codes
}

export async function disableTwoFactor(
  method: 'totp' | 'email',
  password: string,
): Promise<void> {
  await api.post(`/api/auth/2fa/${method}/disable`, { password })
}

export async function regenerateRecoveryCodes(password: string): Promise<string[]> {
  const { data } = await api.post<{ recovery_codes: string[] }>(
    '/api/auth/2fa/recovery-codes',
    { password },
  )
  return data.recovery_codes
}

export async function forgetTrustedDevices(): Promise<void> {
  await api.delete('/api/auth/2fa/trusted-devices')
}

/** Browsers signed in to your account, most recently used first. */
export async function fetchSessions(): Promise<SignedInSession[]> {
  const { data } = await api.get<SignedInSession[]>('/api/auth/sessions')
  return data
}

export async function revokeSession(id: number): Promise<void> {
  await api.delete(`/api/auth/sessions/${id}`)
}

/** Sign out every browser but this one. */
export async function signOutOtherSessions(): Promise<void> {
  await api.post('/api/auth/sessions/sign-out-others')
}

/** Your latest account activity (sign-ins, password and 2FA changes). */
export async function fetchActivity(): Promise<SecurityEvent[]> {
  const { data } = await api.get<SecurityEvent[]>('/api/auth/activity')
  return data
}

/** Someone used this page just now (keeps the inactivity lock away). */
export async function reportActivity(): Promise<void> {
  await api.post('/api/auth/active')
}

/** Lock this browser now; the password unlocks it. */
export async function lockSession(): Promise<void> {
  await api.post('/api/auth/lock')
}

/** Unlock with the password (no 2FA code). 401: signed out after too many tries. */
export async function unlockSession(password: string): Promise<Me> {
  const { data } = await api.post<Me>('/api/auth/unlock', { password })
  return data
}

export async function logout(): Promise<void> {
  await api.post('/api/auth/logout')
}

export async function changePassword(current: string, next: string): Promise<void> {
  await api.post('/api/auth/password', { current_password: current, new_password: next })
}

export async function fetchInvite(token: string): Promise<InviteInfo> {
  const { data } = await api.get<InviteInfo>(
    `/api/auth/invites/${encodeURIComponent(token)}`,
  )
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
