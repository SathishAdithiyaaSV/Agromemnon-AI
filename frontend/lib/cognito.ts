/**
 * Thin wrapper over amazon-cognito-identity-js.
 *
 * The farmer's profile lives on the Cognito user as attributes rather than in a
 * separate database, so it follows them to a new device. Attribute writes do not
 * update the cached ID token, so every mutation refreshes the session — otherwise
 * the token the API sees, and the claims we read back, would lag behind.
 */
import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserAttribute,
  CognitoUserPool,
  CognitoUserSession,
  type ICognitoUserAttributeData,
} from 'amazon-cognito-identity-js'

export type LanguageCode = 'en' | 'hi' | 'kn' | 'mr' | 'ta'

export interface FarmerProfile {
  sub: string
  email: string
  name?: string
  age?: number
  state?: string
  district?: string
  language?: LanguageCode
  isOnboarded: boolean
}

const USER_POOL_ID = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? ''
const CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? ''

export const isAuthConfigured = Boolean(USER_POOL_ID && CLIENT_ID)

let pool: CognitoUserPool | null = null

function userPool(): CognitoUserPool {
  if (!isAuthConfigured) {
    throw new Error(
      'Cognito is not configured. Set NEXT_PUBLIC_COGNITO_USER_POOL_ID and NEXT_PUBLIC_COGNITO_CLIENT_ID.',
    )
  }
  if (!pool) {
    pool = new CognitoUserPool({ UserPoolId: USER_POOL_ID, ClientId: CLIENT_ID })
  }
  return pool
}

function userFor(email: string): CognitoUser {
  return new CognitoUser({ Username: email.trim().toLowerCase(), Pool: userPool() })
}

/** Cognito surfaces failures as objects with `code`/`message`; turn them into something showable. */
export class AuthError extends Error {
  code: string

  constructor(code: string, message: string) {
    super(message)
    this.name = 'AuthError'
    this.code = code
  }
}

function toAuthError(err: unknown): AuthError {
  const e = err as { code?: string; name?: string; message?: string } | null
  return new AuthError(e?.code ?? e?.name ?? 'UnknownError', e?.message ?? 'Authentication failed.')
}

function profileFromSession(session: CognitoUserSession): FarmerProfile {
  const claims = session.getIdToken().decodePayload() as Record<string, unknown>
  const str = (key: string) => {
    const value = claims[key]
    return typeof value === 'string' && value.length > 0 ? value : undefined
  }
  const age = Number(str('custom:age'))

  return {
    sub: str('sub') ?? '',
    email: str('email') ?? '',
    name: str('name'),
    age: Number.isFinite(age) && age > 0 ? age : undefined,
    state: str('custom:state'),
    district: str('custom:district'),
    language: str('custom:language') as LanguageCode | undefined,
    isOnboarded: str('custom:onboarded') === 'true',
  }
}

export function signUp(email: string, password: string): Promise<{ userConfirmed: boolean }> {
  return new Promise((resolve, reject) => {
    userPool().signUp(email.trim().toLowerCase(), password, [], [], (err, result) => {
      if (err || !result) return reject(toAuthError(err))
      resolve({ userConfirmed: result.userConfirmed ?? false })
    })
  })
}

export function confirmSignUp(email: string, code: string): Promise<void> {
  return new Promise((resolve, reject) => {
    userFor(email).confirmRegistration(code.trim(), true, (err) =>
      err ? reject(toAuthError(err)) : resolve(),
    )
  })
}

export function resendConfirmationCode(email: string): Promise<void> {
  return new Promise((resolve, reject) => {
    userFor(email).resendConfirmationCode((err) => (err ? reject(toAuthError(err)) : resolve()))
  })
}

export function signIn(email: string, password: string): Promise<FarmerProfile> {
  return new Promise((resolve, reject) => {
    const user = userFor(email)
    user.authenticateUser(
      new AuthenticationDetails({ Username: email.trim().toLowerCase(), Password: password }),
      {
        onSuccess: (session) => resolve(profileFromSession(session)),
        onFailure: (err) => reject(toAuthError(err)),
        // A pool-created user (rather than a self-signed-up one) lands here on first
        // login. The web app has no flow for it, so say so instead of hanging.
        newPasswordRequired: () =>
          reject(
            new AuthError(
              'NewPasswordRequired',
              'This account needs a new password. Use "Forgot password" to set one.',
            ),
          ),
      },
    )
  })
}

export function forgotPassword(email: string): Promise<void> {
  return new Promise((resolve, reject) => {
    userFor(email).forgotPassword({
      onSuccess: () => resolve(),
      onFailure: (err) => reject(toAuthError(err)),
    })
  })
}

export function confirmForgotPassword(
  email: string,
  code: string,
  newPassword: string,
): Promise<void> {
  return new Promise((resolve, reject) => {
    userFor(email).confirmPassword(code.trim(), newPassword, {
      onSuccess: () => resolve(),
      onFailure: (err) => reject(toAuthError(err)),
    })
  })
}

/** Current session, refreshed by the SDK when the ID token has expired. `null` when signed out. */
export function getSession(): Promise<CognitoUserSession | null> {
  return new Promise((resolve) => {
    if (!isAuthConfigured) return resolve(null)
    const user = userPool().getCurrentUser()
    if (!user) return resolve(null)
    user.getSession((err: Error | null, session: CognitoUserSession | null) => {
      resolve(err || !session?.isValid() ? null : session)
    })
  })
}

export async function getIdToken(): Promise<string | null> {
  const session = await getSession()
  return session ? session.getIdToken().getJwtToken() : null
}

export async function getCurrentProfile(): Promise<FarmerProfile | null> {
  const session = await getSession()
  return session ? profileFromSession(session) : null
}

/** Force a token refresh so freshly written attributes appear in the ID token's claims. */
function refreshSession(user: CognitoUser, session: CognitoUserSession): Promise<FarmerProfile> {
  return new Promise((resolve, reject) => {
    user.refreshSession(session.getRefreshToken(), (err, fresh: CognitoUserSession) => {
      if (err || !fresh) return reject(toAuthError(err))
      resolve(profileFromSession(fresh))
    })
  })
}

type ProfileUpdate = Partial<Pick<FarmerProfile, 'name' | 'age' | 'state' | 'district' | 'language'>> & {
  isOnboarded?: boolean
}

export function updateProfile(update: ProfileUpdate): Promise<FarmerProfile> {
  return new Promise((resolve, reject) => {
    const user = userPool().getCurrentUser()
    if (!user) return reject(new AuthError('NotAuthenticated', 'You are signed out.'))

    user.getSession((sessionErr: Error | null, session: CognitoUserSession | null) => {
      if (sessionErr || !session) return reject(toAuthError(sessionErr))

      const pairs: ICognitoUserAttributeData[] = []
      const push = (Name: string, Value?: string) => {
        if (Value !== undefined) pairs.push({ Name, Value })
      }
      push('name', update.name)
      push('custom:age', update.age === undefined ? undefined : String(update.age))
      push('custom:state', update.state)
      push('custom:district', update.district)
      push('custom:language', update.language)
      push('custom:onboarded', update.isOnboarded === undefined ? undefined : String(update.isOnboarded))

      if (pairs.length === 0) return resolve(profileFromSession(session))

      user.updateAttributes(
        pairs.map((pair) => new CognitoUserAttribute(pair)),
        (err) => {
          if (err) return reject(toAuthError(err))
          refreshSession(user, session).then(resolve, reject)
        },
      )
    })
  })
}

export function signOut(): void {
  if (!isAuthConfigured) return
  userPool().getCurrentUser()?.signOut()
}
