import { en, type TranslationKey } from './en'
import { hi } from './hi'
import { kn } from './kn'
import { mr } from './mr'
import { ta } from './ta'
import type { LanguageCode } from '../cognito'

export type { TranslationKey }

export const dictionaries: Record<LanguageCode, Record<TranslationKey, string>> = {
  en,
  hi,
  kn,
  mr,
  ta,
}

export interface LanguageMeta {
  code: LanguageCode
  /** Endonym — shown in the switcher, because that is what a speaker recognises. */
  label: string
  english: string
  /** BCP-47 tag for SpeechRecognition and SpeechSynthesis. */
  locale: string
}

export const LANGUAGES: LanguageMeta[] = [
  { code: 'en', label: 'English', english: 'English', locale: 'en-IN' },
  { code: 'hi', label: 'हिंदी', english: 'Hindi', locale: 'hi-IN' },
  { code: 'kn', label: 'ಕನ್ನಡ', english: 'Kannada', locale: 'kn-IN' },
  { code: 'mr', label: 'मराठी', english: 'Marathi', locale: 'mr-IN' },
  { code: 'ta', label: 'தமிழ்', english: 'Tamil', locale: 'ta-IN' },
]

export const DEFAULT_LANGUAGE: LanguageCode = 'en'

export function isLanguageCode(value: unknown): value is LanguageCode {
  return typeof value === 'string' && value in dictionaries
}

export function localeFor(code: LanguageCode): string {
  return LANGUAGES.find((l) => l.code === code)?.locale ?? 'en-IN'
}
