import { cn } from '@/lib/utils'

/**
 * The mark: a sprout rising out of three furrow lines, inside a squircle. Drawn
 * inline so it inherits currentColor and needs no asset request.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'relative grid place-items-center rounded-[0.7rem] bg-gradient-to-br from-primary to-accent text-primary-foreground shadow-[0_2px_10px_-4px_color-mix(in_oklch,var(--primary)_80%,transparent)]',
        className,
      )}
    >
      <svg viewBox="0 0 24 24" fill="none" className="size-[62%]" aria-hidden>
        <path
          d="M12 20V10.5"
          stroke="currentColor"
          strokeWidth="1.9"
          strokeLinecap="round"
        />
        <path
          d="M12 11c-3.1 0-5-1.9-5-5 3.1 0 5 1.9 5 5Z"
          fill="currentColor"
          opacity="0.92"
        />
        <path
          d="M12 12.5c3.4 0 5.5-2.1 5.5-5.5-3.4 0-5.5 2.1-5.5 5.5Z"
          fill="currentColor"
        />
        <path
          d="M4.5 20h15M6.5 22.4h11"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          opacity="0.55"
        />
      </svg>
    </span>
  )
}

export function Wordmark({
  className,
  size = 'md',
}: {
  className?: string
  size?: 'sm' | 'md' | 'lg'
}) {
  const scale = {
    sm: { box: 'size-8', text: 'text-base' },
    md: { box: 'size-9', text: 'text-lg' },
    lg: { box: 'size-11', text: 'text-xl' },
  }[size]

  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <Logo className={scale.box} />
      <span className={cn('font-display font-semibold tracking-tight', scale.text)}>
        Agromemnon
      </span>
    </span>
  )
}
