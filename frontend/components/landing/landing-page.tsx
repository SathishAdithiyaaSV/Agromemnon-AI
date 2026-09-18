'use client'

import {
  ArrowRight,
  BadgeIndianRupee,
  Droplets,
  Languages,
  Mic,
  MessagesSquare,
  ScrollText,
  Sprout,
  TableProperties,
} from 'lucide-react'
import { Wordmark } from '@/components/brand'
import { Reveal } from '@/components/reveal'
import { Button } from '@/components/ui/button'
import { useLanguage } from '@/contexts/language-context'
import type { TranslationKey } from '@/lib/i18n'
import { HeroPreview } from './hero-preview'
import { SiteHeader } from './site-header'

const COUNCIL = [
  {
    icon: Sprout,
    tone: 'text-leaf',
    ring: 'from-leaf/18',
    title: 'landing.council.crops.title',
    desc: 'landing.council.crops.desc',
    tag: 'landing.council.crops.tag',
  },
  {
    icon: Droplets,
    tone: 'text-water',
    ring: 'from-water/18',
    title: 'landing.council.water.title',
    desc: 'landing.council.water.desc',
    tag: 'landing.council.water.tag',
  },
  {
    icon: ScrollText,
    tone: 'text-scheme',
    ring: 'from-scheme/18',
    title: 'landing.council.schemes.title',
    desc: 'landing.council.schemes.desc',
    tag: 'landing.council.schemes.tag',
  },
  {
    icon: BadgeIndianRupee,
    tone: 'text-soil',
    ring: 'from-soil/18',
    title: 'landing.council.market.title',
    desc: 'landing.council.market.desc',
    tag: 'landing.council.market.tag',
  },
] satisfies ReadonlyArray<{
  icon: typeof Sprout
  tone: string
  ring: string
  title: TranslationKey
  desc: TranslationKey
  tag: TranslationKey
}>

const FEATURES = [
  { icon: Mic, title: 'landing.features.voice.title', desc: 'landing.features.voice.desc' },
  { icon: Languages, title: 'landing.features.lang.title', desc: 'landing.features.lang.desc' },
  {
    icon: MessagesSquare,
    title: 'landing.features.memory.title',
    desc: 'landing.features.memory.desc',
  },
  {
    icon: TableProperties,
    title: 'landing.features.grounded.title',
    desc: 'landing.features.grounded.desc',
  },
] satisfies ReadonlyArray<{ icon: typeof Mic; title: TranslationKey; desc: TranslationKey }>

const STEPS = [
  { title: 'landing.how.step1.title', desc: 'landing.how.step1.desc' },
  { title: 'landing.how.step2.title', desc: 'landing.how.step2.desc' },
  { title: 'landing.how.step3.title', desc: 'landing.how.step3.desc' },
] satisfies ReadonlyArray<{ title: TranslationKey; desc: TranslationKey }>

export function LandingPage({
  onSignIn,
  onStart,
}: {
  onSignIn: () => void
  onStart: () => void
}) {
  const { t } = useLanguage()

  return (
    <div className="min-h-dvh bg-background">
      <SiteHeader onSignIn={onSignIn} onStart={onStart} />

      {/* ---------------------------------------------------------------- hero */}
      <section className="relative overflow-hidden">
        <div
          className="furrows pointer-events-none absolute inset-0 opacity-70 [mask-image:radial-gradient(120%_80%_at_50%_0%,black,transparent_72%)]"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -right-40 -top-32 size-[34rem] rounded-full bg-gradient-to-br from-accent/20 to-transparent blur-3xl"
          aria-hidden
        />

        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 pb-16 pt-14 sm:px-6 sm:pb-24 sm:pt-20 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
          <div>
            <Reveal>
              <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-3.5 py-1.5 text-xs font-medium text-muted-foreground backdrop-blur">
                <span className="size-1.5 rounded-full bg-accent" />
                {t('landing.hero.eyebrow')}
              </span>
            </Reveal>

            <Reveal delay={0.05}>
              <h1 className="mt-6 font-display text-4xl leading-[1.05] tracking-tight text-balance sm:text-5xl lg:text-6xl">
                {t('landing.hero.title')}
                <br />
                <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                  {t('landing.hero.titleAccent')}
                </span>
              </h1>
            </Reveal>

            <Reveal delay={0.1}>
              <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
                {t('landing.hero.subtitle')}
              </p>
            </Reveal>

            <Reveal delay={0.15}>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
                <Button size="lg" onClick={onStart}>
                  {t('landing.hero.cta')}
                  <ArrowRight />
                </Button>
                <Button size="lg" variant="outline" asChild>
                  <a href="#council">{t('landing.hero.secondary')}</a>
                </Button>
              </div>
              <p className="mt-4 text-sm text-muted-foreground">{t('landing.hero.note')}</p>
            </Reveal>
          </div>

          <div className="flex justify-center lg:justify-end">
            <HeroPreview />
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- council */}
      <section id="council" className="scroll-mt-20 border-t border-border bg-card/40">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
          <Reveal className="max-w-2xl">
            <h2 className="font-display text-3xl tracking-tight text-balance sm:text-4xl">
              {t('landing.council.title')}
            </h2>
            <p className="mt-4 text-lg leading-relaxed text-muted-foreground">
              {t('landing.council.subtitle')}
            </p>
          </Reveal>

          <ul className="mt-12 grid gap-5 sm:grid-cols-2">
            {COUNCIL.map((item, index) => (
              <Reveal as="li" key={item.title} delay={index * 0.06}>
                <article className="group relative h-full overflow-hidden rounded-2xl border border-border bg-card p-6 transition-shadow duration-300 hover:shadow-[0_20px_40px_-28px_color-mix(in_oklch,var(--foreground)_40%,transparent)]">
                  <div
                    className={`pointer-events-none absolute -right-16 -top-16 size-40 rounded-full bg-gradient-to-br ${item.ring} to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100`}
                    aria-hidden
                  />
                  <item.icon className={`size-7 ${item.tone}`} strokeWidth={1.6} />
                  <h3 className="mt-5 font-display text-xl tracking-tight">{t(item.title)}</h3>
                  <p className="mt-3 text-[0.9375rem] leading-relaxed text-muted-foreground">
                    {t(item.desc)}
                  </p>
                  <p className="mt-5 inline-flex rounded-full bg-muted px-3 py-1.5 text-[0.6875rem] font-medium uppercase tracking-[0.06em] text-muted-foreground">
                    {t(item.tag)}
                  </p>
                </article>
              </Reveal>
            ))}
          </ul>
        </div>
      </section>

      {/* ------------------------------------------------------------ features */}
      <section className="border-t border-border">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
          <Reveal>
            <h2 className="font-display text-3xl tracking-tight sm:text-4xl">
              {t('landing.features.title')}
            </h2>
          </Reveal>

          <dl className="mt-12 grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((feature, index) => (
              <Reveal key={feature.title} delay={index * 0.05}>
                <div className="border-t-2 border-primary/25 pt-5">
                  <feature.icon className="size-5 text-primary" strokeWidth={1.8} />
                  <dt className="mt-4 font-display text-lg tracking-tight">{t(feature.title)}</dt>
                  <dd className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
                    {t(feature.desc)}
                  </dd>
                </div>
              </Reveal>
            ))}
          </dl>
        </div>
      </section>

      {/* --------------------------------------------------------------- steps */}
      <section id="steps" className="scroll-mt-20 border-t border-border bg-card/40">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
          <Reveal>
            <h2 className="font-display text-3xl tracking-tight sm:text-4xl">
              {t('landing.how.title')}
            </h2>
          </Reveal>

          <ol className="mt-12 grid gap-8 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <Reveal as="li" key={step.title} delay={index * 0.07} className="relative">
                <span className="font-display text-5xl leading-none text-primary/25">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <h3 className="mt-4 font-display text-xl tracking-tight">{t(step.title)}</h3>
                <p className="mt-3 text-[0.9375rem] leading-relaxed text-muted-foreground">
                  {t(step.desc)}
                </p>
              </Reveal>
            ))}
          </ol>
        </div>
      </section>

      {/* ----------------------------------------------------------------- cta */}
      <section className="border-t border-border">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
          <Reveal>
            <div className="furrows-diag relative overflow-hidden rounded-3xl border border-border bg-gradient-to-br from-primary/12 via-card to-accent/12 px-6 py-14 text-center sm:px-14">
              <h2 className="mx-auto max-w-2xl font-display text-3xl tracking-tight text-balance sm:text-4xl">
                {t('landing.cta.title')}
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-lg text-muted-foreground">
                {t('landing.cta.subtitle')}
              </p>
              <Button size="lg" className="mt-8" onClick={onStart}>
                {t('landing.cta.button')}
                <ArrowRight />
              </Button>
            </div>
          </Reveal>
        </div>
      </section>

      {/* -------------------------------------------------------------- footer */}
      <footer className="border-t border-border bg-card/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-12 sm:px-6 md:flex-row md:items-start md:justify-between">
          <div className="max-w-sm">
            <Wordmark />
            <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
              {t('landing.footer.tagline')}
            </p>
          </div>
          <div className="space-y-2 text-sm text-muted-foreground md:text-right">
            <p className="font-medium text-foreground">{t('landing.footer.built')}</p>
            <p className="max-w-xs md:ml-auto">{t('landing.footer.disclaimer')}</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
