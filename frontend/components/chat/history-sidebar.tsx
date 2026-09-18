'use client'

import { MessageSquarePlus, Trash2, UserRound } from 'lucide-react'
import { Wordmark } from '@/components/brand'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/contexts/auth-context'
import { useChat } from '@/contexts/chat-context'
import { useLanguage } from '@/contexts/language-context'
import { cn } from '@/lib/utils'

function dayLabel(at: number, locale: string): string {
  const date = new Date(at)
  const today = new Date()
  const sameDay = date.toDateString() === today.toDateString()
  if (sameDay) return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
  return date.toLocaleDateString(locale, { day: 'numeric', month: 'short' })
}

export function HistorySidebar({
  onNavigate,
  onOpenProfile,
}: {
  /** Called after any action that should close the drawer on small screens. */
  onNavigate?: () => void
  onOpenProfile: () => void
}) {
  const { t, locale } = useLanguage()
  const { conversations, activeId, startNew, select, remove, clearAll } = useChat()
  const { profile, signOut } = useAuth()

  return (
    <div className="flex h-full flex-col bg-card/70">
      <div className="px-4 pb-3 pt-4">
        <Wordmark size="sm" />
      </div>

      <div className="px-3">
        <Button
          variant="subtle"
          block
          className="justify-start"
          onClick={() => {
            startNew()
            onNavigate?.()
          }}
        >
          <MessageSquarePlus />
          {t('chat.newChat')}
        </Button>
      </div>

      <div className="mt-6 flex min-h-0 flex-1 flex-col">
        <div className="flex items-center gap-2 px-4 pb-2">
          <h2 className="text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            {t('chat.history')}
          </h2>
          {conversations.length > 0 && (
            <button
              type="button"
              onClick={clearAll}
              className="ml-auto text-[0.6875rem] text-muted-foreground underline-offset-2 transition-colors hover:text-destructive hover:underline"
            >
              {t('chat.deleteAll')}
            </button>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
          {conversations.length === 0 ? (
            <p className="px-2 py-3 text-sm text-muted-foreground">{t('chat.historyEmpty')}</p>
          ) : (
            <ul className="space-y-0.5">
              {conversations.map((conversation) => (
                <li key={conversation.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => {
                      select(conversation.id)
                      onNavigate?.()
                    }}
                    className={cn(
                      'w-full rounded-xl px-3 py-2.5 pr-9 text-left transition-colors',
                      conversation.id === activeId
                        ? 'bg-[color-mix(in_oklch,var(--primary)_13%,transparent)]'
                        : 'hover:bg-muted',
                    )}
                  >
                    <span className="block truncate text-[0.8125rem] font-medium leading-snug">
                      {conversation.title}
                    </span>
                    <span className="mt-0.5 block text-[0.6875rem] text-muted-foreground">
                      {dayLabel(conversation.updatedAt, locale)}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => remove(conversation.id)}
                    aria-label={t('chat.delete')}
                    className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-lg p-2 text-muted-foreground opacity-0 transition-all hover:bg-destructive/12 hover:text-destructive focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="border-t border-border p-3">
        <button
          type="button"
          onClick={() => {
            onOpenProfile()
            onNavigate?.()
          }}
          className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition-colors hover:bg-muted"
        >
          <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[color-mix(in_oklch,var(--primary)_14%,transparent)] text-primary">
            <UserRound className="size-4" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[0.8125rem] font-medium">
              {profile?.name || profile?.email}
            </span>
            <span className="block truncate text-[0.6875rem] text-muted-foreground">
              {[profile?.district, profile?.state].filter(Boolean).join(', ') || t('profile.title')}
            </span>
          </span>
        </button>
        <Button
          variant="ghost"
          size="sm"
          block
          className="mt-1 justify-start text-muted-foreground hover:text-destructive"
          onClick={signOut}
        >
          {t('profile.signOut')}
        </Button>
      </div>
    </div>
  )
}
