import type { ButtonHTMLAttributes, Ref } from "react";

import { cn } from "@/lib/cn";

import { Spinner } from "./Spinner";

const variants = {
  primary:
    "bg-gradient-to-br from-primary to-primary-dim text-white shadow-[0_0_14px_hsl(270_70%_62%/0.25)] hover:brightness-110",
  outline: "border border-primary/60 text-primary-light hover:bg-primary/10",
  ghost: "text-muted hover:bg-surface-2 hover:text-fg",
  danger: "border border-stat-red/50 text-stat-red hover:bg-stat-red/10",
} as const;

const sizes = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  icon: "size-9 p-0",
} as const;

export type ButtonVariant = keyof typeof variants;
export type ButtonSize = keyof typeof sizes;

/** Clases de botón para elementos que no son <button>, como un <Link> con aspecto de botón. */
export function buttonClasses({
  variant = "primary",
  size = "md",
  className,
}: { variant?: ButtonVariant; size?: ButtonSize; className?: string | undefined } = {}): string {
  return cn(
    "inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg font-semibold tracking-wide whitespace-nowrap transition",
    "disabled:cursor-not-allowed disabled:opacity-50",
    variants[variant],
    sizes[size],
    className,
  );
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className,
  children,
  disabled,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled === true || loading}
      aria-busy={loading || undefined}
      className={buttonClasses({ variant, size, className })}
      {...props}
    >
      {loading && <Spinner className="size-4" label="Working" />}
      {children}
    </button>
  );
}
