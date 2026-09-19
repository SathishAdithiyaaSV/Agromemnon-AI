'use client'

import { ImagePlus, Mic, Send, Square, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { useChat } from '@/contexts/chat-context'
import { useLanguage } from '@/contexts/language-context'
import { useSpeechRecognition } from '@/hooks/use-speech-recognition'
import { cn } from '@/lib/utils'

const MAX_IMAGE_BYTES = 5 * 1024 * 1024

/**
 * Longest edge the photo is scaled down to before upload.
 *
 * A phone camera produces a 4000px 6 MB JPEG. As a base64 data URL that is 8 MB of
 * request body, which has to cross API Gateway inside the same 30s the diagnosis
 * itself needs, over the rural connection the farmer is actually on. 1280px is well
 * above what the disease classifier sees (it centre-crops to 224px) and above what
 * Bedrock keeps (it downsamples anything larger), so nothing downstream can tell the
 * difference — it just arrives in a fraction of the time.
 */
const MAX_IMAGE_EDGE = 1280
const JPEG_QUALITY = 0.85

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

function loadImage(dataUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('decode failed'))
    img.src = dataUrl
  })
}

/**
 * Scale a photo down to MAX_IMAGE_EDGE and re-encode as JPEG.
 *
 * Returns the original data URL unchanged if the image is already small enough, or
 * if anything in the canvas path fails — a browser that cannot do this should still
 * be able to send the photo, just a slower one. Re-encoding also drops the EXIF
 * block, and with it the GPS coordinates a phone writes into every picture: the
 * agent is told the farmer's district from their profile and has no use for their
 * exact location.
 */
async function shrinkImage(dataUrl: string): Promise<string> {
  try {
    const img = await loadImage(dataUrl)
    const longest = Math.max(img.width, img.height)
    if (!longest) return dataUrl
    if (longest <= MAX_IMAGE_EDGE) return dataUrl

    const scale = MAX_IMAGE_EDGE / longest
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(img.width * scale)
    canvas.height = Math.round(img.height * scale)

    const context = canvas.getContext('2d')
    if (!context) return dataUrl
    context.drawImage(img, 0, 0, canvas.width, canvas.height)

    const shrunk = canvas.toDataURL('image/jpeg', JPEG_QUALITY)
    // A canvas that was never painted encodes to a tiny blank image. Treat an
    // implausibly small result as a failure rather than uploading a white square.
    return shrunk.length > 1024 ? shrunk : dataUrl
  } catch {
    return dataUrl
  }
}

export function Composer({ autoFocus = false }: { autoFocus?: boolean }) {
  const { t, locale } = useLanguage()
  const { send, cancel, isSending } = useChat()
  const mic = useSpeechRecognition(locale)

  const [text, setText] = useState('')
  const [image, setImage] = useState<string | null>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  // What was already typed when the mic started, so dictation appends to it
  // instead of replacing it.
  const typedBeforeMic = useRef('')

  // Focus on wide screens only. On a phone, focusing the composer when a past
  // conversation opens throws the on-screen keyboard over half the transcript.
  useEffect(() => {
    if (!autoFocus) return
    if (window.matchMedia('(min-width: 1024px)').matches) textarea.current?.focus()
  }, [autoFocus])

  // Grow with the content up to a few lines, then scroll inside the box.
  useEffect(() => {
    const node = textarea.current
    if (!node) return
    node.style.height = 'auto'
    node.style.height = `${Math.min(node.scrollHeight, 160)}px`
  }, [text])

  useEffect(() => {
    if (mic.listening) setText(`${typedBeforeMic.current}${mic.transcript}`)
  }, [mic.listening, mic.transcript])

  useEffect(() => {
    if (!mic.error) return
    toast.error(mic.error === 'denied' ? t('chat.micDenied') : t('chat.micUnsupported'))
  }, [mic.error, t])

  const toggleMic = () => {
    if (mic.listening) {
      mic.stop()
      textarea.current?.focus()
      return
    }
    if (!mic.supported) {
      toast.error(t('chat.micUnsupported'))
      return
    }
    typedBeforeMic.current = text ? `${text.trimEnd()} ` : ''
    void mic.start()
  }

  const pickImage = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    if (!file.type.startsWith('image/')) {
      toast.error(t('chat.photoInvalid'))
      return
    }
    if (file.size > MAX_IMAGE_BYTES) {
      toast.error(t('chat.photoTooBig'))
      return
    }
    try {
      setImage(await shrinkImage(await readAsDataUrl(file)))
    } catch {
      toast.error(t('chat.photoInvalid'))
    }
  }

  const submit = () => {
    if (isSending) return
    const body = text.trim()
    if (!body && !image) return
    mic.stop()
    mic.reset()
    typedBeforeMic.current = ''
    setText('')
    setImage(null)
    void send(body, image)
  }

  return (
    <div className="border-t border-border bg-[color-mix(in_oklch,var(--background)_88%,transparent)] backdrop-blur-xl">
      <div className="mx-auto w-full max-w-3xl px-3 pb-3 pt-3 sm:px-4 sm:pb-4">
        {image && (
          <div className="mb-2.5 flex items-center gap-3 rounded-xl border border-border bg-card p-2.5">
            <img src={image} alt="" className="size-14 rounded-lg object-cover" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{t('chat.photoAttached')}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                {t('chat.photoPreview')}
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setImage(null)}
              aria-label={t('chat.remove')}
            >
              <X />
            </Button>
          </div>
        )}

        <div
          className={cn(
            'flex items-end gap-1.5 rounded-[1.6rem] border bg-card p-1.5 transition-colors duration-200',
            mic.listening
              ? 'border-accent shadow-[0_0_0_3px_color-mix(in_oklch,var(--accent)_16%,transparent)]'
              : 'border-border focus-within:border-primary focus-within:shadow-[0_0_0_3px_color-mix(in_oklch,var(--primary)_14%,transparent)]',
          )}
        >
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0 text-muted-foreground hover:text-foreground"
            onClick={() => fileInput.current?.click()}
            aria-label={t('chat.attach')}
          >
            <ImagePlus />
          </Button>

          <textarea
            ref={textarea}
            rows={1}
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                submit()
              }
            }}
            placeholder={image ? t('chat.placeholderPhoto') : t('chat.placeholder')}
            className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-1.5 py-2.5 text-[0.9375rem] leading-relaxed outline-none placeholder:text-muted-foreground/70"
          />

          {/* The ring scales with measured loudness — the only feedback that the
              microphone is actually picking the voice up. */}
          <span className="relative shrink-0">
            {mic.listening && (
              <span
                className="pointer-events-none absolute inset-0 rounded-full bg-accent/30 transition-transform duration-75"
                style={{ transform: `scale(${1 + mic.level * 0.85})` }}
                aria-hidden
              />
            )}
            <Button
              variant={mic.listening ? 'accent' : 'ghost'}
              size="icon"
              className={cn('relative', !mic.listening && 'text-muted-foreground hover:text-foreground')}
              onClick={toggleMic}
              aria-label={mic.listening ? t('chat.stop') : t('chat.mic')}
              aria-pressed={mic.listening}
            >
              <Mic />
            </Button>
          </span>

          {isSending ? (
            <Button
              variant="outline"
              size="icon"
              className="shrink-0"
              onClick={cancel}
              aria-label={t('chat.stop')}
            >
              <Square className="size-3.5" />
            </Button>
          ) : (
            <Button
              size="icon"
              className="shrink-0"
              onClick={submit}
              disabled={!text.trim() && !image}
              aria-label={t('chat.send')}
            >
              <Send />
            </Button>
          )}
        </div>

        <p className="mt-2 text-center text-[0.6875rem] text-muted-foreground">
          {mic.listening ? (
            <span className="font-medium text-accent-foreground">{t('chat.listening')}</span>
          ) : (
            t('chat.disclaimer')
          )}
        </p>

        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={pickImage}
        />
      </div>
    </div>
  )
}
