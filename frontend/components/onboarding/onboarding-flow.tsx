'use client'

import { ArrowLeft, ArrowRight, Check, MapPin, UserRound } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Wordmark } from '@/components/brand'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { Field, Input } from '@/components/ui/field'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAuth } from '@/contexts/auth-context'
import { useLanguage } from '@/contexts/language-context'
import type { LanguageCode } from '@/lib/cognito'
import { LANGUAGES } from '@/lib/i18n'
import { districtsOf, STATES } from '@/lib/states'

export function OnboardingFlow() {
  const { t, language, setLanguage } = useLanguage()
  const { profile, updateProfile, signOut } = useAuth()

  const [step, setStep] = useState<1 | 2>(1)
  const [name, setName] = useState(profile?.name ?? '')
  const [age, setAge] = useState(profile?.age ? String(profile.age) : '')
  const [state, setState] = useState(profile?.state ?? '')
  const [district, setDistrict] = useState(profile?.district ?? '')
  const [ageError, setAgeError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const districts = useMemo(() => districtsOf(state), [state])

  const stepOneReady = name.trim().length > 1 && age.trim().length > 0
  const stepTwoReady = Boolean(state && district)

  const goForward = async () => {
    if (step === 1) {
      const parsed = Number(age)
      if (!Number.isInteger(parsed) || parsed < 16 || parsed > 120) {
        setAgeError(t('onboarding.ageInvalid'))
        return
      }
      setAgeError(null)
      setStep(2)
      return
    }

    setBusy(true)
    try {
      await updateProfile({
        name: name.trim(),
        age: Number(age),
        state,
        district,
        language,
        isOnboarded: true,
      })
    } catch {
      toast.error(t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative min-h-dvh overflow-hidden">
      <div className="furrows pointer-events-none absolute inset-0 opacity-60" aria-hidden />

      <div className="relative mx-auto flex min-h-dvh max-w-xl flex-col px-4 py-6 sm:px-6">
        <div className="flex items-center">
          <Wordmark />
          <div className="ml-auto flex items-center gap-1.5">
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={signOut}>
              {t('profile.signOut')}
            </Button>
          </div>
        </div>

        <div className="flex flex-1 items-center">
          <div className="w-full rounded-3xl border border-border bg-card p-6 shadow-[0_24px_60px_-40px_color-mix(in_oklch,var(--foreground)_45%,transparent)] sm:p-8">
            <div className="flex items-center gap-3">
              <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-[color-mix(in_oklch,var(--primary)_12%,transparent)] text-primary">
                {step === 1 ? <UserRound strokeWidth={1.7} /> : <MapPin strokeWidth={1.7} />}
              </span>
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.08em] text-muted-foreground">
                  {t('onboarding.step', { n: step })}
                </p>
                <h1 className="font-display text-2xl tracking-tight">
                  {step === 1 ? t('onboarding.you') : t('onboarding.where')}
                </h1>
              </div>
            </div>

            {/* Two-segment progress bar rather than a percentage — with only two
                steps, a filling bar reads as more precise than it is. */}
            <div className="mt-6 flex gap-1.5" aria-hidden>
              {[1, 2].map((index) => (
                <span
                  key={index}
                  className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
                    index <= step ? 'bg-primary' : 'bg-muted'
                  }`}
                />
              ))}
            </div>

            <p className="mt-5 text-[0.9375rem] leading-relaxed text-muted-foreground">
              {t('onboarding.subtitle')}
            </p>

            <form
              className="mt-7 space-y-5"
              onSubmit={(event) => {
                event.preventDefault()
                void goForward()
              }}
            >
              {step === 1 ? (
                <>
                  <Field label={t('onboarding.name')}>
                    {(props) => (
                      <Input
                        {...props}
                        autoComplete="name"
                        required
                        value={name}
                        placeholder={t('onboarding.namePlaceholder')}
                        onChange={(event) => setName(event.target.value)}
                      />
                    )}
                  </Field>

                  <Field label={t('onboarding.age')} error={ageError ?? undefined}>
                    {(props) => (
                      <Input
                        {...props}
                        type="number"
                        inputMode="numeric"
                        min={16}
                        max={120}
                        required
                        value={age}
                        placeholder={t('onboarding.agePlaceholder')}
                        onChange={(event) => setAge(event.target.value)}
                      />
                    )}
                  </Field>

                  <Field label={t('onboarding.language')}>
                    {(props) => (
                      <Select
                        value={language}
                        onValueChange={(value) => setLanguage(value as LanguageCode)}
                      >
                        <SelectTrigger id={props.id}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {LANGUAGES.map((entry) => (
                            <SelectItem key={entry.code} value={entry.code}>
                              {entry.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </Field>
                </>
              ) : (
                <>
                  <Field label={t('onboarding.state')}>
                    {(props) => (
                      <Select
                        value={state}
                        onValueChange={(value) => {
                          setState(value)
                          setDistrict('')
                        }}
                      >
                        <SelectTrigger id={props.id}>
                          <SelectValue placeholder={t('onboarding.statePlaceholder')} />
                        </SelectTrigger>
                        <SelectContent>
                          {STATES.map((entry) => (
                            <SelectItem key={entry.state} value={entry.state}>
                              {entry.state}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </Field>

                  <Field label={t('onboarding.district')} hint={t('onboarding.privacy')}>
                    {(props) => (
                      <Select value={district} onValueChange={setDistrict} disabled={!state}>
                        <SelectTrigger id={props.id}>
                          <SelectValue placeholder={t('onboarding.districtPlaceholder')} />
                        </SelectTrigger>
                        <SelectContent>
                          {districts.map((entry) => (
                            <SelectItem key={entry} value={entry}>
                              {entry}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </Field>
                </>
              )}

              <div className="flex gap-3 pt-1">
                {step === 2 && (
                  <Button type="button" variant="outline" size="lg" onClick={() => setStep(1)}>
                    <ArrowLeft />
                  </Button>
                )}
                <Button
                  type="submit"
                  size="lg"
                  block
                  loading={busy}
                  disabled={step === 1 ? !stepOneReady : !stepTwoReady}
                >
                  {step === 1 ? (
                    <>
                      {t('onboarding.next')}
                      <ArrowRight />
                    </>
                  ) : (
                    <>
                      <Check />
                      {t('onboarding.finish')}
                    </>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
