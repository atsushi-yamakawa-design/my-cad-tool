// パーツパレット。catalog のカテゴリごとに自動で並べる

import { useStore } from "../store";

const CATEGORY_LABEL: Record<string, string> = { frame: "フレーム", plate: "板", kit: "キット" };
const ORDER = ["frame", "plate", "kit"];

export function Palette() {
  const catalog = useStore((s) => s.catalog);
  const addPart = useStore((s) => s.addPart);
  if (!catalog) return <aside className="panel palette" />;

  const cats = [...new Set(catalog.components.map((c) => c.category))].sort(
    (a, b) => (ORDER.indexOf(a) + 99) % 99 - (ORDER.indexOf(b) + 99) % 99,
  );
  return (
    <aside className="panel palette">
      {cats.map((cat) => (
        <section key={cat}>
          <h3>{CATEGORY_LABEL[cat] ?? cat}</h3>
          {catalog.components
            .filter((c) => c.category === cat)
            .map((c) => (
              <button key={c.name} className="palette-item" onClick={() => addPart(c.name)} title={`${c.name} を原点に追加`}>
                {c.label}
              </button>
            ))}
        </section>
      ))}
      <p className="hint">クリックで原点に追加。位置は右のパネルで調整します。</p>
    </aside>
  );
}
