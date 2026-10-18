import type { ButtonHTMLAttributes, Ref } from "react";

import { cn } from "@/lib/cn";

import { ArrowIcon, type ArrowDirection } from "./ArrowIcon";
import { Spinner } from "./Spinner";

/*
 * Straight, uppercase buttons at weight 900 (DESIGN.md §6). At most one
 * primary per block; the hover with displacement only acts with a mouse
 * (Tailwind's hover variant is already inside `@media (hover: hover)`).
 */
const variants = {
  primary: "border-acid bg-acid text-on-acid hover:-translate-y-0.5 hover:border-acid-hover hover:bg-acid-hover hover:shadow-glow",
  outline: "border-line-button bg-transparent text-text hover:border-acid hover:text-acid",
  ghost: "border-transparent bg-transparent text-muted hover:bg-white/[0.04] hover:text-text",
  danger: "border-danger/40 bg-transparent text-danger hover:border-danger hover:bg-danger/[0.06]",
} as const;

const sizes = {
  sm: "h-9 gap-2 px-3.5 text-xs",
  md: "h-[42px] gap-2.5 px-5 text-xs",
  lg: "h-[52px] gap-3 px-6 text-xs",
  icon: "size-9 p-0",
} as const;

export type ButtonVariant = keyof typeof variants;
export type ButtonSize = keyof typeof sizes;

/** Button classes for elements that aren't <button>, like a <Link> that looks like a button. */
export function buttonClasses({
  variant = "primary",
  size = "md",
  className,
}: { variant?: ButtonVariant; size?: ButtonSize; className?: string | undefined } = {}): string {
  return cn(
    "inline-flex cursor-pointer items-center justify-center border font-black tracking-[0.045em] whitespace-nowrap uppercase",
    "transition-[translate,background-color,border-color,color,box-shadow] duration-200",
    "disabled:pointer-events-none disabled:opacity-45",
    variants[variant],
    sizes[size],
    className,
  );
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  /** Brand arrow after the text. `true` equals "ne" (↗). */
  arrow?: boolean | ArrowDirection;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  arrow = false,
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
      {loading && <Spinner className="size-3.5" label="Working" />}
      {children}
      {arrow && !loading && <ArrowIcon direction={arrow === true ? "ne" : arrow} />}
    </button>
  );
}
