'use client'

import * as DropdownPrimitive from '@radix-ui/react-dropdown-menu'
import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

export const Dropdown = DropdownPrimitive.Root
export const DropdownTrigger = DropdownPrimitive.Trigger
export const DropdownLabel = forwardRef<
  React.ComponentRef<typeof DropdownPrimitive.Label>,
  React.ComponentPropsWithoutRef<typeof DropdownPrimitive.Label>
>(function DropdownLabel({ className, ...props }, ref) {
  return (
    <DropdownPrimitive.Label
      ref={ref}
      className={cn(
        'px-3 pb-1 pt-2 text-[0.6875rem] font-semibold uppercase tracking-[0.08em] text-muted-foreground',
        className,
      )}
      {...props}
    />
  )
})

export const DropdownSeparator = forwardRef<
  React.ComponentRef<typeof DropdownPrimitive.Separator>,
  React.ComponentPropsWithoutRef<typeof DropdownPrimitive.Separator>
>(function DropdownSeparator({ className, ...props }, ref) {
  return (
    <DropdownPrimitive.Separator ref={ref} className={cn('my-1.5 h-px bg-border', className)} {...props} />
  )
})

export const DropdownContent = forwardRef<
  React.ComponentRef<typeof DropdownPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DropdownPrimitive.Content>
>(function DropdownContent({ className, sideOffset = 8, ...props }, ref) {
  return (
    <DropdownPrimitive.Portal>
      <DropdownPrimitive.Content
        ref={ref}
        sideOffset={sideOffset}
        className={cn(
          'z-50 min-w-[12rem] overflow-hidden rounded-xl border border-border bg-popover p-1.5 text-popover-foreground shadow-xl data-[state=open]:animate-sprout',
          className,
        )}
        {...props}
      />
    </DropdownPrimitive.Portal>
  )
})

export const DropdownItem = forwardRef<
  React.ComponentRef<typeof DropdownPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof DropdownPrimitive.Item>
>(function DropdownItem({ className, ...props }, ref) {
  return (
    <DropdownPrimitive.Item
      ref={ref}
      className={cn(
        'flex cursor-pointer select-none items-center gap-2.5 rounded-lg px-3 py-2.5 text-[0.9375rem] outline-none transition-colors data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-[color-mix(in_oklch,var(--primary)_12%,transparent)]',
        className,
      )}
      {...props}
    />
  )
})
