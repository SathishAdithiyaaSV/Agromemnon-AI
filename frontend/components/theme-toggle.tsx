'use client'

import { Monitor, Moon, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'
import { useLanguage } from '@/contexts/language-context'
import { Button } from '@/components/ui/button'
import {
  Dropdown,
  DropdownContent,
  DropdownItem,
  DropdownLabel,
  DropdownTrigger,
} from '@/components/ui/dropdown'

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const { t } = useLanguage()
  const [mounted, setMounted] = useState(false)

  // The active theme is unknown until hydration, so render a stable placeholder
  // rather than guessing an icon the server cannot know.
  useEffect(() => setMounted(true), [])

  const options = [
    { value: 'light', label: t('common.light'), icon: Sun },
    { value: 'dark', label: t('common.dark'), icon: Moon },
    { value: 'system', label: t('common.system'), icon: Monitor },
  ] as const

  const Active = mounted ? (options.find((o) => o.value === theme)?.icon ?? Monitor) : Monitor

  return (
    <Dropdown>
      <DropdownTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={t('common.theme')}>
          <Active />
        </Button>
      </DropdownTrigger>
      <DropdownContent align="end">
        <DropdownLabel>{t('common.theme')}</DropdownLabel>
        {options.map(({ value, label, icon: Icon }) => (
          <DropdownItem key={value} onSelect={() => setTheme(value)}>
            <Icon className="size-4" />
            <span className="flex-1">{label}</span>
          </DropdownItem>
        ))}
      </DropdownContent>
    </Dropdown>
  )
}
