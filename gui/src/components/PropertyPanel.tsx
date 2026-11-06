// プロパティパネル。入力欄は catalog のパラメータ定義（型・単位・範囲・選択肢）から自動で作る

import { Fragment, useEffect, useState } from "react";
import { api } from "../api";
import { componentDef, useStore } from "../store";
import { findNode, isGroup, resolveNode, splitPath } from "../tree";
import type { ParamDef, Params, PartSpec, Vec3 } from "../types";
import { HolesEditor } from "./HolesEditor";
import { NumberField } from "./NumberField";

export function PropertyPanel() {
  const selected = useStore((s) => s.selected);
  const count = useStore((s) => s.multi.length + (s.selected ? 1 : 0));
  const part = useStore((s) => (s.selected ? findNode(s.asm.parts, s.selected) : undefined));
  if (!selected) {
    return (
      <aside className="panel props">
        <p className="hint">
          部品をクリックすると、ここでパラメータを編集できます。グループの中は、もう一度クリックすると選べます。
          Shift（⌘）クリックで複数選んで ⌘G でグループにまとめます。
        </p>
      </aside>
    );
  }
  if (count > 1) return <MultiProps count={count} />;
  if (!part) return <LockedProps key={selected} path={selected} />;
  return <PartProps key={selected} path={selected} part={part} />;
}

function MultiProps({ count }: { count: number }) {
  const { group, removeSelected, select } = useStore.getState();
  return (
    <aside className="panel props">
      <header className="props-head">
        <div className="props-type">{count} 個の部品を選んでいます</div>
      </header>
      <p className="props-note">同じグループの中の部品なら、まとめて1つのグループにできます。</p>
      <section className="props-actions">
        <button onClick={group} title="⌘G">
          グループにする
        </button>
        <button onClick={() => select(null)}>選択を外す</button>
        <button className="danger" onClick={removeSelected}>
          削除
        </button>
      </section>
    </aside>
  );
}

/** キットの中身。パラメータから作られるので見るだけ（表示/非表示は切り替えられる） */
function LockedProps({ path }: { path: string }) {
  const parts = useStore((s) => s.asm.parts);
  const hidden = useStore((s) => s.hidden.includes(path));
  const { toggleHidden, select } = useStore.getState();
  const [part, setPart] = useState<PartSpec | null>(null);
  useEffect(() => {
    let alive = true;
    resolveNode(parts, path).then((p) => alive && setPart(p ?? null));
    return () => {
      alive = false;
    };
  }, [parts, path]);

  // いちばん内側の「編集できる部品」（キット本体）
  const ids = splitPath(path);
  let owner = ids[0];
  for (let i = 1; i < ids.length && findNode(parts, ids.slice(0, i + 1).join("/")); i++) owner = ids.slice(0, i + 1).join("/");
  const def = part ? componentDef(part.type) : undefined;

  return (
    <aside className="panel props">
      <header className="props-head">
        <div className="props-type">{def?.label ?? part?.type ?? "…"}</div>
        <div className="props-id">{path}</div>
      </header>
      <p className="props-note">
        キット <b>{owner}</b> の中身です。キットのパラメータから作られるので、ここでは動かせません。
        中身を動かしたいときは、キットを選んで「グループに変換」します。
      </p>
      {part && (
        <section>
          <h3>パラメータ</h3>
          <dl className="readonly-params">
            {Object.entries(part.params).map(([k, v]) => (
              <Fragment key={k}>
                <dt title={k}>{def?.params.find((p) => p.name === k)?.label || k}</dt>
                <dd>{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
              </Fragment>
            ))}
            <dt>位置</dt>
            <dd>{part.pos.join(", ")}</dd>
            <dt>回転</dt>
            <dd>{part.rot.join(", ")}</dd>
          </dl>
        </section>
      )}
      <section className="props-actions">
        <button onClick={() => select(owner)}>キットを選ぶ</button>
        <button onClick={() => toggleHidden(path)}>{hidden ? "表示する" : "隠す"}</button>
      </section>
    </aside>
  );
}

function PartProps({ path, part }: { path: string; part: PartSpec }) {
  const def = componentDef(part.type);
  const { updatePart, renamePart, removePart, toGroup, ungroup, registerComponent, notify, rotate90, toggleHidden } =
    useStore.getState();
  const hidden = useStore((s) => s.hidden.includes(path));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [id, setId] = useState(part.id);
  useEffect(() => setId(part.id), [part.id]);
  const group = isGroup(part);
  const kitLike = !group && (def?.category === "kit" || def?.category === "group");

  /** パラメータを1つ変える。サーバーでチェックして、通ったら確定 */
  const setParam = async (name: string, value: unknown) => {
    const params: Params = { ...part.params, [name]: value };
    try {
      const res = await api.validate(part.type, params);
      setErrors((e) => ({ ...e, [name]: "" }));
      updatePart(path, { params: res.params });
    } catch (e) {
      setErrors((err) => ({ ...err, [name]: (e as Error).message }));
    }
  };

  const setVec = (key: "pos" | "rot", i: number, v: number) => {
    const next = [...part[key]] as Vec3;
    next[i] = v;
    updatePart(path, { [key]: next });
  };

  return (
    <aside className="panel props">
      <header className="props-head">
        <div className="props-type">{group ? `グループ（${(part.params.children as unknown[]).length} 個）` : (def?.label ?? part.type)}</div>
        <input
          className="props-id"
          value={id}
          onChange={(e) => setId(e.target.value)}
          onBlur={() => {
            if (!renamePart(path, id.trim())) {
              notify(`id "${id}" は使えません（同じグループの中で重複しているか「/」を含んでいます）`, "error");
              setId(part.id);
            }
          }}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          title={`部品の id（JSON での名前）。パス: ${path}`}
        />
      </header>

      {!group && !!def?.params.length && (
        <section>
          <h3>パラメータ</h3>
          {def.params.map((p) => (
            <ParamField key={p.name} def={p} value={part.params[p.name]} error={errors[p.name]} onChange={(v) => setParam(p.name, v)} />
          ))}
        </section>
      )}
      {group && (
        <p className="props-note">
          中身は 3D ビューでもう一度クリックするか、左の「構成」から選んで動かせます。位置・回転はグループの中での値です。
        </p>
      )}

      <section>
        <h3>配置{path.includes("/") ? "（グループの中）" : ""}</h3>
        <VecRow label="位置" unit="mm" value={part.pos} onChange={(i, v) => setVec("pos", i, v)} />
        <VecRow label="回転" unit="°" value={part.rot} onChange={(i, v) => setVec("rot", i, v)} />
        <div className="field">
          <label>90° 回す</label>
          <div className="rot90">
            {(["X", "Y", "Z"] as const).map((axis, i) => (
              <button
                key={axis}
                className="small"
                onClick={(e) => rotate90(i as 0 | 1 | 2, e.shiftKey ? -1 : 1)}
                title={`${axis} 軸まわりに 90°（Shift で逆回り）${axis === "Z" ? "。R キーでも同じ" : ""}`}
              >
                {axis}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="props-actions">
        {kitLike && (
          <button
            onClick={() => toGroup(path)}
            title="同じ中身のグループにする。中身を1つずつ動かせるようになるが、キットのパラメータでは作り直せなくなる（Undo は可）"
          >
            グループに変換
          </button>
        )}
        {group && (
          <>
            <button onClick={() => ungroup(path)} title="中身を1つ上の階層に出す（⌘⇧G）">
              グループを解除
            </button>
            <button onClick={() => registerComponent(path)} title="parts/<名前>.json に保存して、パレットから使える部品にする">
              コンポーネントとして登録
            </button>
          </>
        )}
        <button onClick={() => toggleHidden(path)} title="画面で隠すだけ（書き出しには含まれます）。H キーでも同じ">
          {hidden ? "表示する" : "隠す"}
        </button>
        <button className="danger" onClick={() => removePart(path)}>
          削除
        </button>
      </section>
    </aside>
  );
}

function ParamField({
  def,
  value,
  error,
  onChange,
}: {
  def: ParamDef;
  value: unknown;
  error?: string;
  onChange: (v: unknown) => void;
}) {
  const materials = useStore((s) => s.catalog?.materials);
  const filaments = useStore((s) => s.catalog?.filaments);
  const label = def.label || def.name;
  const choiceLabel = (c: string) =>
    (def.name.endsWith("mat") && materials?.[c]?.label) || (def.name === "filament" && filaments?.[c]?.label) || c;
  let input: React.ReactNode;

  if (def.type === "float" || def.type === "int") {
    input = (
      <NumberField
        value={Number(value)}
        unit={def.unit}
        min={def.min}
        max={def.max}
        integer={def.type === "int"}
        onCommit={onChange}
      />
    );
  } else if (def.type === "bool") {
    input = <input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />;
  } else if (def.type === "str" && def.choices) {
    input = (
      <select value={String(value)} onChange={(e) => onChange(e.target.value)}>
        {def.choices.map((c) => (
          <option key={String(c)} value={String(c)}>
            {choiceLabel(String(c))}
          </option>
        ))}
      </select>
    );
  } else if (def.type === "str") {
    input = <TextField value={String(value ?? "")} onCommit={onChange} />;
  } else if (def.name === "holes") {
    input = <HolesEditor value={(value as unknown[][]) ?? []} onChange={onChange} />;
  } else {
    input = <JsonField value={value} onCommit={onChange} />;
  }

  const wide = def.type === "list";
  return (
    <div className={`field ${wide ? "field-wide" : ""}`}>
      <label title={def.name}>{label}</label>
      <div className="field-input">{input}</div>
      {error && <div className="field-error">{error}</div>}
    </div>
  );
}

function VecRow({
  label,
  unit,
  value,
  onChange,
}: {
  label: string;
  unit: string;
  value: Vec3;
  onChange: (i: number, v: number) => void;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      <div className="vec">
        {(["X", "Y", "Z"] as const).map((axis, i) => (
          <NumberField key={axis} prefix={axis} value={value[i]} unit={unit} onCommit={(v) => onChange(i, v)} compact />
        ))}
      </div>
    </div>
  );
}

function TextField({ value, onCommit }: { value: string; onCommit: (v: string) => void }) {
  const [text, setText] = useState(value);
  useEffect(() => setText(value), [value]);
  return (
    <input
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => text !== value && onCommit(text)}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
    />
  );
}

/** 刻印・罫書き線などのリストは、4a では JSON をそのまま編集する */
function JsonField({ value, onCommit }: { value: unknown; onCommit: (v: unknown) => void }) {
  const src = JSON.stringify(value);
  const [text, setText] = useState(src);
  const [bad, setBad] = useState(false);
  useEffect(() => setText(src), [src]);
  return (
    <textarea
      className={bad ? "bad" : ""}
      rows={2}
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        try {
          const v = JSON.parse(text);
          setBad(false);
          if (JSON.stringify(v) !== src) onCommit(v);
        } catch {
          setBad(true);
        }
      }}
    />
  );
}
