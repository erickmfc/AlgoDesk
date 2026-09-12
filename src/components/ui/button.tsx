import type { ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'ghost'
}

export function Button({ className, variant = 'default', ...props }: ButtonProps) {
  return <button className={cn('inline-flex items-center justify-center gap-1.5', variant === 'ghost' && 'bg-transparent', className)} {...props} />
}
