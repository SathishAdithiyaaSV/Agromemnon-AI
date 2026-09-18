'use client'

import { useState } from 'react'
import { AuthPanel, type AuthMode } from '@/components/auth/auth-panel'
import { ChatShell } from '@/components/chat/chat-shell'
import { LandingPage } from '@/components/landing/landing-page'
import { OnboardingFlow } from '@/components/onboarding/onboarding-flow'
import { Logo } from '@/components/brand'
import { useAuth } from '@/contexts/auth-context'
import { useLanguage } from '@/contexts/language-context'

/**
 * One route, four screens. Which one shows is decided by the Cognito session
 * rather than the URL: a farmer who is signed in and onboarded should land in
 * the chat, and nothing here is worth deep-linking to.
 */
export default function Home() {
  const { status, profile } = useAuth()
  const { t } = useLanguage()
  const [authMode, setAuthMode] = useState<AuthMode | null>(null)

  if (status === 'loading') {
    return (
      <div className="grid min-h-dvh place-items-center">
        <div className="flex flex-col items-center gap-4">
          <Logo className="size-12 animate-pulse" />
          <p className="text-sm text-muted-foreground">{t('common.loading')}</p>
        </div>
      </div>
    )
  }

  if (status === 'signedOut') {
    return authMode ? (
      <AuthPanel initialMode={authMode} onBack={() => setAuthMode(null)} />
    ) : (
      <LandingPage onSignIn={() => setAuthMode('signIn')} onStart={() => setAuthMode('signUp')} />
    )
  }

  if (!profile?.isOnboarded) return <OnboardingFlow />

  return <ChatShell />
}
