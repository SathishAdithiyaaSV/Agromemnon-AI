'use client'

import { Menu, MessageSquarePlus } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Wordmark } from '@/components/brand'
import { LanguageSwitcher } from '@/components/language-switcher'
import { ProfileDialog } from '@/components/profile-dialog'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { Dialog, DialogTitle, DrawerContent } from '@/components/ui/dialog'
import { useChat } from '@/contexts/chat-context'
import { useLanguage } from '@/contexts/language-context'
import { useSpeechSynthesis } from '@/hooks/use-speech-synthesis'
import type { ChatMessage } from '@/lib/conversations'
import { localeFor } from '@/lib/i18n'
import { Composer } from './composer'
import { HistorySidebar } from './history-sidebar'
import { MessageBubble } from './message-bubble'
import { Thinking } from './thinking'
import { Welcome } from './welcome'

export function ChatShell() {
  const { t, locale } = useLanguage()
  const { active, isSending, startNew, retryLast } = useChat()
  const speech = useSpeechSynthesis()

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const bottom = useRef<HTMLDivElement>(null)

  const messages = active?.messages ?? []
  const lastMessage = messages[messages.length - 1]
  const canRetry = !isSending && lastMessage?.role === 'adviser' && Boolean(lastMessage.error)

  // Follow the conversation as it grows, and when switching between them. Skipped
  // while the welcome screen is up: there is nothing to follow, and scrolling to
  // the bottom anchor pushed the greeting off the top of a short screen.
  useEffect(() => {
    if (messages.length === 0) return
    bottom.current?.scrollIntoView({ behavior: messages.length > 2 ? 'smooth' : 'auto' })
  }, [messages.length, isSending, active?.id])

  // A reply still being read aloud has no business continuing after the user
  // moves to another conversation.
  useEffect(() => {
    speech.stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.id])

  const speak = (message: ChatMessage) => {
    speech.speak(
      message.id,
      message.text,
      message.language ? localeFor(message.language) : locale,
    )
  }

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      {/* Persistent rail on wide screens; the same component goes in the drawer. */}
      <aside className="hidden w-[17rem] shrink-0 border-r border-border lg:block">
        <HistorySidebar onOpenProfile={() => setProfileOpen(true)} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-[color-mix(in_oklch,var(--background)_88%,transparent)] px-2.5 backdrop-blur-xl sm:px-4">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setDrawerOpen(true)}
            aria-label={t('chat.menu')}
          >
            <Menu />
          </Button>

          <div className="lg:hidden">
            <Wordmark size="sm" />
          </div>

          <p className="hidden min-w-0 truncate font-display text-[0.9375rem] tracking-tight lg:block">
            {active?.title ?? t('chat.title')}
          </p>

          <div className="ml-auto flex items-center gap-1.5">
            <Button
              variant="ghost"
              size="icon"
              className="hidden lg:inline-flex"
              onClick={startNew}
              aria-label={t('chat.newChat')}
            >
              <MessageSquarePlus />
            </Button>
            <LanguageSwitcher compact align="end" />
            <ThemeToggle />
          </div>
        </header>

        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          {messages.length === 0 && !isSending ? (
            <Welcome />
          ) : (
            <div className="mx-auto w-full max-w-3xl space-y-5 px-3 py-6 sm:px-4">
              {messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  speaking={speech.speakingId === message.id}
                  onSpeak={speak}
                  onRetry={() => void retryLast()}
                  canRetry={canRetry && message.id === lastMessage?.id}
                />
              ))}
              {isSending && <Thinking />}
            </div>
          )}
          <div ref={bottom} className="h-px shrink-0" />
        </div>

        <Composer autoFocus={messages.length > 0} />
      </div>

      <Dialog open={drawerOpen} onOpenChange={setDrawerOpen}>
        <DrawerContent closeLabel={t('common.close')}>
          <DialogTitle className="sr-only">{t('chat.history')}</DialogTitle>
          <HistorySidebar
            onNavigate={() => setDrawerOpen(false)}
            onOpenProfile={() => setProfileOpen(true)}
          />
        </DrawerContent>
      </Dialog>

      <ProfileDialog open={profileOpen} onOpenChange={setProfileOpen} />
    </div>
  )
}
