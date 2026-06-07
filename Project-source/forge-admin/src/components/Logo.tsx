// Forge brand mark — hand-crafted SVG (scales crisply, themeable, doubles as favicon).
// A forged hexagonal token with an ember/spark, echoing "forging" a license + activation.

export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="forgeMark" x1="6" y1="2" x2="42" y2="46" gradientUnits="userSpaceOnUse">
          <stop stopColor="#3b82f6" />
          <stop offset="1" stopColor="#0043ce" />
        </linearGradient>
      </defs>
      <path d="M24 2 41.7 12 41.7 36 24 46 6.3 36 6.3 12Z" fill="url(#forgeMark)" />
      <path d="M24 11 27.2 20.8 37 24 27.2 27.2 24 37 20.8 27.2 11 24 20.8 20.8Z" fill="#fff" />
    </svg>
  );
}

export function Logo({ size = 32, withWordmark = true }: { size?: number; withWordmark?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 select-none">
      <LogoMark size={size} />
      {withWordmark && (
        <span
          className="font-bold tracking-tight text-zinc-900 dark:text-white"
          style={{ fontSize: size * 0.62 }}
        >
          Forge
        </span>
      )}
    </span>
  );
}
