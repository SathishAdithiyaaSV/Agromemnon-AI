/**
 * Client for the deployed /chat endpoint (backend/Agromemnon/infra/api.yaml).
 *
 * The endpoint is synchronous and sits behind API Gateway's hard 30s ceiling, so
 * a turn either returns a full answer, returns partial text flagged `truncated`,
 * or times out. Callers get a typed ChatError for each case so the UI can say
 * something specific instead of "something went wrong".
 */
import { getIdToken, type FarmerProfile, type LanguageCode } from './cognito'

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
  warning?: string
  usage?: { inputTokens?: number; outputTokens?: number; totalTokens?: number }
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
 * The agent answers in English unless told otherwise, and it needs a location for
 * its weather, soil and mandi-price tools. Both are prepended here rather than
 * asked of the farmer: the location goes in only on the first turn of a session,
 * because after that it is already in the agent's conversation history.
 */
export function buildPrompt(
  text: string,
  options: { language: LanguageCode; profile?: FarmerProfile | null; includeContext?: boolean },
): string {
  const directives: string[] = []

  if (options.language !== 'en') {
    directives.push(
      `Reply entirely in ${LANGUAGE_NAMES[options.language]}, including any table headings. Keep crop, scheme and place names recognisable, adding the English name in brackets where it helps.`,
    )
  }

  if (options.includeContext && options.profile) {
    const { name, district, state } = options.profile
    const where = [district, state].filter(Boolean).join(', ')
    const who = [
      name ? `The farmer's name is ${name}.` : null,
      where ? `They farm in ${where}, India — use this location for weather, soil and mandi-price lookups unless they name another place.` : null,
    ].filter(Boolean)
    directives.push(...(who as string[]))
  }

  if (directives.length === 0) return text
  return `[Context for you, not to be repeated back: ${directives.join(' ')}]\n\n${text}`
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

  const text = typeof body.response === 'string' ? body.response : ''
  if (!text) {
    throw new ChatError('upstream', detail || 'The adviser returned an empty answer.')
  }

  return {
    text,
    sessionId: typeof body.sessionId === 'string' ? body.sessionId : sessionId,
    truncated: body.truncated === true,
    warning: typeof body.warning === 'string' ? body.warning : undefined,
    usage: (body.usage as ChatReply['usage']) ?? undefined,
  }
}
