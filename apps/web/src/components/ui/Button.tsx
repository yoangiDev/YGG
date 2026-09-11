import type { ButtonHTMLAttributes, Ref } from "react";

import { cn } from "@/lib/cn";

import { ArrowIcon, type ArrowDirection } from "./ArrowIcon";
import { Spinner } from "./Spinner";

/*
 * Botones rectos, en mayúsculas y a peso 900 (DESIGN.md §6). Como mucho un
 * primario por bloque; el hover con desplazamiento solo actúa con ratón
 * (la variante hover de Tailwind ya va dentro de `@media (hover: hover)`).
 */
const variants = {
  primary: "border-acid bg-acid text-on-acid hover:-translate-y-0.5 hover:border-acid-hover hover:bg-acid-hover hover:shadow-glow",
  outline: "border-line-button bg-transparent text-text hover:border-acid hover:text-acid",
  ghost: "border-transparent bg-transparent text-muted hover:bg-white/[0.04] hover:text-text",
  danger: "border-danger/40 bg-transparent text-danger hover:border-danger hover:bg-danger/[0.06]",
} as const;

const sizes = {
  sm: "h-9 gap-2 px-3.5 text-[11px]",
  md: "h-[42px] gap-2.5 px-5 text-[12px]",
  lg: "h-[52px] gap-3 px-6 text-[12px]",
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
  /** Flecha de la marca tras el texto. `true` equivale a "ne" (↗). */
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
