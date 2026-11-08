// 上のツールバー: デザインの切り替え・Undo/Redo・書き出し・チェック結果（保存は自動）

import { useEffect, useRef, useState } from "react";
import { SNAP_CHOICES, flushSave, useStore } from "../store";
import { useTheme, type ThemePref } from "../theme";

export function Toolbar() {
  const { designs, name, dirty, past, future, issues, tool, snap } = useStore();
  const { openDesign, newDesign, setName, build, undo, redo, setTool, setSnap } = useStore.getState();
  const [draft, setDraft] = useState(name);
  useEffect(() => setDraft(name), [name]);

  // 別のデザインに移る前に、待っている自動保存を済ませる。保存できない（名前のない新規など）ときだけ確認する
  const leave = async () => (await flushSave()) || window.confirm("保存していない変更があります。破棄しますか？");
  const errors = issues.filter((i) => i.level === "error").length;
  const warnings = issues.length - errors;

  return (
    <header className="toolbar">
      <span className="brand">alucad</span>

      <select
        value={designs.includes(name) ? name : ""}
        onChange={async (e) => {
          const next = e.target.value;
          if (next && (await leave())) await openDesign(next);
        }}
        title="designs/ のデザインを開く"
      >
        <option value="">開く…</option>
        {designs.map((d) => (
          <option key={d} value={d}>
            {d}
          </option>
        ))}
      </select>
      <button onClick={async () => (await leave()) && newDesign()}>新規</button>

      <span className="sep" />
      <input
        className="design-name"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => draft !== name && setName(draft)}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        title="デザイン名（designs/<名前>.json に保存）"
      />
      <span
        className={`dirty ${dirty ? "on" : ""}`}
        title={name === "untitled" ? "名前を付けると自動で保存します" : "保存待ちの変更（自動で保存します）"}
      >
        ●
      </span>

      <span className="sep" />
      <button onClick={undo} disabled={!past.length} title="元に戻す（⌘Z）">
        元に戻す
      </button>
      <button onClick={redo} disabled={!future.length} title="やり直す（⇧⌘Z）">
        やり直す
      </button>

      <span className="sep" />
      <span className="seg" role="group" aria-label="3D 上の操作">
        <button className={tool === "move" ? "on" : ""} onClick={() => setTool("move")} title="矢印で動かす（W）">
          移動
        </button>
        <button className={tool === "rotate" ? "on" : ""} onClick={() => setTool("rotate")} title="輪で回す（E）。90° ずつは R">
          回転
        </button>
      </span>
      <select value={snap} onChange={(e) => setSnap(Number(e.target.value))} title="グリッドスナップ（矢印キーで動かす幅も同じ）">
        {SNAP_CHOICES.map((v) => (
          <option key={v} value={v}>
            {v ? `スナップ ${v}mm` : "スナップなし"}
          </option>
        ))}
      </select>

      <span className="grow" />
      <span className={`check-badge ${errors ? "error" : warnings ? "warning" : "ok"}`} title="加工前チェック">
        {errors ? `エラー ${errors}` : warnings ? `注意 ${warnings}` : "チェックOK"}
      </span>
      <button className="primary" onClick={build} title="保存して DXF / STL / STEP / GLB / 部品表 を書き出す（書き出し先は alucad.local.toml の [out_dirs]、なければ designs/out/）">
        書き出し
      </button>
      <Settings />
    </header>
  );
}

const THEME_CHOICES: [ThemePref, string][] = [
  ["system", "システム"],
  ["light", "ライト"],
  ["dark", "ダーク"],
];

/** ⚙ ボタンと設定の小窓。外をクリックするか Esc で閉じる */
function Settings() {
  const [open, setOpen] = useState(false);
  const pref = useTheme((s) => s.pref);
  const setPref = useTheme((s) => s.setPref);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="settings" ref={ref}>
      <button onClick={() => setOpen(!open)} title="設定" aria-expanded={open}>
        ⚙
      </button>
      {open && (
        <div className="settings-pop" role="dialog" aria-label="設定">
          <h3>テーマ</h3>
          <span className="seg" role="group" aria-label="テーマ">
            {THEME_CHOICES.map(([v, label]) => (
              <button key={v} className={pref === v ? "on" : ""} onClick={() => setPref(v)}>
                {label}
              </button>
            ))}
          </span>
          <p className="hint">「システム」は Mac の外観（ライト／ダーク）に合わせます。</p>
        </div>
      )}
    </div>
  );
}
