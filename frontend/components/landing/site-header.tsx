'use client'

import { useEffect, useState } from 'react'
import { Wordmark } from '@/components/brand'
import { LanguageSwitcher } from '@/components/language-switcher'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { useLanguage } from '@/contexts/language-context'
import { cn } from '@/lib/utils'

export function SiteHeader({
  onSignIn,
  onStart,
}: {
  onSignIn: () => void
  onStart: () => void
}) {
  const { t } = useLanguage()
  const [lifted, setLifted] = useState(false)

  // Borderless over the hero, bordered once the page moves — keeps the top of
  // the page open without losing the header against content.
  useEffect(() => {
    const onScroll = () => setLifted(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={cn(
        'sticky top-0 z-40 transition-colors duration-300',
        lifted
          ? 'border-b border-border bg-[color-mix(in_oklch,var(--background)_82%,transparent)] backdrop-blur-xl'
          : 'border-b border-transparent',
      )}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Wordmark />

        <nav className="ml-6 hidden items-center gap-1 lg:flex">
          <a
            href="#council"
            className="rounded-full px-3.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            {t('nav.features')}
          </a>
          <a
            href="#steps"
            className="rounded-full px-3.5 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            {t('nav.how')}
          </a>
        </nav>

        <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
          <div className="hidden sm:block">
            <LanguageSwitcher />
          </div>
          <div className="sm:hidden">
            <LanguageSwitcher compact />
          </div>
          <ThemeToggle />
          <Button variant="ghost" size="sm" className="hidden sm:inline-flex" onClick={onSignIn}>
            {t('nav.signIn')}
          </Button>
          <Button size="sm" onClick={onStart}>
            {t('nav.start')}
          </Button>
        </div>
      </div>
    </header>
  )
}
