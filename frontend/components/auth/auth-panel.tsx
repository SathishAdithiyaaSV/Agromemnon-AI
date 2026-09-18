'use client'

import { ArrowLeft, Sprout } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Wordmark } from '@/components/brand'
import { LanguageSwitcher } from '@/components/language-switcher'
import { Button } from '@/components/ui/button'
import { Field, Input } from '@/components/ui/field'
import { useAuth } from '@/contexts/auth-context'
import { useLanguage } from '@/contexts/language-context'
import { AuthError } from '@/lib/cognito'

export type AuthMode = 'signIn' | 'signUp'
type Stage = AuthMode | 'confirm' | 'forgot' | 'reset'

/** Mirrors the pool's password policy so the failure is caught before the round trip. */
function passwordProblem(password: string): boolean {
  return password.length < 8 || !/[0-9]/.test(password) || !/[a-z]/.test(password)
}

function message(err: unknown, fallback: string): string {
  if (err instanceof AuthError) {
    // Cognito's own wording for these two is confusing out of context.
    if (err.code === 'UsernameExistsException') return 'That email already has an account. Sign in instead.'
    if (err.code === 'NotAuthorizedException') return 'Wrong email or password.'
    if (err.code === 'CodeMismatchException') return 'That code is not right. Check it and try again.'
    if (err.code === 'ExpiredCodeException') return 'That code has expired. Ask for a new one.'
    if (err.code === 'LimitExceededException') return 'Too many attempts. Wait a few minutes.'
    return err.message
  }
  return fallback
}

export function AuthPanel({ initialMode, onBack }: { initialMode: AuthMode; onBack: () => void }) {
  const { t } = useLanguage()
  const auth = useAuth()

  const [stage, setStage] = useState<Stage>(initialMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [code, setCode] = useState('')
  const [fieldError, setFieldError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setFieldError(null)
    try {
      await action()
    } catch (err) {
      toast.error(message(err, t('common.error')))
    } finally {
      setBusy(false)
    }
  }

  const submitSignIn = () =>
    run(async () => {
      try {
        await auth.signIn(email, password)
      } catch (err) {
        // Signing up and abandoning the email leaves the account unconfirmed;
        // send them back to the code step rather than a dead end.
        if (err instanceof AuthError && err.code === 'UserNotConfirmedException') {
          await auth.resendCode(email).catch(() => undefined)
          setStage('confirm')
          toast.info(t('auth.verify.resent'))
          return
        }
        throw err
      }
    })

  const submitSignUp = () =>
    run(async () => {
      if (passwordProblem(password)) {
        setFieldError(t('auth.passwordHint'))
        return
      }
      if (password !== confirmPassword) {
        setFieldError(t('auth.mismatch'))
        return
      }
      const { userConfirmed } = await auth.signUp(email, password)
      if (userConfirmed) {
        await auth.signIn(email, password)
        return
      }
      setStage('confirm')
    })

  const submitConfirm = () =>
    run(async () => {
      await auth.confirmSignUp(email, code)
      // The password is still in state from the previous step, so the farmer
      // goes straight into the app instead of typing it again.
      if (password) {
        await auth.signIn(email, password)
      } else {
        setStage('signIn')
      }
    })

  const submitForgot = () =>
    run(async () => {
      await auth.forgotPassword(email)
      setStage('reset')
    })

  const submitReset = () =>
    run(async () => {
      if (passwordProblem(password)) {
        setFieldError(t('auth.passwordHint'))
        return
      }
      await auth.confirmForgotPassword(email, code, password)
      toast.success(t('auth.reset.done'))
      setCode('')
      setPassword('')
      setStage('signIn')
    })

  const heading = {
    signIn: { title: t('auth.signIn.title'), subtitle: t('auth.signIn.subtitle') },
    signUp: { title: t('auth.signUp.title'), subtitle: t('auth.signUp.subtitle') },
    confirm: { title: t('auth.verify.title'), subtitle: t('auth.verify.subtitle', { email }) },
    forgot: { title: t('auth.reset.title'), subtitle: t('auth.reset.subtitle') },
    reset: { title: t('auth.reset.title'), subtitle: t('auth.verify.subtitle', { email }) },
  }[stage]

  const handlers: Record<Stage, () => Promise<void>> = {
    signIn: submitSignIn,
    signUp: submitSignUp,
    confirm: submitConfirm,
    forgot: submitForgot,
    reset: submitReset,
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-[0.85fr_1fr]">
      {/* Brand column — decorative, so it drops away on small screens. */}
      <aside className="relative hidden overflow-hidden border-r border-border bg-gradient-to-b from-primary/12 via-card to-accent/10 lg:block">
        <div className="furrows absolute inset-0 opacity-60" aria-hidden />
        <div className="relative flex h-full flex-col justify-between p-10">
          <Wordmark size="lg" />
          <div className="max-w-sm">
            <Sprout className="size-8 text-primary" strokeWidth={1.6} />
            <p className="mt-5 font-display text-2xl leading-snug tracking-tight">
              {t('landing.footer.tagline')}
            </p>
            <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
              {t('landing.hero.note')}
            </p>
          </div>
          <p className="text-xs text-muted-foreground">{t('landing.footer.disclaimer')}</p>
        </div>
      </aside>

      <main className="relative flex flex-col px-4 py-6 sm:px-8">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onBack}>
            <ArrowLeft />
            {t('auth.back')}
          </Button>
          <div className="ml-auto">
            <LanguageSwitcher />
          </div>
        </div>

        <div className="flex flex-1 items-center justify-center py-8">
          <div className="w-full max-w-sm">
            <div className="lg:hidden">
              <Wordmark size="md" />
            </div>

            <h1 className="mt-6 font-display text-3xl tracking-tight lg:mt-0">{heading.title}</h1>
            <p className="mt-2.5 text-[0.9375rem] leading-relaxed text-muted-foreground">
              {heading.subtitle}
            </p>

            {!auth.configured && (
              <p className="mt-5 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {t('auth.unconfigured')}
              </p>
            )}

            <form
              className="mt-7 space-y-4"
              onSubmit={(event) => {
                event.preventDefault()
                void handlers[stage]()
              }}
            >
              {(stage === 'signIn' || stage === 'signUp' || stage === 'forgot') && (
                <Field label={t('auth.email')}>
                  {(props) => (
                    <Input
                      {...props}
                      type="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                    />
                  )}
                </Field>
              )}

              {(stage === 'confirm' || stage === 'reset') && (
                <Field label={t('auth.verify.code')}>
                  {(props) => (
                    <Input
                      {...props}
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      required
                      maxLength={10}
                      value={code}
                      onChange={(event) => setCode(event.target.value)}
                      className="tracking-[0.3em]"
                    />
                  )}
                </Field>
              )}

              {(stage === 'signIn' || stage === 'signUp' || stage === 'reset') && (
                <Field
                  label={stage === 'reset' ? t('auth.reset.newPassword') : t('auth.password')}
                  hint={stage === 'signIn' ? undefined : t('auth.passwordHint')}
                  error={fieldError ?? undefined}
                >
                  {(props) => (
                    <Input
                      {...props}
                      type="password"
                      autoComplete={stage === 'signIn' ? 'current-password' : 'new-password'}
                      required
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                    />
                  )}
                </Field>
              )}

              {stage === 'signUp' && (
                <Field label={t('auth.confirmPassword')}>
                  {(props) => (
                    <Input
                      {...props}
                      type="password"
                      autoComplete="new-password"
                      required
                      value={confirmPassword}
                      onChange={(event) => setConfirmPassword(event.target.value)}
                    />
                  )}
                </Field>
              )}

              <Button type="submit" size="lg" block loading={busy} disabled={!auth.configured}>
                {
                  {
                    signIn: t('auth.signInButton'),
                    signUp: t('auth.signUpButton'),
                    confirm: t('auth.verify.button'),
                    forgot: t('auth.reset.send'),
                    reset: t('auth.reset.button'),
                  }[stage]
                }
              </Button>
            </form>

            <div className="mt-5 space-y-1 text-center text-sm">
              {stage === 'signIn' && (
                <>
                  <Button variant="link" size="sm" onClick={() => setStage('forgot')}>
                    {t('auth.forgot')}
                  </Button>
                  <p>
                    <Button variant="link" size="sm" onClick={() => setStage('signUp')}>
                      {t('auth.toSignUp')}
                    </Button>
                  </p>
                </>
              )}

              {stage === 'signUp' && (
                <Button variant="link" size="sm" onClick={() => setStage('signIn')}>
                  {t('auth.toSignIn')}
                </Button>
              )}

              {stage === 'confirm' && (
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => void run(async () => {
                    await auth.resendCode(email)
                    toast.info(t('auth.verify.resent'))
                  })}
                >
                  {t('auth.verify.resend')}
                </Button>
              )}

              {(stage === 'forgot' || stage === 'reset') && (
                <Button variant="link" size="sm" onClick={() => setStage('signIn')}>
                  {t('auth.toSignIn')}
                </Button>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
