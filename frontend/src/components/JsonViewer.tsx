import { useState } from "react";
import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cx";
import { Button } from "./Button";

export interface JsonViewerProps {
  data: unknown;
  /** Levels expanded at first. Default 1. */
  defaultDepth?: number;
  className?: string;
}

function Primitive({ value }: { value: unknown }) {
  if (value === null) return <span className="text-muted">null</span>;
  if (typeof value === "string") return <span className="text-accent-ink">&quot;{value}&quot;</span>;
  if (typeof value === "number") return <span className="text-info-ink">{String(value)}</span>;
  return <span className="text-due-ink">{String(value)}</span>;
}

function Node({ name, value, depth, defaultDepth }: { name?: string; value: unknown; depth: number; defaultDepth: number }) {
  const isArr = Array.isArray(value);
  const isObj = value !== null && typeof value === "object";
  const key = name !== undefined ? <span className="text-ink">{name}: </span> : null;
  if (!isObj) {
    return (
      <div className="ps-4">
        {key}
        <Primitive value={value} />
      </div>
    );
  }
  const entries: Array<[string, unknown]> = isArr
    ? (value as unknown[]).map((v, i) => [String(i), v])
    : Object.entries(value as Record<string, unknown>);
  const summary = isArr ? `[${entries.length}]` : `{${entries.length}}`;
  return (
    <details open={depth < defaultDepth} className="ps-4">
      <summary className="cursor-pointer select-none">
        {key}
        <span className="text-muted">{summary}</span>
      </summary>
      {entries.map(([k, v]) => (
        <Node key={k} name={k} value={v} depth={depth + 1} defaultDepth={defaultDepth} />
      ))}
    </details>
  );
}

/** Collapsible, read-only JSON tree with a copy button. Used in the FHIR drawer. Always left to right. */
export function JsonViewer({ data, defaultDepth = 1, className }: JsonViewerProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const [version, setVersion] = useState(0);
  const [depth, setDepth] = useState(defaultDepth);

  async function copy() {
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be blocked */
    }
  }

  return (
    <div className={className}>
      <div className="mb-2 flex gap-2">
        <Button size="sm" variant="secondary" onClick={copy}>
          {copied ? t("json.copied") : t("json.copy")}
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            setDepth(99);
            setVersion((v) => v + 1);
          }}
        >
          {t("json.expand")}
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            setDepth(0);
            setVersion((v) => v + 1);
          }}
        >
          {t("json.collapse")}
        </Button>
      </div>
      <div
        dir="ltr"
        lang="en"
        className={cx("overflow-x-auto rounded-control border border-line bg-surface-2 p-3 font-mono text-xs leading-relaxed")}
      >
        <Node key={version} value={data} depth={0} defaultDepth={depth} />
      </div>
    </div>
  );
}
