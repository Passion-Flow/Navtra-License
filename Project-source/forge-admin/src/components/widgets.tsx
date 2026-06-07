import { ReactNode, useEffect, useRef, useState } from "react";
import { useI18n } from "@/i18n/useI18n";
import { IconChevron } from "./icons";

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex items-end justify-between">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-zinc-200/80 bg-white shadow-[0_1px_2px_rgba(16,24,40,.04),0_1px_3px_rgba(16,24,40,.06)] dark:border-zinc-800 dark:bg-[#131315] dark:shadow-none ${className}`}>
      {children}
    </div>
  );
}

export function Table({ head, children, cols, align }: {
  head: ReactNode[]; children: ReactNode; cols?: string[]; align?: ("left" | "right" | "center")[];
}) {
  return (
    <Card className="overflow-hidden">
      <table className={`w-full text-sm ${cols ? "table-fixed" : ""}`}>
        {cols && (
          <colgroup>{cols.map((w, i) => <col key={i} style={{ width: w || undefined }} />)}</colgroup>
        )}
        <thead>
          <tr className="border-b border-zinc-200 text-left dark:border-zinc-800">
            {head.map((h, i) => (
              <th key={i} className={`px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-zinc-400 dark:text-zinc-500 ${align?.[i] === "right" ? "text-right" : ""}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/70 [&>tr]:h-14 [&>tr]:transition-colors [&>tr:hover]:bg-zinc-50/70 dark:[&>tr:hover]:bg-zinc-800/30">{children}</tbody>
      </table>
    </Card>
  );
}

export function Td({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <td className={`px-4 align-middle text-zinc-700 dark:text-zinc-300 ${className}`}>{children}</td>;
}

// Initial avatar — gives the first column of a table a visual anchor (like the reference).
export function Avatar({ name, src }: { name: string; src?: string | null }) {
  if (src) {
    return <img src={src} alt={name} className="h-8 w-8 shrink-0 rounded-full object-cover" />;
  }
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-100 text-[13px] font-semibold text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
      {(name || "?").charAt(0).toUpperCase()}
    </span>
  );
}

// Two-line primary cell: bold primary over a muted secondary line.
export function Primary({ title, sub }: { title: ReactNode; sub?: ReactNode }) {
  return (
    <div className="leading-tight">
      <div className="font-medium text-zinc-900 dark:text-zinc-100">{title}</div>
      {sub && <div className="mt-0.5 text-xs text-zinc-400 dark:text-zinc-500">{sub}</div>}
    </div>
  );
}

export function RowAction({ children, onClick, danger }: { children: ReactNode; onClick: () => void; danger?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-2 py-1 text-[13px] transition-colors ${
        danger
          ? "text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/40"
          : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
      }`}
    >
      {children}
    </button>
  );
}

const DOT: Record<string, string> = {
  active: "bg-emerald-500", issued: "bg-sky-500", expiring: "bg-amber-500",
  expired: "bg-zinc-400", revoked: "bg-red-500", locked: "bg-red-500",
  success: "bg-emerald-500", failure: "bg-red-500",
};

// Linear-style status: a coloured dot + neutral text (no loud coloured pills).
export function Badge({ status, label }: { status: string; label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[13px] text-zinc-600 dark:text-zinc-300">
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[status] || "bg-zinc-400"}`} />
      {label ?? status}
    </span>
  );
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-lg rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-[#161618]" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-5 text-base font-semibold text-zinc-900 dark:text-zinc-50">{title}</h2>
        {children}
      </div>
    </div>
  );
}

// Custom listbox (NOT a native <select>) — i18n.md §4.6.3: native control text can't be
// styled or localized, so all user-facing dropdowns are custom components.
export interface Option { value: string; label: string }

export function Select({ label, value, onChange, options, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; options: Option[]; placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, [open]);

  const selected = options.find((o) => o.value === value);
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-zinc-600 dark:text-zinc-400">{label}</span>
      <div className="relative" ref={ref}>
        <button
          type="button" onClick={() => setOpen((v) => !v)} aria-haspopup="listbox" aria-expanded={open}
          className="flex w-full items-center justify-between rounded-md border border-zinc-200 bg-white px-3 py-2 text-left text-sm outline-none transition focus:border-zinc-400 dark:border-zinc-800 dark:bg-[#131315] dark:focus:border-zinc-600"
        >
          <span className={selected ? "text-zinc-900 dark:text-zinc-100" : "text-zinc-400"}>
            {selected ? selected.label : (placeholder ?? "—")}
          </span>
          <IconChevron size={14} {...{ className: "text-zinc-400" }} />
        </button>
        {open && (
          <div role="listbox" className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-md border border-zinc-200 bg-white p-1 shadow-lg dark:border-zinc-800 dark:bg-[#161618]">
            {options.map((o) => (
              <button
                key={o.value} type="button" role="option" aria-selected={o.value === value}
                onClick={() => { onChange(o.value); setOpen(false); }}
                className="flex w-full items-center justify-between rounded px-3 py-1.5 text-left text-sm text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                {o.label}
                {o.value === value && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-zinc-900 dark:text-white">
                    <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </label>
  );
}

export function CopyBox({ value }: { value: string }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-stretch gap-2">
      <div className="flex-1 overflow-x-auto whitespace-pre-wrap rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 font-mono text-[13px] text-zinc-700 break-all dark:border-zinc-800 dark:bg-[#0e0e10] dark:text-zinc-300">
        {value}
      </div>
      <button
        type="button"
        onClick={() => { navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
        className="shrink-0 rounded-md bg-zinc-900 px-3 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-white dark:text-zinc-900 dark:hover:bg-zinc-200"
      >
        {copied ? t("common.copied") : t("common.copy")}
      </button>
    </div>
  );
}

export function EmptyState({ text }: { text: string }) {
  return <div className="py-16 text-center text-sm text-zinc-400 dark:text-zinc-600">{text}</div>;
}

// Adaptive page size: how many table rows fit the current viewport height (no scroll).
// Recomputes on window resize so the table fills whatever browser size the user has.
export function useFitRows(rowPx = 56, reserved = 250, min = 4): number {
  const calc = () =>
    Math.max(min, Math.floor((window.innerHeight - reserved) / rowPx));
  const [rows, setRows] = useState(calc);
  useEffect(() => {
    const onResize = () => setRows(calc());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowPx, reserved, min]);
  return rows;
}

function pageList(current: number, last: number): (number | "…")[] {
  if (last <= 7) return Array.from({ length: last }, (_, i) => i + 1);
  const out: (number | "…")[] = [1];
  const lo = Math.max(2, current - 1), hi = Math.min(last - 1, current + 1);
  if (lo > 2) out.push("…");
  for (let i = lo; i <= hi; i++) out.push(i);
  if (hi < last - 1) out.push("…");
  out.push(last);
  return out;
}

export function Pagination({ page, pageSize, total, onPage }: {
  page: number; pageSize: number; total: number; onPage: (p: number) => void;
}) {
  const { t } = useI18n();
  const last = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  const btn = "flex h-7 min-w-7 items-center justify-center rounded-md px-2 text-[13px] disabled:opacity-40";
  return (
    <div className="mt-4 flex items-center justify-between">
      <span className="text-[13px] text-zinc-400 tnum dark:text-zinc-500">
        {t("common.showing").replace("{from}", String(from)).replace("{to}", String(to)).replace("{total}", String(total))}
      </span>
      <div className="flex items-center gap-1">
        <button className={`${btn} border border-zinc-200 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-900`}
          onClick={() => onPage(page - 1)} disabled={page <= 1}>‹</button>
        {pageList(page, last).map((p, i) =>
          p === "…" ? <span key={`e${i}`} className="px-1 text-zinc-400">…</span> : (
            <button key={p} onClick={() => onPage(p)}
              className={`${btn} tnum ${p === page ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900" : "border border-zinc-200 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-900"}`}>
              {p}
            </button>
          ),
        )}
        <button className={`${btn} border border-zinc-200 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-900`}
          onClick={() => onPage(page + 1)} disabled={page >= last}>›</button>
      </div>
    </div>
  );
}
