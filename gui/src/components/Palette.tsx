// 左のパネル。「構成」（デザインの部品の木）と「部品」（パーツパレット＝コンポーネント集）をタブで切り替える。
// パレットは catalog のカテゴリごとに並べ、見出しをクリックで開け閉めする。
// projects/ の形（1つの用途のためのもの）と、空の「グループ」はパレットには出さない

import { useState } from "react";
import { useStore } from "../store";
import { GROUP } from "../tree";
import { Outliner } from "./Outliner";

const CATEGORY_LABEL: Record<string, string> = {
  frame: "フレーム",
  plate: "板（レーザー）",
  print: "3Dプリント",
  hardware: "買う部品",
  kit: "キット",
  group: "グループ（登録したもの）",
};
const ORDER = ["frame", "plate", "print", "hardware", "kit", "group"];
const CLOSED_KEY = "alucad.palette.closed"; // 閉じているカテゴリをブラウザに覚えておく
const TAB_KEY = "alucad.left.tab";

type Tab = "tree" | "palette";

export function LeftPanel() {
  const [tab, setTab] = useState<Tab>(() => {
    try {
      return window.localStorage.getItem(TAB_KEY) === "palette" ? "palette" : "tree";
    } catch {
      return "tree";
    }
  });
  const choose = (t: Tab) => {
    setTab(t);
    try {
      window.localStorage.setItem(TAB_KEY, t);
    } catch {
      /* 覚えられなくても切り替えはできる */
    }
  };
  return (
    <aside className="panel palette">
      <nav className="tabs left-tabs">
        <button className={tab === "tree" ? "on" : ""} onClick={() => choose("tree")}>
          構成
        </button>
        <button className={tab === "palette" ? "on" : ""} onClick={() => choose("palette")}>
          部品
        </button>
      </nav>
      {tab === "tree" ? <Outliner /> : <Palette />}
    </aside>
  );
}

function loadClosed(): string[] {
  try {
    const v = JSON.parse(window.localStorage.getItem(CLOSED_KEY) ?? "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

function Palette() {
  const catalog = useStore((s) => s.catalog);
  const addPart = useStore((s) => s.addPart);
  const [closed, setClosed] = useState<string[]>(loadClosed);
  if (!catalog) return null;

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

  const items = catalog.components.filter((c) => !c.project && c.name !== GROUP);
  const cats = [...new Set(items.map((c) => c.category))].sort(
    (a, b) => (ORDER.indexOf(a) + 99) % 99 - (ORDER.indexOf(b) + 99) % 99,
  );
  return (
    <>
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
    </>
  );
}
