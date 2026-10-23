import type { SecurityEvent, SecurityEventKind } from '../api'

const LABELS: Record<SecurityEventKind, string> = {
  account_created: 'Account created',
  sign_in: 'Signed in',
  sign_in_failed: 'Failed sign-in',
  session_revoked: 'Signed out a device',
  other_sessions_revoked: 'Signed out other devices',
  password_changed: 'Password changed',
  password_reset: 'Password reset',
  reset_link_created: 'Password reset link created',
  two_factor_enabled: 'Two-factor turned on',
  two_factor_disabled: 'Two-factor turned off',
  two_factor_reset: 'Two-factor reset',
  recovery_codes_regenerated: 'New recovery codes',
  trusted_devices_forgotten: 'Remembered devices forgotten',
  account_disabled: 'Account disabled',
  account_enabled: 'Account enabled',
  role_changed: 'Role changed',
  session_unlocked: 'Unlocked after inactivity',
}

/** "Signed in (new device)", "Two-factor turned off (email codes)". */
export function eventLabel(event: SecurityEvent): string {
  const extra = event.new_device ? 'new device' : event.detail
  return extra ? `${LABELS[event.kind]} (${extra})` : LABELS[event.kind]
}

const WORTH_A_LOOK = new Set<SecurityEventKind>([
  'sign_in_failed',
  'two_factor_disabled',
  'two_factor_reset',
  'account_disabled',
])

/** Entries to check if they weren't you: highlighted in the lists. */
export const isNotable = (event: SecurityEvent) =>
  event.new_device || WORTH_A_LOOK.has(event.kind)
