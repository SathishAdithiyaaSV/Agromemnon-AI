'use client'

import { forwardRef, useId } from 'react'
import { cn } from '@/lib/utils'

const controlClasses =
  'w-full rounded-xl border border-input bg-card px-4 text-[0.9375rem] text-foreground shadow-[0_1px_2px_color-mix(in_oklch,var(--foreground)_6%,transparent)] transition-colors placeholder:text-muted-foreground/70 focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color-mix(in_oklch,var(--primary)_25%,transparent)] disabled:opacity-60'

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(controlClasses, 'h-12', className)} {...props} />
  },
)

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...props }, ref) {
  return (
    <textarea ref={ref} className={cn(controlClasses, 'py-3 leading-relaxed', className)} {...props} />
  )
})

interface FieldProps {
  label: string
  hint?: string
  error?: string
  children: (props: { id: string; 'aria-describedby'?: string }) => React.ReactNode
  className?: string
}

/** Label + control + hint/error, wired together so screen readers follow along. */
export function Field({ label, hint, error, children, className }: FieldProps) {
  const id = useId()
  const messageId = hint || error ? `${id}-message` : undefined

  return (
    <div className={cn('space-y-2', className)}>
      <label htmlFor={id} className="block text-sm font-medium text-foreground">
        {label}
      </label>
      {children({ id, 'aria-describedby': messageId })}
      {(error || hint) && (
        <p
          id={messageId}
          className={cn('text-xs leading-relaxed', error ? 'text-destructive' : 'text-muted-foreground')}
        >
          {error || hint}
        </p>
      )}
    </div>
  )
}

export { controlClasses }
