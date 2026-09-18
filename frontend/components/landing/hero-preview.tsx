'use client'

import { motion, useReducedMotion } from 'framer-motion'
import { Logo } from '@/components/brand'

/**
 * A still of a real exchange, used in place of a hero image. It shows the two
 * things the product claims — a spoken question in an Indian language, and an
 * answer that cites the data behind it — without a video download.
 */
export function HeroPreview() {
  const reduced = useReducedMotion()

  const rows = [
    ['Tomato', '₹1,850', 'Kolar APMC'],
    ['Onion', '₹2,240', 'Hubballi'],
    ['Ragi', '₹3,410', 'Mandya'],
  ]

  return (
    <motion.div
      initial={reduced ? undefined : { opacity: 0, y: 24, rotate: -1.2 }}
      animate={reduced ? undefined : { opacity: 1, y: 0, rotate: -1.2 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1], delay: 0.15 }}
      className="relative w-full max-w-md rounded-2xl border border-border bg-card p-4 shadow-[0_30px_60px_-30px_color-mix(in_oklch,var(--foreground)_35%,transparent)] sm:p-5"
    >
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <Logo className="size-7" />
        <span className="font-display text-sm font-semibold">Agromemnon</span>
        <span className="ml-auto inline-flex items-center gap-1.5 text-[0.6875rem] font-medium text-muted-foreground">
          <span className="size-1.5 rounded-full bg-leaf" />
          ಕನ್ನಡ
        </span>
      </div>

      <div className="space-y-3">
        <div className="flex justify-end">
          <p className="max-w-[80%] rounded-2xl rounded-br-md bg-primary px-3.5 py-2.5 text-sm text-primary-foreground">
            ಇಂದು ಟೊಮೇಟೊ ದರ ಎಷ್ಟು?
          </p>
        </div>

        <div className="space-y-2.5 rounded-2xl rounded-bl-md bg-muted px-3.5 py-3">
          <p className="text-sm leading-relaxed">
            ಕೋಲಾರ ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ ಇಂದಿನ ದರ ಕ್ವಿಂಟಲ್‌ಗೆ{' '}
            <strong className="font-semibold">₹1,850</strong>.
          </p>

          <div className="overflow-hidden rounded-lg border border-border bg-card">
            <table className="w-full text-[0.6875rem]">
              <thead>
                <tr className="bg-[color-mix(in_oklch,var(--muted)_85%,transparent)] text-left text-muted-foreground">
                  <th className="px-2.5 py-1.5 font-medium">Crop</th>
                  <th className="px-2.5 py-1.5 font-medium">Modal</th>
                  <th className="px-2.5 py-1.5 font-medium">Market</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(([crop, price, market]) => (
                  <tr key={crop} className="border-t border-border">
                    <td className="px-2.5 py-1.5">{crop}</td>
                    <td className="px-2.5 py-1.5 font-medium tabular-nums">{price}</td>
                    <td className="px-2.5 py-1.5 text-muted-foreground">{market}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-[0.6875rem] text-muted-foreground">
            Source: AgMarkNet · mandi_price
          </p>
        </div>
      </div>
    </motion.div>
  )
}
