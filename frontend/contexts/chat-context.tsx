'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { buildPrompt, ChatError, sendChat } from '@/lib/api'
import {
  loadConversations,
  newId,
  saveConversations,
  sessionIdFor,
  titleFrom,
  type ChatMessage,
  type Conversation,
} from '@/lib/conversations'
import { useAuth } from './auth-context'
import { useLanguage } from './language-context'

interface ChatContextValue {
  conversations: Conversation[]
  activeId: string | null
  active: Conversation | null
  /** True from the moment a question is sent until the answer or error lands. */
  isSending: boolean
  startNew: () => void
  select: (id: string) => void
  remove: (id: string) => void
  clearAll: () => void
  send: (text: string, image?: string | null) => Promise<void>
  retryLast: () => Promise<void>
  cancel: () => void
}

const ChatContext = createContext<ChatContextValue | null>(null)

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const { profile, signOut } = useAuth()
  const { language } = useLanguage()

  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)

  const abortRef = useRef<AbortController | null>(null)
  const sub = profile?.sub ?? null
  // Which user's history has been read in. Deliberately state, not a ref: it is
  // set in the same update as the loaded conversations, so the saving effect
  // below never sees "hydrated" alongside a still-empty list — which would
  // write [] over the stored history before the load was visible.
  const [hydratedSub, setHydratedSub] = useState<string | null>(null)

  useEffect(() => {
    if (!sub) {
      setConversations([])
      setActiveId(null)
      setHydratedSub(null)
      return
    }
    setConversations(loadConversations(sub))
    setActiveId(null)
    setHydratedSub(sub)
  }, [sub])

  useEffect(() => {
    if (sub && hydratedSub === sub) saveConversations(sub, conversations)
  }, [sub, hydratedSub, conversations])

  const active = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) ?? null,
    [conversations, activeId],
  )

  const startNew = useCallback(() => {
    abortRef.current?.abort()
    setActiveId(null)
  }, [])

  const select = useCallback((id: string) => {
    abortRef.current?.abort()
    setActiveId(id)
  }, [])

  const remove = useCallback(
    (id: string) => {
      setConversations((current) => current.filter((conversation) => conversation.id !== id))
      setActiveId((current) => (current === id ? null : current))
    },
    [],
  )

  const clearAll = useCallback(() => {
    setConversations([])
    setActiveId(null)
  }, [])

  /** Applies a change to one conversation and floats it to the top of the list. */
  const patch = useCallback((id: string, change: (conversation: Conversation) => Conversation) => {
    setConversations((current) => {
      const index = current.findIndex((conversation) => conversation.id === id)
      if (index === -1) return current
      const updated = change(current[index])
      const rest = current.filter((_, i) => i !== index)
      return [updated, ...rest]
    })
  }, [])

  const deliver = useCallback(
    async (conversationId: string, userText: string, image: string | null | undefined) => {
      if (!profile) return

      const startedAt = Date.now()
      const controller = new AbortController()
      abortRef.current = controller
      setIsSending(true)

      try {
        const reply = await sendChat({
          prompt: buildPrompt(userText, { language, profile, includeContext: true }),
          sessionId: sessionIdFor(profile.sub, conversationId),
          image,
          signal: controller.signal,
        })

        const answer: ChatMessage = {
          id: newId(),
          role: 'adviser',
          text: reply.text,
          at: Date.now(),
          language,
          truncated: reply.truncated,
          elapsedMs: Date.now() - startedAt,
        }
        patch(conversationId, (conversation) => ({
          ...conversation,
          updatedAt: answer.at,
          messages: [...conversation.messages, answer],
        }))
      } catch (err) {
        const chatError = err instanceof ChatError ? err : null
        if (chatError?.kind === 'aborted') return

        const failure: ChatMessage = {
          id: newId(),
          role: 'adviser',
          text: '',
          at: Date.now(),
          language,
          error: chatError?.message ?? 'The adviser could not be reached.',
          elapsedMs: Date.now() - startedAt,
        }
        patch(conversationId, (conversation) => ({
          ...conversation,
          updatedAt: failure.at,
          messages: [...conversation.messages, failure],
        }))

        // An expired refresh token cannot be recovered in place; drop to the
        // sign-in screen rather than letting every later turn fail the same way.
        if (chatError?.kind === 'unauthenticated') signOut()
      } finally {
        if (abortRef.current === controller) abortRef.current = null
        setIsSending(false)
      }
    },
    [language, patch, profile, signOut],
  )

  const send = useCallback(
    async (text: string, image?: string | null) => {
      const trimmed = text.trim()
      if (!profile || isSending || (!trimmed && !image)) return

      const question: ChatMessage = {
        id: newId(),
        role: 'user',
        text: trimmed,
        at: Date.now(),
        language,
        ...(image ? { image } : {}),
      }

      let conversationId = activeId
      if (!conversationId) {
        conversationId = newId()
        const conversation: Conversation = {
          id: conversationId,
          title: titleFrom(trimmed),
          createdAt: question.at,
          updatedAt: question.at,
          messages: [question],
        }
        setConversations((current) => [conversation, ...current])
        setActiveId(conversationId)
      } else {
        patch(conversationId, (conversation) => ({
          ...conversation,
          updatedAt: question.at,
          messages: [...conversation.messages, question],
        }))
      }

      await deliver(conversationId, trimmed, image)
    },
    [activeId, deliver, isSending, language, patch, profile],
  )

  /** Drops the failed reply and asks the same question again. */
  const retryLast = useCallback(async () => {
    if (!active || isSending) return

    const messages = [...active.messages]
    while (messages.length > 0 && messages[messages.length - 1].role === 'adviser') {
      messages.pop()
    }
    const lastQuestion = messages[messages.length - 1]
    if (!lastQuestion || lastQuestion.role !== 'user') return

    const conversationId = active.id
    patch(conversationId, (conversation) => ({ ...conversation, messages }))
    await deliver(conversationId, lastQuestion.text, lastQuestion.image)
  }, [active, deliver, isSending, patch])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsSending(false)
  }, [])

  const value = useMemo<ChatContextValue>(
    () => ({
      conversations,
      activeId,
      active,
      isSending,
      startNew,
      select,
      remove,
      clearAll,
      send,
      retryLast,
      cancel,
    }),
    [
      conversations,
      activeId,
      active,
      isSending,
      startNew,
      select,
      remove,
      clearAll,
      send,
      retryLast,
      cancel,
    ],
  )

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}

export function useChat(): ChatContextValue {
  const context = useContext(ChatContext)
  if (!context) throw new Error('useChat must be used inside <ChatProvider>')
  return context
}
