'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

/* The Web Speech API is not in TypeScript's DOM library, so the bits used here
   are declared locally rather than pulling in a dependency. */
interface SpeechRecognitionAlternativeLike {
  transcript: string
}
interface SpeechRecognitionResultLike {
  isFinal: boolean
  0: SpeechRecognitionAlternativeLike
}
interface SpeechRecognitionEventLike {
  resultIndex: number
  results: { length: number; [index: number]: SpeechRecognitionResultLike }
}
interface SpeechRecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start: () => void
  stop: () => void
  abort: () => void
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike

function recognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor
    webkitSpeechRecognition?: SpeechRecognitionCtor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export type MicError = 'unsupported' | 'denied' | 'failed' | null

interface UseSpeechRecognition {
  supported: boolean
  listening: boolean
  /** Everything heard so far this session, final text plus the in-flight guess. */
  transcript: string
  /** Smoothed microphone loudness, 0–1, for the input visualiser. */
  level: number
  error: MicError
  start: () => Promise<void>
  stop: () => void
  reset: () => void
}

/** Stop on its own after this much silence, so a forgotten mic does not run on. */
const SILENCE_MS = 6000

export function useSpeechRecognition(locale: string): UseSpeechRecognition {
  const [supported, setSupported] = useState(false)
  const [listening, setListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [level, setLevel] = useState(0)
  const [error, setError] = useState<MicError>(null)

  const recognition = useRef<SpeechRecognitionLike | null>(null)
  const finalText = useRef('')
  const silenceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const audioContext = useRef<AudioContext | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const frame = useRef<number | null>(null)

  useEffect(() => {
    setSupported(recognitionCtor() !== null)
  }, [])

  const stopMeter = useCallback(() => {
    if (frame.current !== null) cancelAnimationFrame(frame.current)
    frame.current = null
    stream.current?.getTracks().forEach((track) => track.stop())
    stream.current = null
    if (audioContext.current && audioContext.current.state !== 'closed') {
      void audioContext.current.close()
    }
    audioContext.current = null
    setLevel(0)
  }, [])

  /* Loudness comes from getUserMedia directly. SpeechRecognition exposes no
     amplitude, and without one the mic button gives no sign it is hearing
     anything — which is the whole point of a voice-first UI. */
  const startMeter = useCallback(async () => {
    const media = await navigator.mediaDevices.getUserMedia({ audio: true })
    stream.current = media
    const context = new AudioContext()
    audioContext.current = context
    const analyser = context.createAnalyser()
    analyser.fftSize = 512
    analyser.smoothingTimeConstant = 0.75
    context.createMediaStreamSource(media).connect(analyser)

    const bins = new Uint8Array(analyser.frequencyBinCount)
    const tick = () => {
      analyser.getByteFrequencyData(bins)
      let sum = 0
      for (let i = 0; i < bins.length; i += 1) sum += bins[i] * bins[i]
      const rms = Math.sqrt(sum / bins.length) / 255
      // Speech sits low in this range; the curve lifts it into something visible.
      setLevel(Math.min(1, rms * 2.6))
      frame.current = requestAnimationFrame(tick)
    }
    tick()
  }, [])

  const stop = useCallback(() => {
    if (silenceTimer.current) clearTimeout(silenceTimer.current)
    silenceTimer.current = null
    recognition.current?.stop()
    setListening(false)
    stopMeter()
  }, [stopMeter])

  const reset = useCallback(() => {
    finalText.current = ''
    setTranscript('')
    setError(null)
  }, [])

  const start = useCallback(async () => {
    const Ctor = recognitionCtor()
    if (!Ctor) {
      setError('unsupported')
      return
    }

    setError(null)
    finalText.current = ''
    setTranscript('')

    try {
      await startMeter()
    } catch {
      // Recognition would fail on the same permission, so stop here with a
      // message the UI can act on.
      setError('denied')
      stopMeter()
      return
    }

    const instance = new Ctor()
    instance.lang = locale
    instance.continuous = true
    instance.interimResults = true
    instance.maxAlternatives = 1

    const armSilenceTimer = () => {
      if (silenceTimer.current) clearTimeout(silenceTimer.current)
      silenceTimer.current = setTimeout(() => instance.stop(), SILENCE_MS)
    }

    instance.onresult = (event) => {
      armSilenceTimer()
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]
        if (result.isFinal) finalText.current += result[0].transcript
        else interim += result[0].transcript
      }
      setTranscript(`${finalText.current}${interim}`.trimStart())
    }

    instance.onerror = (event) => {
      if (event.error === 'aborted') return
      setError(event.error === 'not-allowed' ? 'denied' : 'failed')
      setListening(false)
      stopMeter()
    }

    instance.onend = () => {
      if (silenceTimer.current) clearTimeout(silenceTimer.current)
      silenceTimer.current = null
      setListening(false)
      stopMeter()
    }

    recognition.current = instance
    try {
      instance.start()
      setListening(true)
      armSilenceTimer()
    } catch {
      setError('failed')
      stopMeter()
    }
  }, [locale, startMeter, stopMeter])

  useEffect(
    () => () => {
      if (silenceTimer.current) clearTimeout(silenceTimer.current)
      recognition.current?.abort()
      stopMeter()
    },
    [stopMeter],
  )

  return { supported, listening, transcript, level, error, start, stop, reset }
}
