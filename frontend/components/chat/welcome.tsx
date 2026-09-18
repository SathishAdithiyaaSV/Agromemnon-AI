'use client'

import { BadgeIndianRupee, Droplets, Mic, ScrollText, Sprout } from 'lucide-react'
import { useChat } from '@/contexts/chat-context'
import { useAuth } from '@/contexts/auth-context'
import { useLanguage } from '@/contexts/language-context'
import type { TranslationKey } from '@/lib/i18n'

const SUGGESTIONS = [
  { icon: Sprout, tone: 'text-leaf', text: 'suggest.1', tag: 'suggest.1.tag' },
  { icon: BadgeIndianRupee, tone: 'text-soil', text: 'suggest.2', tag: 'suggest.2.tag' },
  { icon: Droplets, tone: 'text-water', text: 'suggest.3', tag: 'suggest.3.tag' },
  { icon: ScrollText, tone: 'text-scheme', text: 'suggest.4', tag: 'suggest.4.tag' },
] satisfies ReadonlyArray<{
  icon: typeof Sprout
  tone: string
  text: TranslationKey
  tag: TranslationKey
}>

export function Welcome() {
  const { t } = useLanguage()
  const { send, isSending } = useChat()
  const { profile } = useAuth()

  const firstName = profile?.name?.trim().split(/\s+/)[0]

  return (
    /* `my-auto` rather than `justify-center` on the scroll parent: a centred
       flex child taller than its container clips its own top, which put the
       greeting out of reach on short screens. */
    <div className="mx-auto my-auto w-full max-w-3xl px-4 py-10">
      <div className="animate-rise">
        <p className="text-sm font-medium text-primary">
          {firstName ? `${t('brand.role')} · ${firstName}` : t('brand.role')}
        </p>
        <h1 className="mt-3 font-display text-3xl leading-tight tracking-tight text-balance sm:text-4xl">
          {t('chat.welcome.title')}
        </h1>
        <p className="mt-3 text-[1.0625rem] leading-relaxed text-muted-foreground">
          {t('chat.welcome.subtitle')}
        </p>
      </div>

      <div className="mt-9">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          {t('chat.welcome.examples')}
        </p>

        <ul className="mt-4 grid gap-2.5 sm:grid-cols-2">
          {SUGGESTIONS.map((item, index) => (
            <li
              key={item.text}
              className="animate-rise"
              style={{ animationDelay: `${80 + index * 60}ms` }}
            >
              <button
                type="button"
                disabled={isSending}
                onClick={() => void send(t(item.text))}
                className="group flex h-full w-full items-start gap-3 rounded-2xl border border-border bg-card p-4 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-[color-mix(in_oklch,var(--primary)_35%,var(--border))] hover:shadow-[0_14px_30px_-22px_color-mix(in_oklch,var(--foreground)_50%,transparent)] disabled:pointer-events-none disabled:opacity-60"
              >
                <item.icon className={`mt-0.5 size-5 shrink-0 ${item.tone}`} strokeWidth={1.7} />
                <span className="min-w-0">
                  <span className="block text-[0.9375rem] font-medium leading-snug">
                    {t(item.text)}
                  </span>
                  <span className="mt-1 block text-xs text-muted-foreground">{t(item.tag)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>

        <p className="mt-6 flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <Mic className="size-3.5" />
          {t('chat.mic')}
        </p>
      </div>
    </div>
  )
}
