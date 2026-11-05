// パーツパレット（コンポーネント集）。catalog のカテゴリごとに並べ、見出しをクリックで開け閉めする。
// projects/ の形（1つの用途のためのもの）はここには出さない

import { useState } from "react";
import { useStore } from "../store";

const CATEGORY_LABEL: Record<string, string> = {
  frame: "フレーム",
  plate: "板（レーザー）",
  print: "3Dプリント",
  hardware: "買う部品",
  kit: "キット",
};
const ORDER = ["frame", "plate", "print", "hardware", "kit"];
const CLOSED_KEY = "alucad.palette.closed"; // 閉じているカテゴリをブラウザに覚えておく

function loadClosed(): string[] {
  try {
    const v = JSON.parse(window.localStorage.getItem(CLOSED_KEY) ?? "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

export function Palette() {
  const catalog = useStore((s) => s.catalog);
  const addPart = useStore((s) => s.addPart);
  const [closed, setClosed] = useState<string[]>(loadClosed);
  if (!catalog) return <aside className="panel palette" />;

  const toggle = (cat: string) =>
    setClosed((prev) => {
      const next = prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat];
      try {
        window.localStorage.setItem(CLOSED_KEY, JSON.stringify(next));
      } catch {
        /* 覚えられなくても開け閉めはできる */
      }
      return next;
    });

  const items = catalog.components.filter((c) => !c.project);
  const cats = [...new Set(items.map((c) => c.category))].sort(
    (a, b) => (ORDER.indexOf(a) + 99) % 99 - (ORDER.indexOf(b) + 99) % 99,
  );
  return (
    <aside className="panel palette">
      {cats.map((cat) => {
        const open = !closed.includes(cat);
        const list = items.filter((c) => c.category === cat);
        return (
          <section key={cat}>
            <button className="palette-cat" onClick={() => toggle(cat)} aria-expanded={open}>
              <span className="caret">{open ? "▾" : "▸"}</span>
              {CATEGORY_LABEL[cat] ?? cat}
              <span className="count">{list.length}</span>
            </button>
            {open &&
              list.map((c) => (
                <button
                  key={c.name}
                  className="palette-item"
                  onClick={() => addPart(c.name)}
                  title={`${c.name}${c.description ? `\n${c.description}` : ""}${c.user ? "\n（parts/ の自作部品）" : ""}`}
                >
                  {c.label}
                  {c.user && <span className="tag">自作</span>}
                </button>
              ))}
          </section>
        );
      })}
      <p className="hint">クリックで原点に追加。位置は右のパネルで調整します。</p>
    </aside>
  );
}
