import React from "react";
import { cn } from "@/lib/utils";

/* ── Panel ──────────────────────────────────────────────────── */
export function Panel({
  title,
  actions,
  children,
  tight,
  className,
  muted,
}: {
  title?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  tight?: boolean;
  className?: string;
  muted?: boolean;
}) {
  return (
    <section className={cn("panel", className)}>
      {(title || actions) && (
        <header className="panel-head">
          {title ? (
            <div className={cn("panel-title", muted && "muted")}>{title}</div>
          ) : (
            <span />
          )}
          {actions ? <div className="panel-actions">{actions}</div> : null}
        </header>
      )}
      <div className={cn("panel-body", tight && "tight")}>{children}</div>
    </section>
  );
}

/* ── Badge ──────────────────────────────────────────────────── */
type Tone = "ok" | "warn" | "err" | "info" | "dim" | "primary";

export function Badge({
  tone = "dim",
  children,
  dot,
}: {
  tone?: Tone;
  children: React.ReactNode;
  dot?: boolean;
}) {
  return (
    <span className={`badge badge-${tone}`}>
      {dot ? <span className={`dot ${tone === "ok" ? "ok" : tone === "err" ? "err" : tone === "warn" ? "warn" : "idle"}`} /> : null}
      {children}
    </span>
  );
}

/* ── Button ─────────────────────────────────────────────────── */
export function Button({
  children,
  variant = "default",
  size = "md",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "primary" | "ghost" | "danger";
  size?: "sm" | "xs" | "md";
}) {
  return (
    <button
      className={cn(
        "btn",
        variant === "primary" && "btn-primary",
        variant === "ghost" && "btn-ghost",
        variant === "danger" && "btn-danger",
        size === "sm" && "btn-sm",
        size === "xs" && "btn-xs",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

/* ── Stat ───────────────────────────────────────────────────── */
export function Stat({
  value,
  label,
  hint,
  tone,
}: {
  value: React.ReactNode;
  label: string;
  hint?: React.ReactNode;
  tone?: "ok" | "warn" | "info";
}) {
  return (
    <div className={cn("stat", tone)}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {hint ? <div className="stat-hint">{hint}</div> : null}
    </div>
  );
}

/* ── Page header ────────────────────────────────────────────── */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="page-head">
      <div>
        <h1 className="page-title">{title}</h1>
        {subtitle ? <p className="page-sub">{subtitle}</p> : null}
      </div>
      {actions ? <div className="panel-actions">{actions}</div> : null}
    </header>
  );
}

/* ── Empty state ────────────────────────────────────────────── */
export function Empty({
  icon,
  title,
  detail,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  detail?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      {icon ? <div className="empty-icon">{icon}</div> : null}
      <div className="strong small">{title}</div>
      {detail ? <div className="tiny">{detail}</div> : null}
      {action}
    </div>
  );
}

/* ── Segmented control ──────────────────────────────────────── */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string; icon?: React.ReactNode }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="seg" role="tablist">
      {options.map((option) => (
        <button
          key={option.value}
          role="tab"
          aria-selected={value === option.value}
          className={cn("seg-btn", value === option.value && "active")}
          onClick={() => onChange(option.value)}
        >
          {option.icon}
          {option.label}
        </button>
      ))}
    </div>
  );
}

/* ── Field ──────────────────────────────────────────────────── */
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint ? <span className="tiny mute">{hint}</span> : null}
    </label>
  );
}

/* ── Progress ───────────────────────────────────────────────── */
export function Progress({ value, thin }: { value: number; thin?: boolean }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("progress", thin && "thin")}>
      <span style={{ width: `${pct}%` }} />
    </div>
  );
}

/* ── Terminal ───────────────────────────────────────────────── */
export function Terminal({
  lines,
  title = "output",
  actions,
  className,
  maxHeight,
}: {
  lines: { text: string; tone?: "ok" | "err" | "cmd" | "dim" }[] | string;
  title?: string;
  actions?: React.ReactNode;
  className?: string;
  maxHeight?: number;
}) {
  const normalized =
    typeof lines === "string"
      ? lines.split("\n").map((text) => ({ text, tone: classify(text) }))
      : lines;
  return (
    <div className={cn("terminal", className)}>
      <div className="terminal-bar">
        <span className="dot ok" />
        <span>{title}</span>
        <span className="spacer" />
        {actions}
      </div>
      <div className="terminal-body" style={maxHeight ? { maxHeight } : undefined}>
        {normalized.length === 0 ? (
          <span className="dim">(no output)</span>
        ) : (
          normalized.map((line, index) => (
            <div key={index} className={cn("terminal-line", line.tone)}>
              {line.text || "\u00a0"}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function classify(text: string): "ok" | "err" | "cmd" | "dim" | undefined {
  if (/^\s*\$ /.test(text) || /^\s*[▶>]/.test(text)) return "cmd";
  if (/\b(error|failed|exception|denied|traceback)\b/i.test(text)) return "err";
  if (/\b(success|connected|ok|complete|found)\b/i.test(text)) return "ok";
  if (/^\[?\d|^\s*$/.test(text)) return "dim";
  return undefined;
}

/* ── Modal ──────────────────────────────────────────────────── */
export function Modal({
  title,
  children,
  footer,
  onClose,
  width,
}: {
  title: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  onClose: () => void;
  width?: number;
}) {
  React.useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={width ? { width } : undefined} role="dialog" aria-modal="true">
        <div className="modal-head">
          <div className="panel-title" style={{ marginBottom: 0 }}>
            {title}
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
            ✕
          </Button>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-foot">{footer}</div> : null}
      </div>
    </div>
  );
}

/* ── Skeleton / loading ─────────────────────────────────────── */
export function Loading({ label = "Loading…", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div className="col" style={{ gap: 10 }}>
      <div className="tiny mute">{label}</div>
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="skeleton" style={{ height: 34 }} />
      ))}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div
      className="small"
      style={{
        border: "1px solid rgba(215,58,73,.4)",
        background: "rgba(215,58,73,.08)",
        color: "#ff8b95",
        padding: "10px 12px",
        borderRadius: 6,
      }}
    >
      {message}
    </div>
  );
}
