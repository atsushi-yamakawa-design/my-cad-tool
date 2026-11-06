// 構成パネル: 部品を木の形で並べる。グループ・キットは開いて中身を選べる。目のボタンで表示/非表示。
// キットの中身は（パラメータから作られるので）選択と表示切替だけで、動かせない

import { useEffect, useState } from "react";
import { fetchMesh } from "../api";
import { componentDef, useStore } from "../store";
import { groupChildren, joinPath, parentPath } from "../tree";
import type { PartSpec } from "../types";

export function Outliner() {
  const parts = useStore((s) => s.asm.parts);
  const selected = useStore((s) => s.selected);
  const [open, setOpen] = useState<string[]>([]);

  // 3D ビューで中の部品を選んだら、その親を開いて見えるようにする
  useEffect(() => {
    if (!selected) return;
    const ancestors: string[] = [];
    for (let p = parentPath(selected); p; p = parentPath(p)) ancestors.push(p);
    setOpen((prev) => [...new Set([...prev, ...ancestors])]);
  }, [selected]);

  const toggle = (path: string) => setOpen((prev) => (prev.includes(path) ? prev.filter((p) => p !== path) : [...prev, path]));

  if (!parts.length) return <p className="hint">部品がありません。「部品」タブから追加します。</p>;
  return (
    <ul className="tree">
      {parts.map((p) => (
        <TreeRow key={p.id} spec={p} path={p.id} depth={0} locked={false} open={open} toggle={toggle} />
      ))}
    </ul>
  );
}

function TreeRow({
  spec,
  path,
  depth,
  locked,
  open,
  toggle,
}: {
  spec: PartSpec;
  path: string;
  depth: number;
  locked: boolean; // キットの中身（動かせない）
  open: string[];
  toggle: (path: string) => void;
}) {
  const kids = useChildren(spec);
  const isOpen = open.includes(path);
  const on = useStore((s) => s.selected === path || s.multi.includes(path));
  const hidden = useStore((s) => s.hidden.includes(path));
  const { select, toggleHidden } = useStore.getState();
  const def = componentDef(spec.type);
  const isKit = kids !== null && groupChildren(spec) === null;

  return (
    <li>
      <div
        className={`tree-row ${on ? "on" : ""} ${hidden ? "hidden" : ""} ${locked ? "locked" : ""}`}
        style={{ paddingLeft: 4 + depth * 12 }}
        onClick={(e) => select(path, e.shiftKey || e.metaKey || e.ctrlKey)}
        title={locked ? "キットの中身（選択と表示切替だけできます）" : undefined}
      >
        <button
          className="icon caret"
          style={{ visibility: kids?.length ? "visible" : "hidden" }}
          onClick={(e) => {
            e.stopPropagation();
            toggle(path);
          }}
        >
          {isOpen ? "▾" : "▸"}
        </button>
        <span className="tree-id">{spec.id}</span>
        <span className="tree-type">
          {def?.label ?? spec.type}
          {isKit && "（キット）"}
        </span>
        <button
          className="icon eye"
          onClick={(e) => {
            e.stopPropagation();
            toggleHidden(path);
          }}
          title={hidden ? "表示する（H）" : "隠す（H）。書き出しには含まれます"}
        >
          {hidden ? "◌" : "●"}
        </button>
      </div>
      {isOpen && kids && (
        <ul>
          {kids.map((c, i) => (
            <TreeRow
              key={`${c.id}-${i}`}
              spec={c}
              path={joinPath(path, c.id)}
              depth={depth + 1}
              locked={locked || isKit}
              open={open}
              toggle={toggle}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

/** 中身（グループは JSON から、キットはサーバーに聞く）。中身のない部品は null */
function useChildren(spec: PartSpec): PartSpec[] | null {
  const kids = groupChildren(spec);
  const [kitKids, setKitKids] = useState<PartSpec[] | null>(null);
  const epoch = useStore((s) => s.meshEpoch);
  const category = componentDef(spec.type)?.category;
  const maybeKit = kids === null && (category === "kit" || category === "group");
  const key = maybeKit ? epoch + spec.type + JSON.stringify(spec.params) : "";
  useEffect(() => {
    if (!maybeKit) return setKitKids(null);
    let alive = true;
    fetchMesh(spec.type, spec.params)
      .then((d) => alive && setKitKids(d.kit ? d.children : null))
      .catch(() => alive && setKitKids(null));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return kids ?? kitKids;
}
