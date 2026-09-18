/**
 * Conversation history, kept in localStorage per signed-in user.
 *
 * The agent keeps its own conversation state in-process, keyed by the session id
 * we send, so this store exists to redraw the transcript — not to replay it to
 * the agent. Attached photos are held in memory only: a handful of base64 images
 * would blow past the ~5 MB localStorage quota, so a saved message records that
 * a photo was sent without keeping the bytes.
 */
import type { LanguageCode } from './cognito'

export interface ChatMessage {
  id: string
  role: 'user' | 'adviser'
  text: string
  at: number
  language?: LanguageCode
  /** Data URL of a photo the farmer attached. Never persisted. */
  image?: string
  hadImage?: boolean
  /** Set when the agent hit the 30s ceiling mid-answer. */
  truncated?: boolean
  /** Set instead of `text` when the turn failed, so the UI can offer a retry. */
  error?: string
  elapsedMs?: number
}

export interface Conversation {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  messages: ChatMessage[]
}

const MAX_CONVERSATIONS = 40
const TITLE_LENGTH = 64

export function storageKey(userSub: string): string {
  return `agromemnon.chats.${userSub}`
}

export function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

export function titleFrom(text: string): string {
  const flat = text.replace(/\s+/g, ' ').trim()
  if (!flat) return 'Photo'
  return flat.length > TITLE_LENGTH ? `${flat.slice(0, TITLE_LENGTH).trimEnd()}…` : flat
}

/**
 * The agent runtime needs a session id of at least 33 characters and the Lambda
 * pads shorter ones with a hash of themselves — deterministically, so the same
 * conversation keeps reaching the same agent session. The user's `sub` is mixed
 * in so two accounts can never land on one session.
 */
export function sessionIdFor(userSub: string, conversationId: string): string {
  return `${userSub.replace(/[^A-Za-z0-9_-]/g, '')}-${conversationId}`.slice(0, 120)
}

export function loadConversations(userSub: string): Conversation[] {
  try {
    const raw = window.localStorage.getItem(storageKey(userSub))
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (item): item is Conversation =>
        Boolean(item) && typeof item.id === 'string' && Array.isArray(item.messages),
    )
  } catch {
    return []
  }
}

export function saveConversations(userSub: string, conversations: Conversation[]): void {
  const trimmed = conversations.slice(0, MAX_CONVERSATIONS).map((conversation) => ({
    ...conversation,
    messages: conversation.messages.map(({ image, ...rest }) => ({
      ...rest,
      ...(image ? { hadImage: true } : {}),
    })),
  }))

  const key = storageKey(userSub)
  try {
    window.localStorage.setItem(key, JSON.stringify(trimmed))
  } catch {
    // Almost certainly the quota. Keep only the most recent handful rather than
    // losing the lot, and give up quietly if even that fails.
    try {
      window.localStorage.setItem(key, JSON.stringify(trimmed.slice(0, 5)))
    } catch {
      /* history is a convenience; never break the chat over it */
    }
  }
}
