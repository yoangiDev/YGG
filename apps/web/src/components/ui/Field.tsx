import { useId, type InputHTMLAttributes, type ReactNode, type Ref, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

/*
 * Controles de formulario (DESIGN.md §8.4): rectos, fondo casi negro y borde
 * ácido al enfocar. En móvil suben a 16px para que iOS no haga zoom.
 */
const control =
  "w-full border border-line-strong bg-field px-3.5 text-sm font-medium text-text placeholder:text-[#79817b] " +
  "transition-colors focus:border-acid focus:outline focus:outline-1 focus:outline-acid " +
  "aria-[invalid=true]:border-danger disabled:opacity-50 max-sm:text-base";

export function Input({ className, ref, ...props }: InputHTMLAttributes<HTMLInputElement> & { ref?: Ref<HTMLInputElement> }) {
  return <input ref={ref} className={cn(control, "h-11 max-sm:h-12", className)} {...props} />;
}

export function Textarea({
  className,
  ref,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { ref?: Ref<HTMLTextAreaElement> }) {
  return <textarea ref={ref} className={cn(control, "min-h-24 py-3 leading-relaxed", className)} {...props} />;
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

/** Etiqueta, control y mensaje de error enlazados para lectores de pantalla. */
export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId();
  const messageId = `${id}-message`;
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-[11px] font-extrabold tracking-[0.06em] text-[#d5ddd7] uppercase">
        {label}
      </label>
      {children({ id, "aria-invalid": Boolean(error), "aria-describedby": error || hint ? messageId : undefined })}
      {(error ?? hint) && (
        <p id={messageId} className={cn(error ? "text-[13px] text-danger" : "text-xs text-subtle")}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}
