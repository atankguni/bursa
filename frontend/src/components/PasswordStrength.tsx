import type { Strength } from '../lib/passwordStrength'

/** Four-bar meter with what to improve, under a "new password" field. */
export default function PasswordStrength({ strength }: { strength: Strength | null }) {
  if (!strength) return <>A few random words work well, e.g. “kopi pagi di jogja”.</>

  const [filled, label, tone, bar] = strength.acceptable
    ? strength.score === 4
      ? [4, 'Very strong', 'text-bull', 'bg-bull']
      : [3, 'Strong', 'text-bull', 'bg-bull']
    : strength.score === 2
      ? [2, 'Almost there', 'text-amber-700 dark:text-amber-400', 'bg-amber-500']
      : [1, 'Too weak', 'text-bear', 'bg-bear']

  return (
    <span className="block space-y-1" aria-live="polite">
      <span className="flex items-center gap-2">
        <span className="flex flex-1 gap-1" aria-hidden="true">
          {[0, 1, 2, 3].map((i) => (
            <span
              key={i}
              className={`h-1 flex-1 rounded-full ${i < filled ? bar : 'bg-active'}`}
            />
          ))}
        </span>
        <span className={`font-medium ${tone}`}>{label}</span>
      </span>
      {strength.feedback && <span className="block">{strength.feedback}</span>}
    </span>
  )
}
