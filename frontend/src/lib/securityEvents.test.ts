import { describe, expect, it } from 'vitest'
import type { SecurityEvent } from '../api'
import { eventLabel, isNotable } from './securityEvents'

const event = (patch: Partial<SecurityEvent>): SecurityEvent => ({
  id: 1,
  kind: 'sign_in',
  at: '2026-10-23T07:00:00Z',
  ip: null,
  device: 'Chrome on macOS',
  new_device: false,
  detail: null,
  ...patch,
})

describe('eventLabel', () => {
  it('adds the detail, or flags a new device', () => {
    expect(eventLabel(event({}))).toBe('Signed in')
    expect(eventLabel(event({ new_device: true }))).toBe('Signed in (new device)')
    expect(eventLabel(event({ kind: 'role_changed', detail: 'to admin by Ana' }))).toBe(
      'Role changed (to admin by Ana)',
    )
  })
})

describe('isNotable', () => {
  it('highlights what deserves a second look', () => {
    expect(isNotable(event({}))).toBe(false)
    expect(isNotable(event({ new_device: true }))).toBe(true)
    expect(isNotable(event({ kind: 'sign_in_failed' }))).toBe(true)
    expect(isNotable(event({ kind: 'password_changed' }))).toBe(false)
  })
})
