'use client'

import { BadgeIndianRupee, Play, Sprout, Stethoscope, Tractor } from 'lucide-react'
import { useLanguage } from '@/contexts/language-context'
import type { TranslationKey } from '@/lib/i18n'

/**
 * Which specialists produced an answer, shown under it.
 *
 * Agents, not tools. A farmer has no use for "mandi_price returned 3 rows", but
 * "the market adviser and the crop adviser worked on this" tells them what kind
 * of judgement is behind the reply and how many ways it was checked — which is
 * the difference between a paragraph they have to take on trust and one they can
 * weigh. The list comes off the backend stream, so it records what actually ran.
 *
 * An id with no entry here is dropped rather than shown raw: a new specialist
 * added to the backend should be named properly or not at all, never surfaced to
 * a farmer as `soil_agent`.
 */
const SPECIALISTS: Record<string, { icon: typeof Sprout; label: TranslationKey; tone: string }> = {
  crop_agent: { icon: Sprout, label: 'agent.crop', tone: 'text-leaf' },
  operations_agent: { icon: Tractor, label: 'agent.operations', tone: 'text-soil' },
  advice_agent: { icon: BadgeIndianRupee, label: 'agent.advice', tone: 'text-scheme' },
  plant_doctor: { icon: Stethoscope, label: 'agent.doctor', tone: 'text-destructive' },
  video_tutor: { icon: Play, label: 'agent.video', tone: 'text-water' },
}

export function AgentCredits({ agents }: { agents: string[] }) {
  const { t } = useLanguage()

  const known = agents.filter((id) => id in SPECIALISTS)
  if (known.length === 0) return null

  return (
    <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-border pt-3">
      <span className="text-[0.6875rem] text-muted-foreground">{t('chat.answeredBy')}</span>
      {known.map((id) => {
        const specialist = SPECIALISTS[id]
        return (
          <span
            key={id}
            className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-[0.6875rem] font-medium text-muted-foreground"
          >
            <specialist.icon className={`size-3 ${specialist.tone}`} strokeWidth={2} />
            {t(specialist.label)}
          </span>
        )
      })}
    </div>
  )
}
