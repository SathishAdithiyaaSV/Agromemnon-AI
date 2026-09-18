'use client'

import { useEffect, useState } from 'react'
import { Logo } from '@/components/brand'
import { useLanguage } from '@/contexts/language-context'

/**
 * A turn takes roughly 10–25 seconds — several tool calls behind one synchronous
 * request — and API Gateway cuts it off at 30. A counter is shown rather than a
 * bare spinner so the wait feels accounted for, and the wording changes once it
 * passes the point where a quick answer was likely.
 */
const LONG_WAIT_MS = 14_000

export function Thinking() {
  const { t } = useLanguage()
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const startedAt = Date.now()
    const timer = setInterval(() => setElapsed(Date.now() - startedAt), 250)
    return () => clearInterval(timer)
  }, [])

  const seconds = Math.floor(elapsed / 1000)
  const label = elapsed > LONG_WAIT_MS ? t('chat.thinkingLong') : t('chat.thinking')

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
        <span className="text-sm text-muted-foreground">{label}</span>
        <span className="text-xs tabular-nums text-muted-foreground/70">{seconds}s</span>
      </div>
    </div>
  )
}
