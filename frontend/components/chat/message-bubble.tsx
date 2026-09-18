'use client'

import { AlertTriangle, Check, Copy, RotateCcw, Square, Volume2 } from 'lucide-react'
import { useState } from 'react'
import { Logo } from '@/components/brand'
import { MarkdownView } from '@/components/markdown'
import { Button } from '@/components/ui/button'
import { useLanguage } from '@/contexts/language-context'
import type { ChatMessage } from '@/lib/conversations'
import { cn } from '@/lib/utils'

function clockTime(at: number, locale: string): string {
  return new Date(at).toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
}

export function MessageBubble({
  message,
  speaking,
  onSpeak,
  onRetry,
  canRetry,
}: {
  message: ChatMessage
  speaking: boolean
  onSpeak: (message: ChatMessage) => void
  onRetry: () => void
  canRetry: boolean
}) {
  const { t, locale } = useLanguage()
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard access can be blocked; the button simply does nothing */
    }
  }

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[min(34rem,85%)] space-y-2">
          {message.image && (
            <img
              src={message.image}
              alt=""
              className="ml-auto max-h-56 rounded-2xl border border-border object-cover"
            />
          )}
          {message.hadImage && !message.image && (
            <p className="text-right text-xs text-muted-foreground">{t('chat.photoAttached')}</p>
          )}
          {message.text && (
            <p className="whitespace-pre-wrap rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-[0.9375rem] leading-relaxed text-primary-foreground">
              {message.text}
            </p>
          )}
          <p className="text-right text-[0.6875rem] text-muted-foreground">
            {clockTime(message.at, locale)}
          </p>
        </div>
      </div>
    )
  }

  if (message.error) {
    return (
      <div className="flex gap-3">
        <Logo className="mt-0.5 size-8 shrink-0 opacity-60" />
        <div className="max-w-[min(38rem,92%)] rounded-2xl rounded-tl-md border border-destructive/35 bg-destructive/8 px-4 py-3.5">
          <p className="flex items-start gap-2 text-sm leading-relaxed text-foreground">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" />
            {message.error}
          </p>
          {canRetry && (
            <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
              <RotateCcw />
              {t('chat.retry')}
            </Button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3">
      <Logo className="mt-0.5 size-8 shrink-0" />
      <div className="min-w-0 max-w-[min(42rem,92%)]">
        <div className="rounded-2xl rounded-tl-md border border-border bg-card px-4 py-3.5">
          <MarkdownView>{message.text}</MarkdownView>

          {message.truncated && (
            <p className="mt-3 flex items-start gap-2 rounded-lg bg-accent/12 px-3 py-2 text-xs leading-relaxed text-accent-foreground">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
              {t('chat.truncated')}
            </p>
          )}
        </div>

        <div className="mt-1.5 flex flex-wrap items-center gap-1 pl-1">
          <span className="text-[0.6875rem] text-muted-foreground">
            {clockTime(message.at, locale)}
          </span>
          <span className="text-[0.6875rem] text-muted-foreground/60">·</span>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-[0.6875rem] text-muted-foreground hover:text-foreground"
            onClick={() => onSpeak(message)}
            aria-label={speaking ? t('chat.speakStop') : t('chat.speak')}
          >
            {speaking ? <Square className="size-3" /> : <Volume2 className="size-3" />}
            {speaking ? t('chat.speakStop') : t('chat.speak')}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              'h-7 px-2 text-[0.6875rem] text-muted-foreground hover:text-foreground',
              copied && 'text-primary',
            )}
            onClick={copy}
          >
            {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
            {copied ? t('chat.copied') : t('chat.copy')}
          </Button>
        </div>
      </div>
    </div>
  )
}
