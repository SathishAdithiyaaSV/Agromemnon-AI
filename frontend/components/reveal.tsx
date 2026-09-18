import { cn } from '@/lib/utils'

/**
 * Entrance animation for landing-page blocks.
 *
 * Deliberately CSS-only. An earlier version used an in-view observer, which left
 * the copy at `opacity: 0` whenever the observer did not fire — the content of a
 * marketing page must never depend on JavaScript to become visible. The keyframe
 * ends at full opacity and is switched off under `prefers-reduced-motion`.
 */
export function Reveal({
  children,
  className,
  delay = 0,
  as: Component = 'div',
}: {
  children: React.ReactNode
  className?: string
  delay?: number
  as?: 'div' | 'section' | 'li'
}) {
  return (
    <Component
      className={cn('reveal', className)}
      style={delay ? { animationDelay: `${delay}s` } : undefined}
    >
      {children}
    </Component>
  )
}
