'use client'

import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'relative inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium transition-[background-color,box-shadow,transform,color] duration-150 active:translate-y-px disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary:
          'bg-primary text-primary-foreground shadow-[0_1px_0_0_color-mix(in_oklch,white_25%,transparent)_inset,0_6px_18px_-8px_color-mix(in_oklch,var(--primary)_70%,transparent)] hover:bg-[color-mix(in_oklch,var(--primary)_92%,black)]',
        accent:
          'bg-accent text-accent-foreground shadow-[0_6px_18px_-8px_color-mix(in_oklch,var(--accent)_70%,transparent)] hover:bg-[color-mix(in_oklch,var(--accent)_92%,black)]',
        outline:
          'border border-border bg-transparent hover:bg-[color-mix(in_oklch,var(--primary)_7%,transparent)] hover:border-[color-mix(in_oklch,var(--primary)_35%,var(--border))]',
        subtle:
          'bg-[color-mix(in_oklch,var(--primary)_10%,transparent)] text-[color-mix(in_oklch,var(--primary)_75%,var(--foreground))] hover:bg-[color-mix(in_oklch,var(--primary)_16%,transparent)]',
        ghost: 'hover:bg-muted',
        destructive: 'bg-destructive text-destructive-foreground hover:opacity-90',
        link: 'text-primary underline underline-offset-4 hover:opacity-80 rounded-none',
      },
      size: {
        sm: 'h-9 px-3.5 text-sm [&_svg]:size-4',
        md: 'h-11 px-5 text-[0.9375rem] [&_svg]:size-4',
        lg: 'h-13 px-7 text-base [&_svg]:size-5',
        icon: 'size-10 [&_svg]:size-4',
        iconLg: 'size-12 [&_svg]:size-5',
      },
      block: { true: 'w-full', false: '' },
    },
    defaultVariants: { variant: 'primary', size: 'md', block: false },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  loading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, block, asChild, loading, children, disabled, ...props },
  ref,
) {
  // `asChild` renders the caller's element, which cannot host a spinner, so the
  // two are mutually exclusive by construction.
  if (asChild) {
    return (
      <Slot ref={ref} className={cn(buttonVariants({ variant, size, block }), className)} {...props}>
        {children}
      </Slot>
    )
  }

  return (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size, block }), className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="animate-spin" aria-hidden />}
      {children}
    </button>
  )
})

export { buttonVariants }
