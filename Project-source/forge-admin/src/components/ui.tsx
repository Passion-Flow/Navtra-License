// Primitives — editorial/neutral language (status colour only; flat, hairline, restrained).
// Native control copy is wrapped so all user-visible text routes through i18n (§4.6.3).
import { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

export function Button({ children, className = "", variant = "primary", ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode; variant?: "primary" | "ghost" }) {
  const styles = variant === "ghost"
    ? `border border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50
       dark:border-zinc-700 dark:bg-transparent dark:text-zinc-300 dark:hover:bg-zinc-800
       disabled:cursor-not-allowed disabled:opacity-50`
    : `bg-zinc-900 text-white hover:bg-zinc-700
       dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200
       disabled:cursor-not-allowed disabled:bg-zinc-200 disabled:text-zinc-400
       dark:disabled:bg-zinc-800 dark:disabled:text-zinc-600`;
  return (
    <button
      className={`inline-flex items-center justify-center rounded-md px-3.5 py-2 text-sm font-medium transition-colors ${styles} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

export function TextField({
  label,
  error,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-zinc-600 dark:text-zinc-400">{label}</span>
      <input
        className="w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 outline-none transition
          placeholder:text-zinc-400 focus:border-zinc-400 focus:ring-2 focus:ring-zinc-900/5
          dark:border-zinc-800 dark:bg-[#131315] dark:text-zinc-100 dark:placeholder:text-zinc-600 dark:focus:border-zinc-600 dark:focus:ring-white/5"
        aria-invalid={!!error}
        {...rest}
      />
      {error && <span className="mt-1 block text-xs text-red-600 dark:text-red-400">{error}</span>}
    </label>
  );
}

export function Alert({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
      {children}
    </div>
  );
}
