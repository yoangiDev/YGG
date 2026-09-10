import { useId, type InputHTMLAttributes, type ReactNode, type Ref, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

const control =
  "w-full rounded-lg border border-border bg-surface-2 px-3 text-sm text-fg placeholder:text-muted/70 " +
  "transition focus:border-primary focus:outline-none aria-[invalid=true]:border-stat-red";

export function Input({ className, ref, ...props }: InputHTMLAttributes<HTMLInputElement> & { ref?: Ref<HTMLInputElement> }) {
  return <input ref={ref} className={cn(control, "h-10", className)} {...props} />;
}

export function Textarea({
  className,
  ref,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { ref?: Ref<HTMLTextAreaElement> }) {
  return <textarea ref={ref} className={cn(control, "min-h-20 py-2", className)} {...props} />;
}

export function Select({
  className,
  ref,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { ref?: Ref<HTMLSelectElement> }) {
  return (
    <select ref={ref} className={cn(control, "h-10", className)} {...props}>
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

/** Etiqueta, control y mensaje de error enlazados para lectores de pantalla. */
export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId();
  const messageId = `${id}-message`;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[11px] font-semibold tracking-[0.12em] text-muted uppercase">
        {label}
      </label>
      {children({ id, "aria-invalid": Boolean(error), "aria-describedby": error || hint ? messageId : undefined })}
      {(error ?? hint) && (
        <p id={messageId} className={cn("text-xs", error ? "text-stat-red" : "text-muted")}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}
