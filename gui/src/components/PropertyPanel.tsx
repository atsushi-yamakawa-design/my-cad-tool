// プロパティパネル。入力欄は catalog のパラメータ定義（型・単位・範囲・選択肢）から自動で作る

import { useEffect, useState } from "react";
import { api } from "../api";
import { componentDef, useStore } from "../store";
import type { ParamDef, Params, PartSpec, Vec3 } from "../types";
import { HolesEditor } from "./HolesEditor";
import { NumberField } from "./NumberField";

export function PropertyPanel() {
  const part = useStore((s) => s.asm.parts.find((p) => p.id === s.selected));
  if (!part) {
    return (
      <aside className="panel props">
        <p className="hint">部品をクリックすると、ここでパラメータを編集できます。</p>
      </aside>
    );
  }
  return <PartProps key={part.id} part={part} />;
}

function PartProps({ part }: { part: PartSpec }) {
  const def = componentDef(part.type);
  const { updatePart, renamePart, removePart, explode, notify } = useStore.getState();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [id, setId] = useState(part.id);
  useEffect(() => setId(part.id), [part.id]);

  /** パラメータを1つ変える。サーバーでチェックして、通ったら確定 */
  const setParam = async (name: string, value: unknown) => {
    const params: Params = { ...part.params, [name]: value };
    try {
      const res = await api.validate(part.type, params);
      setErrors((e) => ({ ...e, [name]: "" }));
      updatePart(part.id, { params: res.params });
    } catch (e) {
      setErrors((err) => ({ ...err, [name]: (e as Error).message }));
    }
  };

  const setVec = (key: "pos" | "rot", i: number, v: number) => {
    const next = [...part[key]] as Vec3;
    next[i] = v;
    updatePart(part.id, { [key]: next });
  };

  return (
    <aside className="panel props">
      <header className="props-head">
        <div className="props-type">{def?.label ?? part.type}</div>
        <input
          className="props-id"
          value={id}
          onChange={(e) => setId(e.target.value)}
          onBlur={() => {
            if (!renamePart(part.id, id.trim())) {
              notify(`id "${id}" は使えません（重複か「/」を含んでいます）`, "error");
              setId(part.id);
            }
          }}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          title="部品の id（JSON での名前）"
        />
      </header>

      <section>
        <h3>パラメータ</h3>
        {def?.params.map((p) => (
          <ParamField key={p.name} def={p} value={part.params[p.name]} error={errors[p.name]} onChange={(v) => setParam(p.name, v)} />
        ))}
      </section>

      <section>
        <h3>配置</h3>
        <VecRow label="位置" unit="mm" value={part.pos} onChange={(i, v) => setVec("pos", i, v)} />
        <VecRow label="回転" unit="°" value={part.rot} onChange={(i, v) => setVec("rot", i, v)} />
      </section>

      <section className="props-actions">
        {def?.category === "kit" && (
          <button onClick={() => explode(part.id)} title="中身をばらばらの部品にする（元には戻せません。Undo は可）">
            キットを分解
          </button>
        )}
        <button className="danger" onClick={() => removePart(part.id)}>
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
