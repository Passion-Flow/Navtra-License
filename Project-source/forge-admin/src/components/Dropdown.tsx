// Headless custom dropdown — wraps native controls so all visible copy routes through
// i18n (i18n.md §4.6.3: no bare native <select>). Click-outside + Esc to close, keyboard-open.
import { ReactNode, useEffect, useRef, useState } from "react";

export function Dropdown({
  trigger,
  children,
  align = "right",
  width = "w-56",
  placement = "down",
  triggerClassName,
}: {
  trigger: ReactNode;
  children: (close: () => void) => ReactNode;
  align?: "left" | "right";
  width?: string;
  placement?: "down" | "up";
  triggerClassName?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={triggerClassName ??
          "inline-flex items-center gap-1.5 rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-[13px] text-zinc-600 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-[#131315] dark:text-zinc-300 dark:hover:bg-zinc-900"}
      >
        {trigger}
      </button>
      {open && (
        <div
          role="menu"
          className={`absolute z-20 ${width} max-h-80 overflow-auto rounded-lg border border-zinc-200 bg-white p-1 shadow-lg dark:border-zinc-800 dark:bg-[#161618] ${
            align === "right" ? "right-0" : "left-0"
          } ${placement === "up" ? "bottom-full mb-2" : "mt-2"}`}
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

export function DropdownItem({
  children,
  onSelect,
  selected = false,
  icon,
}: {
  children: ReactNode;
  onSelect: () => void;
  selected?: boolean;
  icon?: ReactNode;
}) {
  return (
    <button
      type="button"
      role="menuitemradio"
      aria-checked={selected}
      onClick={onSelect}
      className="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm text-zinc-700 hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-700"
    >
      <span className="flex items-center gap-2">
        {icon}
        {children}
      </span>
      {selected && (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="text-brand">
          <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </button>
  );
}
