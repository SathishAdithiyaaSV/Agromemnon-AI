'use client'

import { useEffect, useState } from 'react'
import { Logo } from '@/components/brand'
import { useLanguage } from '@/contexts/language-context'
import type { TranslationKey } from '@/lib/i18n'

/**
 * What the system is doing while a turn runs.
 *
 * The phases are on a timer, not on live progress, and that is a limitation of
 * the transport rather than a choice: /chat is a synchronous request behind API
 * Gateway (see lib/api.ts), so the browser gets one response at the end and
 * nothing in between. Naming a specific specialist here would therefore be a
 * guess dressed up as a status line. The phases instead describe the stages the
 * orchestrator really goes through, in the order it goes through them, and the
 * specialists that actually ran are named honestly once the answer lands — see
 * AgentCredits.
 *
 * The thresholds come from the shape of a real turn: routing is decided in the
 * first couple of seconds, the specialists and their lookups take the bulk of
 * the time, and the orchestrator writes its merged reply at the end. A turn runs
 * roughly 10–25s and API Gateway cuts it off at 30, so the last phase also
 * covers the wait turning long.
 */
const PHASES: ReadonlyArray<{ after: number; label: TranslationKey }> = [
  { after: 0, label: 'chat.phase.routing' },
  { after: 2_500, label: 'chat.thinking' },
  { after: 8_000, label: 'chat.phase.data' },
  { after: 15_000, label: 'chat.phase.writing' },
  { after: 24_000, label: 'chat.thinkingLong' },
]

export function Thinking() {
  const { t } = useLanguage()
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const startedAt = Date.now()
    const timer = setInterval(() => setElapsed(Date.now() - startedAt), 250)
    return () => clearInterval(timer)
  }, [])

  const seconds = Math.floor(elapsed / 1000)
  // The last phase whose threshold has passed. PHASES[0] starts at 0, so there
  // is always one. A plain scan rather than findLast, which needs a browser from
  // 2022 onward — not a safe assumption for the phones this is built for.
  let phase = PHASES[0]
  for (const candidate of PHASES) {
    if (elapsed >= candidate.after) phase = candidate
  }

  return (
    <div className="flex gap-3" aria-live="polite">
      <Logo className="mt-0.5 size-8 shrink-0" />
      <div className="flex min-h-8 items-center gap-3 rounded-2xl rounded-tl-md border border-border bg-card px-4 py-2.5">
        <span className="flex gap-1" aria-hidden>
          {[0, 1, 2].map((index) => (
            <span
              key={index}
              className="size-1.5 rounded-full bg-primary/70"
              style={{
                animation: 'sprout 1s ease-in-out infinite alternate',
                animationDelay: `${index * 0.18}s`,
              }}
            />
          ))}
        </span>
        {/* Keyed on the phase so each new label fades in rather than swapping
            mid-word, which at this size reads as a glitch. */}
        <span key={phase.label} className="animate-fade text-sm text-muted-foreground">
          {t(phase.label)}
        </span>
        <span className="text-xs tabular-nums text-muted-foreground/70">{seconds}s</span>
      </div>
    </div>
  )
}
