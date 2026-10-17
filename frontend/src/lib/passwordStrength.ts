import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ZxcvbnFactory } from '@zxcvbn-ts/core'
import { fetchAuthOptions } from '../api'

/**
 * Live password strength for the "new password" forms, mirroring the server's
 * policy (backend/services/passwords.py): a minimum length, a zxcvbn score and
 * no passwords built from your name, email or the app's name. The server has
 * the final say, and also checks leaked passwords, which needs the network.
 */

export interface Strength {
  score: 0 | 1 | 2 | 3 | 4
  /** Why it's weak, and how to improve it ('' when fine). */
  feedback: string
  acceptable: boolean
}

// Words an attacker would try first against this app (same list as the server).
const APP_WORDS = ['bursa', 'saham', 'idx', 'bei', 'ihsg', 'invest', 'investor', 'stock']
const OWN_LETTERS = 6

// The dictionaries are big (~400 KB): loaded once, only when a password form opens.
let loader: Promise<ZxcvbnFactory> | null = null
function loadZxcvbn() {
  loader ??= Promise.all([
    import('@zxcvbn-ts/core'),
    import('@zxcvbn-ts/language-common'),
    import('@zxcvbn-ts/language-en'),
  ]).then(
    ([core, common, en]) =>
      new core.ZxcvbnFactory({
        translations: en.translations,
        graphs: common.adjacencyGraphs,
        dictionary: { ...common.dictionary, ...en.dictionary },
      }),
  )
  return loader
}

function userWords(inputs: string[]) {
  const words: string[] = [...APP_WORDS]
  for (const input of inputs) {
    const value = input.trim()
    if (!value) continue
    words.push(value, value.split('@')[0], ...value.split(/\s+/))
  }
  return words.filter(Boolean)
}

/** Mostly the name, email or app words plus digits, e.g. "budisantoso2024". */
function mostlyPersonal(password: string, words: string[]) {
  let rest = password.toLowerCase()
  let removed = false
  const unique = [
    ...new Set(words.map((w) => w.toLowerCase()).filter((w) => w.length >= 3)),
  ]
  for (const word of unique.sort((a, b) => b.length - a.length)) {
    if (rest.includes(word)) {
      rest = rest.split(word).join('')
      removed = true
    }
  }
  return removed && rest.replace(/[^a-z]/g, '').length < OWN_LETTERS
}

/** null until the checker has loaded (or while the field is empty). */
export function usePasswordStrength(
  password: string,
  inputs: string[] = [],
): Strength | null {
  const [zxcvbn, setZxcvbn] = useState<ZxcvbnFactory | null>(null)
  const { data: options } = useQuery({
    queryKey: ['auth', 'options'],
    queryFn: fetchAuthOptions,
  })
  const minLength = options?.password_min_length ?? 12
  const minScore = options?.password_min_score ?? 3

  useEffect(() => {
    let live = true
    loadZxcvbn()
      .then((z) => live && setZxcvbn(z))
      .catch(() => {}) // offline: the server still checks on submit
    return () => {
      live = false
    }
  }, [])

  if (!password || !zxcvbn) return null
  if (password.length < minLength) {
    return {
      score: 0,
      feedback: `Use at least ${minLength} characters (${password.length} so far).`,
      acceptable: false,
    }
  }
  const words = userWords(inputs)
  if (mostlyPersonal(password, words)) {
    return {
      score: 1,
      feedback: "It's mostly your name, email or the app's name. Add words of your own.",
      acceptable: false,
    }
  }
  const result = zxcvbn.check(password.slice(0, 100), words)
  const acceptable = result.score >= minScore
  const hints = [result.feedback.warning, ...result.feedback.suggestions].filter(Boolean)
  return {
    score: result.score,
    feedback: acceptable ? '' : hints.join(' ') || 'Add another word or two.',
    acceptable,
  }
}
