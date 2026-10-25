// 数値入力。Enter かフォーカスを外したときに確定。↑↓キーで 1 ずつ（Shift で 10）増減

import { useEffect, useState } from "react";

export function NumberField({
  value,
  unit,
  min,
  max,
  integer,
  prefix,
  compact,
  onCommit,
}: {
  value: number;
  unit?: string;
  min?: number | null;
  max?: number | null;
  integer?: boolean;
  prefix?: string;
  compact?: boolean;
  onCommit: (v: number) => void;
}) {
  const [text, setText] = useState(fmt(value));
  useEffect(() => setText(fmt(value)), [value]);

  const commit = (raw: string) => {
    const v = Number(raw);
    if (raw.trim() === "" || !Number.isFinite(v)) {
      setText(fmt(value));
      return;
    }
    const next = integer ? Math.round(v) : v;
    if (next !== value) onCommit(next);
    else setText(fmt(value));
  };

  return (
    <span className={`num ${compact ? "num-compact" : ""}`}>
      {prefix && <span className="num-prefix">{prefix}</span>}
      <input
        inputMode="decimal"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          if (e.key === "ArrowUp" || e.key === "ArrowDown") {
            e.preventDefault();
            const step = (e.shiftKey ? 10 : 1) * (e.key === "ArrowUp" ? 1 : -1);
            let v = (Number(text) || 0) + step;
            if (min != null) v = Math.max(min, v);
            if (max != null) v = Math.min(max, v);
            setText(fmt(v));
            onCommit(integer ? Math.round(v) : v);
          }
        }}
      />
      {unit && <span className="num-unit">{unit}</span>}
    </span>
  );
}

function fmt(v: number): string {
  return Number.isFinite(v) ? String(Math.round(v * 1000) / 1000) : "";
}
