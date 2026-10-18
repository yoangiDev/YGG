import { useId, type InputHTMLAttributes, type ReactNode, type Ref, type SelectHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

/*
 * Form controls (DESIGN.md §8.4): straight, almost-black background and an
 * acid border on focus. On mobile they go up to 16px so iOS doesn't zoom.
 */
const control =
  "w-full border border-line-strong bg-field px-3.5 text-sm font-normal text-text placeholder:text-subtle " +
  "transition-colors focus:border-acid focus:outline focus:outline-1 focus:outline-acid " +
  "aria-[invalid=true]:border-danger disabled:opacity-50 max-sm:text-base";

export function Input({ className, ref, ...props }: InputHTMLAttributes<HTMLInputElement> & { ref?: Ref<HTMLInputElement> }) {
  return <input ref={ref} className={cn(control, "h-11 max-sm:h-12", className)} {...props} />;
}

export function Select({
  className,
  ref,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { ref?: Ref<HTMLSelectElement> }) {
  return (
    <select ref={ref} className={cn(control, "select-chevron h-11 cursor-pointer max-sm:h-12", className)} {...props}>
      {children}
    </select>
  );
}

interface FieldProps {
  label: string;
  error?: string | undefined;
  hint?: string;
  children: (props: { id: string; "aria-invalid": boolean; "aria-describedby": string | undefined }) => ReactNode;
}

/** Label, control and error message linked for screen readers. */
export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId();
  const messageId = `${id}-message`;
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-xs font-black tracking-field text-soft uppercase">
        {label}
      </label>
      {children({ id, "aria-invalid": Boolean(error), "aria-describedby": error || hint ? messageId : undefined })}
      {(error ?? hint) && (
        <p id={messageId} className={cn(error ? "text-sm text-danger" : "text-xs text-subtle")}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}
