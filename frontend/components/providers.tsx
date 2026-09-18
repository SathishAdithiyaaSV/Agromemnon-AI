'use client'

import { ThemeProvider } from 'next-themes'
import { Toaster } from 'sonner'
import { AuthProvider } from '@/contexts/auth-context'
import { ChatProvider } from '@/contexts/chat-context'
import { LanguageProvider } from '@/contexts/language-context'

/**
 * Provider order matters: the auth provider adopts the language saved on the
 * account, and the chat provider keys its stored history by the signed-in user.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
      <LanguageProvider>
        <AuthProvider>
          <ChatProvider>
            {children}
            <Toaster
              position="top-center"
              toastOptions={{
                classNames: {
                  toast:
                    'rounded-xl border border-border bg-popover text-popover-foreground shadow-xl',
                },
              }}
            />
          </ChatProvider>
        </AuthProvider>
      </LanguageProvider>
    </ThemeProvider>
  )
}
