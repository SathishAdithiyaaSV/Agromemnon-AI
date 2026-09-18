'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Reads an answer back aloud.
 *
 * Two details make this work on real answers: the agent replies in markdown,
 * which has to be flattened or the voice reads out asterisks and pipe characters;
 * and several engines silently truncate long utterances, so the text is split
 * into sentence-sized chunks and queued.
 */
const CHUNK_LIMIT = 180

function toSpeakable(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/^\s{0,3}#{1,6}\s*/gm, '')
    .replace(/(\*\*|__|\*|_)/g, '')
    .replace(/^\s*>\s?/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    // Table rows read as gibberish; turn the cell separators into pauses.
    .replace(/^\s*\|?[\s:|-]{6,}\|?\s*$/gm, '')
    .replace(/\s*\|\s*/g, ', ')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function chunk(text: string): string[] {
  const sentences = text.split(/(?<=[.!?。！?॥।])\s+/)
  const chunks: string[] = []
  let current = ''

  for (const sentence of sentences) {
    if (!current) {
      current = sentence
    } else if (current.length + sentence.length + 1 <= CHUNK_LIMIT) {
      current += ` ${sentence}`
    } else {
      chunks.push(current)
      current = sentence
    }
  }
  if (current) chunks.push(current)

  // A single sentence can still exceed what an engine will read; cut it on a space.
  return chunks.flatMap((part) => {
    if (part.length <= CHUNK_LIMIT * 2) return [part]
    return part.match(new RegExp(`.{1,${CHUNK_LIMIT}}(\\s|$)`, 'g')) ?? [part]
  })
}

export function useSpeechSynthesis() {
  const [supported, setSupported] = useState(false)
  const [speakingId, setSpeakingId] = useState<string | null>(null)
  const voices = useRef<SpeechSynthesisVoice[]>([])

  useEffect(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    setSupported(true)

    // Chrome populates the voice list asynchronously; an early read returns [].
    const load = () => {
      voices.current = window.speechSynthesis.getVoices()
    }
    load()
    window.speechSynthesis.addEventListener('voiceschanged', load)
    return () => {
      window.speechSynthesis.removeEventListener('voiceschanged', load)
      window.speechSynthesis.cancel()
    }
  }, [])

  const stop = useCallback(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    setSpeakingId(null)
  }, [])

  const speak = useCallback(
    (id: string, markdown: string, locale: string) => {
      if (!('speechSynthesis' in window)) return

      if (speakingId === id) {
        stop()
        return
      }

      window.speechSynthesis.cancel()
      const body = toSpeakable(markdown)
      if (!body) return

      const language = locale.split('-')[0]
      const voice =
        voices.current.find((candidate) => candidate.lang.replace('_', '-') === locale) ??
        voices.current.find((candidate) => candidate.lang.startsWith(language)) ??
        null

      const parts = chunk(body)
      parts.forEach((part, index) => {
        const utterance = new SpeechSynthesisUtterance(part)
        utterance.lang = locale
        if (voice) utterance.voice = voice
        utterance.rate = 0.95
        if (index === parts.length - 1) {
          utterance.onend = () => setSpeakingId(null)
          utterance.onerror = () => setSpeakingId(null)
        }
        window.speechSynthesis.speak(utterance)
      })

      setSpeakingId(id)
    },
    [speakingId, stop],
  )

  return { supported, speakingId, speak, stop }
}
