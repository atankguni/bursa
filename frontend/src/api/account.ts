// Your own account: name, email (changed by a confirmation link), and your data.
import { api } from './client'
import type { EmailChange, Me } from './types'

export async function changeName(name: string): Promise<Me> {
  const { data } = await api.put<Me>('/api/account/name', { name })
  return data
}

/** A change waiting for its link to be opened, or null. */
export async function fetchEmailChange(): Promise<EmailChange | null> {
  const { data } = await api.get<EmailChange | null>('/api/account/email-change')
  return data
}

/** Sends a confirmation link to the new address (409 when email isn't set up). */
export async function requestEmailChange(
  newEmail: string,
  password: string,
): Promise<EmailChange> {
  const { data } = await api.post<EmailChange>('/api/account/email-change', {
    new_email: newEmail,
    password,
  })
  return data
}

export async function cancelEmailChange(): Promise<void> {
  await api.delete('/api/account/email-change')
}

/** Public: what a confirmation link would change (404 when invalid or expired). */
export async function checkEmailChange(token: string): Promise<EmailChange> {
  const { data } = await api.get<EmailChange>(
    `/api/account/email-change/${encodeURIComponent(token)}`,
  )
  return data
}

/** Public: switch the account to the new address. */
export async function confirmEmailChange(token: string): Promise<EmailChange> {
  const { data } = await api.post<EmailChange>(
    `/api/account/email-change/${encodeURIComponent(token)}`,
  )
  return data
}

/** Deletes your transactions, cash movements and notes (watchlist and alerts stay). */
export async function clearPortfolio(password: string): Promise<void> {
  await api.post('/api/account/clear-portfolio', { password })
}

/** Deletes your account and everything in it, and signs out. */
export async function deleteAccount(password: string): Promise<void> {
  await api.post('/api/account/delete', { password, confirm: 'DELETE' })
}
