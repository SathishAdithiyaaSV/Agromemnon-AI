'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { LanguageCode } from '@/lib/cognito'
import {
  DEFAULT_LANGUAGE,
  dictionaries,
  isLanguageCode,
  localeFor,
  type TranslationKey,
} from '@/lib/i18n'

const STORAGE_KEY = 'agromemnon.language'

interface LanguageContextValue {
  language: LanguageCode
  locale: string
  setLanguage: (code: LanguageCode) => void
  /** `t('onboarding.step', { n: 1 })` fills `{n}` placeholders. */
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<LanguageCode>(DEFAULT_LANGUAGE)

  // Read after mount, not during render: the server has no localStorage, and
  // reading it in an initialiser would make the first client render disagree
  // with the server's HTML.
  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (isLanguageCode(stored)) setLanguageState(stored)
  }, [])

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  const setLanguage = useCallback((code: LanguageCode) => {
    setLanguageState(code)
    window.localStorage.setItem(STORAGE_KEY, code)
  }, [])

  const t = useCallback(
    (key: TranslationKey, vars?: Record<string, string | number>) => {
      const dict = dictionaries[language] ?? dictionaries[DEFAULT_LANGUAGE]
      const template = dict[key] ?? dictionaries[DEFAULT_LANGUAGE][key] ?? key
      if (!vars) return template
      return Object.entries(vars).reduce(
        (text, [name, value]) => text.replaceAll(`{${name}}`, String(value)),
        template,
      )
    },
    [language],
  )

  const value = useMemo(
    () => ({ language, locale: localeFor(language), setLanguage, t }),
    [language, setLanguage, t],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage(): LanguageContextValue {
  const context = useContext(LanguageContext)
  if (!context) throw new Error('useLanguage must be used inside <LanguageProvider>')
  return context
}
