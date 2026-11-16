/** /confirm-email/:token — the link sent to a new email address. Works signed out. */
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { checkEmailChange, confirmEmailChange, errorMessage } from '../../api'
import { ME_KEY } from '../../lib/auth'
import AuthLayout, { FormError, primaryBtn } from './AuthLayout'

export default function ConfirmEmail() {
  const { token = '' } = useParams()
  const qc = useQueryClient()
  // Look first, change on the button: mail scanners that open links don't change anything.
  const check = useQuery({
    queryKey: ['account', 'confirm-email', token],
    queryFn: () => checkEmailChange(token),
    retry: false,
  })
  const confirm = useMutation({
    mutationFn: () => confirmEmailChange(token),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ME_KEY }),
  })
  const home = (
    <Link to="/" className="hover:text-ink">
      Go to Bursa
    </Link>
  )

  if (check.isPending) return <AuthLayout title="Checking your link…">{null}</AuthLayout>
  if (confirm.isSuccess) {
    return (
      <AuthLayout title="Email changed" footer={home}>
        <p className="text-sm text-muted">
          Your account now uses <b className="text-ink">{confirm.data.new_email}</b>. Sign
          in with it from now on.
        </p>
      </AuthLayout>
    )
  }
  if (check.isError) {
    return (
      <AuthLayout title="Link not valid" footer={home}>
        <p className="text-sm text-muted">
          {errorMessage(
            check.error,
            'This link is invalid, was used already or has expired.',
          )}
        </p>
      </AuthLayout>
    )
  }
  return (
    <AuthLayout title="Confirm your new email" footer={home}>
      <p className="mb-4 text-sm text-muted">
        Use <b className="text-ink">{check.data.new_email}</b> for your Bursa account?
      </p>
      <button
        onClick={() => confirm.mutate()}
        disabled={confirm.isPending}
        className={primaryBtn}
      >
        {confirm.isPending ? 'Confirming…' : 'Use this email'}
      </button>
      <FormError>
        {confirm.isError ? errorMessage(confirm.error, 'Could not confirm') : null}
      </FormError>
    </AuthLayout>
  )
}
