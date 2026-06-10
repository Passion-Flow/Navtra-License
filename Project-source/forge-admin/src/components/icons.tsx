// Lightweight line icons (Lucide-style), inline SVG — themeable via currentColor, no deps.
import { SVGProps } from "react";

type P = SVGProps<SVGSVGElement> & { size?: number };
const base = (size: number): SVGProps<SVGSVGElement> => ({
  width: size, height: size, viewBox: "0 0 24 24", fill: "none",
  stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round",
});

export const IconDashboard = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></svg>
);
export const IconProduct = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><path d="m3.3 7 8.7 5 8.7-5M12 22V12" /></svg>
);
export const IconCustomer = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></svg>
);
export const IconUser = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
);
export const IconIssue = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M12 18v-6M9 15h6" /></svg>
);
export const IconLicense = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="m9 12 2 2 4-4" /></svg>
);
export const IconAudit = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M11 12H3M16 6H3M16 18H3M18 9l3 3-3 3" /></svg>
);
export const IconSettings = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><line x1="4" y1="6" x2="20" y2="6" /><circle cx="9" cy="6" r="2.2" fill="currentColor" stroke="none" /><line x1="4" y1="12" x2="20" y2="12" /><circle cx="15" cy="12" r="2.2" fill="currentColor" stroke="none" /><line x1="4" y1="18" x2="20" y2="18" /><circle cx="9" cy="18" r="2.2" fill="currentColor" stroke="none" /></svg>
);
export const IconCheck = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><path d="m9 11 3 3L22 4" /></svg>
);
export const IconRevoked = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><circle cx="12" cy="12" r="10" /><path d="m15 9-6 6M9 9l6 6" /></svg>
);
export const IconClock = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg>
);
export const IconOnline = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M5 13a10 10 0 0 1 14 0M8.5 16.5a5 5 0 0 1 7 0M2 8.8a15 15 0 0 1 20 0" /><line x1="12" y1="20" x2="12.01" y2="20" /></svg>
);
export const IconOffline = ({ size = 18, ...p }: P) => (
  <svg {...base(size)} {...p}><rect x="2" y="14" width="20" height="8" rx="2" /><rect x="2" y="2" width="20" height="8" rx="2" /><line x1="6" y1="6" x2="6.01" y2="6" /><line x1="6" y1="18" x2="6.01" y2="18" /></svg>
);
export const IconChevron = ({ size = 16, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="m6 9 6 6 6-6" /></svg>
);
export const IconLogout = ({ size = 16, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" /></svg>
);
export const IconCopy = ({ size = 16, ...p }: P) => (
  <svg {...base(size)} {...p}><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
);
export const IconCheckMark = ({ size = 16, ...p }: P) => (
  <svg {...base(size)} {...p}><path d="M20 6 9 17l-5-5" /></svg>
);
