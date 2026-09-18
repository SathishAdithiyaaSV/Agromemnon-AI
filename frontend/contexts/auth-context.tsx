'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import * as cognito from '@/lib/cognito'
import type { FarmerProfile } from '@/lib/cognito'
import { isLanguageCode } from '@/lib/i18n'
import { useLanguage } from './language-context'

type AuthStatus = 'loading' | 'signedOut' | 'signedIn'

interface AuthContextValue {
  status: AuthStatus
  profile: FarmerProfile | null
  configured: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<{ userConfirmed: boolean }>
  confirmSignUp: (email: string, code: string) => Promise<void>
  resendCode: (email: string) => Promise<void>
  forgotPassword: (email: string) => Promise<void>
  confirmForgotPassword: (email: string, code: string, password: string) => Promise<void>
  updateProfile: (update: Parameters<typeof cognito.updateProfile>[0]) => Promise<void>
  signOut: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [profile, setProfile] = useState<FarmerProfile | null>(null)
  const { setLanguage } = useLanguage()

  // The saved language follows the account, but only on the first load of a
  // session — otherwise a switch made from the header would be undone every
  // time the profile refreshed.
  const languageAdopted = useRef(false)

  const adopt = useCallback(
    (next: FarmerProfile | null) => {
      setProfile(next)
      setStatus(next ? 'signedIn' : 'signedOut')
      if (next && !languageAdopted.current && isLanguageCode(next.language)) {
        setLanguage(next.language)
        languageAdopted.current = true
      }
    },
    [setLanguage],
  )

  useEffect(() => {
    if (!cognito.isAuthConfigured) {
      setStatus('signedOut')
      return
    }
    let cancelled = false
    cognito.getCurrentProfile().then((current) => {
      if (!cancelled) adopt(current)
    })
    return () => {
      cancelled = true
    }
  }, [adopt])

  const signIn = useCallback(
    async (email: string, password: string) => {
      adopt(await cognito.signIn(email, password))
    },
    [adopt],
  )

  const updateProfile = useCallback(
    async (update: Parameters<typeof cognito.updateProfile>[0]) => {
      adopt(await cognito.updateProfile(update))
    },
    [adopt],
  )

  const signOut = useCallback(() => {
    cognito.signOut()
    languageAdopted.current = false
    setProfile(null)
    setStatus('signedOut')
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      profile,
      configured: cognito.isAuthConfigured,
      signIn,
      signUp: cognito.signUp,
      confirmSignUp: cognito.confirmSignUp,
      resendCode: cognito.resendConfirmationCode,
      forgotPassword: cognito.forgotPassword,
      confirmForgotPassword: cognito.confirmForgotPassword,
      updateProfile,
      signOut,
    }),
    [status, profile, signIn, updateProfile, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
