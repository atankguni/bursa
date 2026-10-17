import { api } from './client'

export type Role = 'user' | 'admin'

export interface Me {
  id: number
  email: string
  name: string
  role: Role
  has_2fa: boolean
  /** Admin without 2FA: only the 2FA setup works until it's turned on. */
  mfa_setup_required: boolean
}

export type TwoFactorMethod = 'totp' | 'email' | 'recovery'

/** The password was right; a code is needed to finish signing in. */
export interface TwoFactorChallenge {
  token: string
  /** Usable now, preferred first. */
  methods: TwoFactorMethod[]
  email_hint: string
  email_sent: boolean
}

export interface LoginResult {
  user: Me | null
  two_factor: TwoFactorChallenge | null
}

export interface TwoFactorStatus {
  totp: boolean
  email: boolean
  /** Email is set up on the server (needed for email codes). */
  email_available: boolean
  recovery_codes_left: number
  trusted_devices: number
  /** Admins must keep 2FA on. */
  required: boolean
}

export interface TotpSetup {
  secret: string
  uri: string
  qr_svg: string
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
