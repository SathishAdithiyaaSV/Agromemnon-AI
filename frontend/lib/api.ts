/**
 * Client for the deployed /chat endpoint (backend/Agromemnon/infra/api.yaml).
 *
 * The endpoint is synchronous and sits behind API Gateway's hard 30s ceiling, so
 * a turn either returns a full answer, returns partial text flagged `truncated`,
 * or times out. Callers get a typed ChatError for each case so the UI can say
 * something specific instead of "something went wrong".
 */
import { getIdToken, type LanguageCode } from './cognito'

const API_BASE = (process.env.NEXT_PUBLIC_AGENT_API_URL ?? '').replace(/\/+$/, '')

export const isApiConfigured = Boolean(API_BASE)

export type ChatErrorKind =
  | 'unconfigured'
  | 'unauthenticated'
  | 'busy'
  | 'timeout'
  | 'upstream'
  | 'network'
  | 'aborted'

export class ChatError extends Error {
  kind: ChatErrorKind

  constructor(kind: ChatErrorKind, message: string) {
    super(message)
    this.name = 'ChatError'
    this.kind = kind
  }
}

export interface ChatReply {
  text: string
  sessionId: string
  truncated: boolean
  /** Specialist agents that actually ran this turn, in the order they were called. */
  agents: string[]
  warning?: string
  usage?: { inputTokens?: number; outputTokens?: number; totalTokens?: number }
}

/**
 * The roster the backend appends to the answer — see AGENTS_MARKER in
 * app/Agromemnon/main.py for why it rides along in the text rather than in its
 * own field. Anchored to the end and strict about its characters, so a farmer
 * who types something that looks like an HTML comment cannot forge credits.
 */
const AGENTS_MARKER = /\s*<!--agents:([a-z_]+(?:,[a-z_]+)*)-->\s*$/

function splitAgents(raw: string): { text: string; agents: string[] } {
  const match = raw.match(AGENTS_MARKER)
  if (!match) return { text: raw, agents: [] }
  return { text: raw.slice(0, match.index).trimEnd(), agents: match[1].split(',') }
}

/** Language names in English, so the instruction is unambiguous to the model. */
const LANGUAGE_NAMES: Record<LanguageCode, string> = {
  en: 'English',
  hi: 'Hindi',
  kn: 'Kannada',
  mr: 'Marathi',
  ta: 'Tamil',
}

/**
 * The language directive is the only thing prepended to a farmer's message.
 *
 * Who the farmer is and where they farm used to be prepended here too, on the
 * first turn of each session. That is now the backend's job: the chat Lambda reads
 * those details from the Cognito ID token it has already verified and passes them
 * to the agent, which puts them in its system prompt. Two reasons that is better.
 * The claims cannot be edited by the browser, and a system prompt is present on
 * every turn — the first-turn prepend survived only as long as the conversation
 * history did, so a backend restart lost the farmer's district while the screen
 * still showed the conversation that established it.
 *
 * Language stays here because it is a live UI choice. The farmer can flip the
 * switcher mid-conversation, and that has to win over the language saved on their
 * profile.
 */
export function buildPrompt(text: string, options: { language: LanguageCode }): string {
  if (options.language === 'en') return text

  const directive =
    `Reply entirely in ${LANGUAGE_NAMES[options.language]}, including any table headings. ` +
    'Keep crop, scheme and place names recognisable, adding the English name in brackets where it helps.'

  return `[Context for you, not to be repeated back: ${directive}]\n\n${text}`
}

export interface SendChatArgs {
  prompt: string
  sessionId: string
  /** Data URL of an attached photo. Forwarded as-is; see README on backend support. */
  image?: string | null
  signal?: AbortSignal
}

export async function sendChat({
  prompt,
  sessionId,
  image,
  signal,
}: SendChatArgs): Promise<ChatReply> {
  if (!isApiConfigured) {
    throw new ChatError(
      'unconfigured',
      'NEXT_PUBLIC_AGENT_API_URL is not set. Copy .env.example to .env.local and fill it in.',
    )
  }

  const token = await getIdToken()
  if (!token) {
    throw new ChatError('unauthenticated', 'Your session expired. Please sign in again.')
  }

  let response: Response
  try {
    response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ prompt, sessionId, ...(image ? { image } : {}) }),
      signal,
    })
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') {
      throw new ChatError('aborted', 'Request cancelled.')
    }
    throw new ChatError('network', 'Could not reach the adviser. Check your connection.')
  }

  // A 401/403 comes from the API's JWT authorizer, before the Lambda runs, so the
  // body is API Gateway's own and carries nothing worth showing.
  if (response.status === 401 || response.status === 403) {
    throw new ChatError('unauthenticated', 'Your session expired. Please sign in again.')
  }

  let body: Record<string, unknown> = {}
  try {
    body = (await response.json()) as Record<string, unknown>
  } catch {
    throw new ChatError('upstream', `The adviser returned an unreadable response (${response.status}).`)
  }

  const detail = typeof body.error === 'string' ? body.error : ''

  if (!response.ok) {
    // 504 is the Lambda's own "I ran out of time" reply; 503 is API Gateway
    // abandoning the integration at 30s before the Lambda could answer at all.
    // Both mean the same thing to the farmer, and neither carries a useful body.
    if (response.status === 504 || response.status === 503) {
      throw new ChatError(
        'timeout',
        detail || 'That question took longer than 30 seconds. Try asking it in smaller parts.',
      )
    }
    // The runtime rejects a second concurrent turn on the same session id.
    if (/already processing/i.test(detail)) {
      throw new ChatError('busy', 'The adviser is still working on your previous question.')
    }
    throw new ChatError('upstream', detail || `The adviser could not answer (${response.status}).`)
  }

  const raw = typeof body.response === 'string' ? body.response : ''
  // The marker is stripped before the emptiness check: an answer that was nothing
  // but credits is still an empty answer.
  const { text, agents } = splitAgents(raw)
  if (!text) {
    throw new ChatError('upstream', detail || 'The adviser returned an empty answer.')
  }

  return {
    text,
    agents,
    sessionId: typeof body.sessionId === 'string' ? body.sessionId : sessionId,
    truncated: body.truncated === true,
    warning: typeof body.warning === 'string' ? body.warning : undefined,
    usage: (body.usage as ChatReply['usage']) ?? undefined,
  }
}
