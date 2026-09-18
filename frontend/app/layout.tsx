import type { Metadata, Viewport } from 'next'
import { Fraunces, Inter } from 'next/font/google'
import { Providers } from '@/components/providers'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

// The display serif carries the brand; body copy stays on Inter, which has the
// Devanagari/Kannada/Tamil fallbacks the headings do not need.
const fraunces = Fraunces({
  subsets: ['latin'],
  variable: '--font-fraunces',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Agromemnon — farm advice in your language',
  description:
    'Ask about crops, irrigation, mandi prices and government schemes by voice or text, in English, Hindi, Kannada, Marathi or Tamil. Answers cite the data behind them.',
  applicationName: 'Agromemnon',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  // Matches the paper/charcoal backgrounds so the mobile browser chrome blends in.
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#fbf9f4' },
    { media: '(prefers-color-scheme: dark)', color: '#16211b' },
  ],
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${fraunces.variable} antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
