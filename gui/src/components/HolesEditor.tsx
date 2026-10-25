// 穴のリスト [[x, y, サイズ], ...] を表で編集する

import { NumberField } from "./NumberField";

const SIZES = ["M3", "M4", "M5", "M6"];

export function HolesEditor({ value, onChange }: { value: unknown[][]; onChange: (v: unknown[][]) => void }) {
  const set = (i: number, j: number, v: unknown) => onChange(value.map((row, k) => (k === i ? row.map((c, n) => (n === j ? v : c)) : row)));
  return (
    <div className="holes">
      {value.length > 0 && (
        <div className="holes-head">
          <span>x</span>
          <span>y</span>
          <span>サイズ</span>
          <span />
        </div>
      )}
      {value.map((row, i) => (
        <div className="holes-row" key={i}>
          <NumberField value={Number(row[0])} onCommit={(v) => set(i, 0, v)} compact />
          <NumberField value={Number(row[1])} onCommit={(v) => set(i, 1, v)} compact />
          <select value={String(row[2])} onChange={(e) => set(i, 2, e.target.value)}>
            {(SIZES.includes(String(row[2])) ? SIZES : [...SIZES, String(row[2])]).map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
          <button className="icon" onClick={() => onChange(value.filter((_, k) => k !== i))} title="この穴を削除">
            ×
          </button>
        </div>
      ))}
      <button className="small" onClick={() => onChange([...value, [0, 0, "M5"]])}>
        ＋ 穴を追加
      </button>
    </div>
  );
}
