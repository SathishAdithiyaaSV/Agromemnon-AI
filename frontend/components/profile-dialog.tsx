'use client'

import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
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

export function ProfileDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t, language, setLanguage } = useLanguage()
  const { profile, updateProfile } = useAuth()

  const [name, setName] = useState('')
  const [age, setAge] = useState('')
  const [state, setState] = useState('')
  const [district, setDistrict] = useState('')
  const [busy, setBusy] = useState(false)

  // Refill from the profile each time it opens, so a cancelled edit is discarded.
  useEffect(() => {
    if (!open || !profile) return
    setName(profile.name ?? '')
    setAge(profile.age ? String(profile.age) : '')
    setState(profile.state ?? '')
    setDistrict(profile.district ?? '')
  }, [open, profile])

  const districts = useMemo(() => districtsOf(state), [state])

  const save = async () => {
    setBusy(true)
    try {
      await updateProfile({
        name: name.trim(),
        ...(age ? { age: Number(age) } : {}),
        state,
        district,
        language,
      })
      toast.success(t('profile.saved'))
      onOpenChange(false)
    } catch {
      toast.error(t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent closeLabel={t('common.close')}>
        <div className="border-b border-border px-6 py-5">
          <DialogTitle className="font-display text-xl tracking-tight">
            {t('profile.title')}
          </DialogTitle>
          <DialogDescription className="mt-1.5 text-sm text-muted-foreground">
            {t('profile.subtitle')}
          </DialogDescription>
        </div>

        <form
          className="max-h-[min(70vh,34rem)] space-y-5 overflow-y-auto px-6 py-6"
          onSubmit={(event) => {
            event.preventDefault()
            void save()
          }}
        >
          <Field label={t('profile.email')} hint={t('profile.emailFixed')}>
            {(props) => <Input {...props} value={profile?.email ?? ''} readOnly disabled />}
          </Field>

          <Field label={t('onboarding.name')}>
            {(props) => (
              <Input {...props} value={name} onChange={(event) => setName(event.target.value)} />
            )}
          </Field>

          <Field label={t('onboarding.age')}>
            {(props) => (
              <Input
                {...props}
                type="number"
                min={16}
                max={120}
                value={age}
                onChange={(event) => setAge(event.target.value)}
              />
            )}
          </Field>

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

          <Field label={t('onboarding.district')}>
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

          <Field label={t('onboarding.language')}>
            {(props) => (
              <Select value={language} onValueChange={(value) => setLanguage(value as LanguageCode)}>
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

          <div className="flex gap-3 pt-1">
            <Button type="button" variant="outline" block onClick={() => onOpenChange(false)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" block loading={busy}>
              {busy ? t('common.saving') : t('profile.save')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
