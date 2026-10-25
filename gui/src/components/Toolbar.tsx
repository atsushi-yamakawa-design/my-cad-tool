// 上のツールバー: デザインの切り替え・保存・Undo/Redo・書き出し・チェック結果

import { useEffect, useState } from "react";
import { useStore } from "../store";

export function Toolbar() {
  const { designs, name, dirty, past, future, issues } = useStore();
  const { openDesign, newDesign, setName, save, build, undo, redo } = useStore.getState();
  const [draft, setDraft] = useState(name);
  useEffect(() => setDraft(name), [name]);

  const confirmDiscard = () => !dirty || window.confirm("保存していない変更があります。破棄しますか？");
  const errors = issues.filter((i) => i.level === "error").length;
  const warnings = issues.length - errors;

  return (
    <header className="toolbar">
      <span className="brand">alucad</span>

      <select
        value={designs.includes(name) ? name : ""}
        onChange={(e) => e.target.value && confirmDiscard() && openDesign(e.target.value)}
        title="designs/ のデザインを開く"
      >
        <option value="">開く…</option>
        {designs.map((d) => (
          <option key={d} value={d}>
            {d}
          </option>
        ))}
      </select>
      <button onClick={() => confirmDiscard() && newDesign()}>新規</button>

      <span className="sep" />
      <input
        className="design-name"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => draft !== name && setName(draft)}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        title="デザイン名（designs/<名前>.json に保存）"
      />
      <span className={`dirty ${dirty ? "on" : ""}`} title="未保存の変更">
        ●
      </span>
      <button onClick={save} title="保存（⌘S）">
        保存
      </button>

      <span className="sep" />
      <button onClick={undo} disabled={!past.length} title="元に戻す（⌘Z）">
        元に戻す
      </button>
      <button onClick={redo} disabled={!future.length} title="やり直す（⇧⌘Z）">
        やり直す
      </button>

      <span className="grow" />
      <span className={`check-badge ${errors ? "error" : warnings ? "warning" : "ok"}`} title="加工前チェック">
        {errors ? `エラー ${errors}` : warnings ? `注意 ${warnings}` : "チェックOK"}
      </span>
      <button className="primary" onClick={build} title="保存して DXF / STEP / GLB / 部品表 を designs/out/ に書き出す">
        書き出し
      </button>
    </header>
  );
}
