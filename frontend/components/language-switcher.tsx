'use client'

import { Check, Languages } from 'lucide-react'
import { useAuth } from '@/contexts/auth-context'
import { useLanguage } from '@/contexts/language-context'
import { LANGUAGES } from '@/lib/i18n'
import type { LanguageCode } from '@/lib/cognito'
import { Button } from '@/components/ui/button'
import {
  Dropdown,
  DropdownContent,
  DropdownItem,
  DropdownLabel,
  DropdownTrigger,
} from '@/components/ui/dropdown'

export function LanguageSwitcher({
  compact = false,
  align = 'end',
}: {
  compact?: boolean
  align?: 'start' | 'end'
}) {
  const { language, setLanguage, t } = useLanguage()
  // Also present on the public landing page, where nobody is signed in yet.
  const { status, updateProfile } = useAuth()
  const current = LANGUAGES.find((entry) => entry.code === language)

  const choose = (code: LanguageCode) => {
    setLanguage(code)
    // Remember it on the account too, so a new device opens in the same
    // language. Failure here is not worth interrupting anyone over.
    if (status === 'signedIn') void updateProfile({ language: code }).catch(() => undefined)
  }

  return (
    <Dropdown>
      <DropdownTrigger asChild>
        <Button variant="outline" size={compact ? 'icon' : 'sm'} aria-label={t('common.language')}>
          <Languages />
          {!compact && <span>{current?.label ?? 'Language'}</span>}
        </Button>
      </DropdownTrigger>
      <DropdownContent align={align}>
        <DropdownLabel>{t('common.language')}</DropdownLabel>
        {LANGUAGES.map((entry) => (
          <DropdownItem key={entry.code} onSelect={() => choose(entry.code)}>
            <span className="flex-1">{entry.label}</span>
            <span className="text-xs text-muted-foreground">{entry.english}</span>
            {entry.code === language && <Check className="size-4 text-primary" />}
          </DropdownItem>
        ))}
      </DropdownContent>
    </Dropdown>
  )
}
