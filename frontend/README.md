# Agromemnon web

Next.js frontend for the Agromemnon agent. Farmers sign in with Cognito, ask
questions by voice or text in one of five languages, and get the agent's answer
rendered as markdown with read-aloud.

The backend it talks to lives in [`../backend/Agromemnon`](../backend/Agromemnon):
a Bedrock AgentCore runtime behind an API Gateway `POST /chat` endpoint. See
[`../setup.md`](../setup.md) for deploying it.

## Running it

```bash
cp .env.example .env.local   # fill in the values below
npm install
npm run dev                  # http://localhost:3000
```

| Variable | Where it comes from |
| --- | --- |
| `NEXT_PUBLIC_AGENT_API_URL` | `ApiBaseUrl` output of `infra/api.yaml` (stack `Agromemnon-api`) |
| `NEXT_PUBLIC_COGNITO_USER_POOL_ID` | `UserPoolId` output of `infra/auth.yaml` (stack `Agromemnon-auth`) |
| `NEXT_PUBLIC_COGNITO_CLIENT_ID` | `UserPoolClientId` output of the same stack |

All three are `NEXT_PUBLIC_` and therefore visible in the browser bundle. That is
correct for these values — a public Cognito client has no secret, and the API is
protected by the pool's JWT authorizer rather than by the URL being unguessable.

Sign-up sends a 6-digit code to a real inbox. To make a throwaway account without
one:

```bash
POOL=<user pool id>
aws cognito-idp admin-create-user --user-pool-id $POOL --username you@example.com \
  --user-attributes Name=email,Value=you@example.com Name=email_verified,Value=true \
  --message-action SUPPRESS
aws cognito-idp admin-set-user-password --user-pool-id $POOL \
  --username you@example.com --password 'Fieldtest12' --permanent
```

Delete it again with `aws cognito-idp admin-delete-user`.

## How it fits together

One route (`app/page.tsx`) picks between four screens from the Cognito session:
landing → auth → onboarding → chat. Nothing is deep-linkable, which is why there
is no router.

State lives in three contexts, nested in this order (`components/providers.tsx`):

- **`language-context`** — the active language and `t()`. Dictionaries are in
  `lib/i18n/`; English is the source of truth and the other four are typed
  `Record<TranslationKey, string>`, so a new key fails the build until all five
  have it.
- **`auth-context`** — wraps `lib/cognito.ts`. The farmer's profile (name, age,
  state, district, language) is stored as Cognito user attributes, not in a
  database, so it follows them between devices. Attribute writes refresh the
  session, because the ID token's claims are what the app reads back.
- **`chat-context`** — conversations, sending, retry, cancel. History is in
  localStorage per user; the agent keeps its own history server-side, keyed by
  the session id.

### Session ids

`sessionIdFor(sub, conversationId)` builds the id sent with each turn. The Lambda
pads anything shorter than 33 characters with a hash of itself, deterministically,
so one conversation keeps reaching one agent session — that is what makes
follow-up questions work. The user's `sub` is mixed in so two accounts can never
collide on a session.

### Language

Two things happen when the language is not English:

1. The interface switches dictionary.
2. `buildPrompt()` in `lib/api.ts` prefixes the question with an instruction to
   answer in that language, plus the farmer's district and state. The agent
   defaults to English and its weather/soil/price tools need a location, so
   without this prefix a Kannada question comes back in English and asks where
   the farm is.

To add a language: add a dictionary in `lib/i18n/`, register it in
`lib/i18n/index.ts` (`dictionaries` and `LANGUAGES`, with a BCP-47 locale for
speech), and add its English name to `LANGUAGE_NAMES` in `lib/api.ts`.

### Voice

`hooks/use-speech-recognition.ts` uses the Web Speech API — Chrome, Edge and
Safari, not Firefox, which is why the mic reports an unsupported error rather
than silently doing nothing. Loudness for the level ring is measured separately
through `getUserMedia`, since recognition exposes no amplitude.

`hooks/use-speech-synthesis.ts` reads answers back. It flattens the markdown
first (otherwise the voice reads out asterisks and table pipes) and queues
sentence-sized chunks, because several engines truncate long utterances.

## Known limits

- **A turn must finish in 30 seconds.** That is API Gateway's hard ceiling for
  HTTP APIs. Simple questions come back in 10–20s; anything that scrapes mandi
  prices can exceed it, and the UI then shows a timeout with a retry. Fixing it
  properly means streaming — a Lambda response-streaming Function URL or
  WebSockets — which would also let answers appear token by token instead of all
  at once.
- **One turn at a time per conversation.** The runtime rejects a concurrent
  second turn on the same session, so the composer blocks while a turn is in
  flight.
- **Chat history is local.** Clearing site data loses the transcripts. The
  agent-side history is separate and resets on a cold start.
- **Photo attachments are not read by the agent yet.** The composer accepts a
  photo and sends it as an `image` data URL in the request body, but nothing
  downstream consumes it: the Lambda in `infra/api.yaml` forwards only `prompt`,
  and `app/Agromemnon/main.py` accepts a prompt string or a Strands message list.
  Making it work needs, in order: the Lambda passing `image` through to the
  runtime payload; `main.py` decoding the base64 into a Strands image content
  block (`{"image": {"format": ..., "source": {"bytes": ...}}}`) rather than a
  plain string prompt; and a vision-capable model in `model/load.py`. Until then
  the composer says photo diagnosis is in preview and asks for a written
  description too, so the answer is still useful.
