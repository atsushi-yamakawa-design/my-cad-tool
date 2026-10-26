// 外部（Claude Code など）の変更と、画面の未保存の変更を部品ごとに合わせる（3方向マージ）
//
//   base   … 最後にファイルと一致していた内容（読み込み・保存したとき）
//   mine   … 画面の今の内容
//   theirs … 外で書き換わったファイルの内容
//
// 部品の id ごとに見て、片方だけが変えた部品はその変更を取り込む。両方が同じ部品を別々に変えたときだけ「衝突」

import type { AssemblySpec, PartSpec } from "./types";

export interface MergeResult {
  merged: AssemblySpec; // 衝突した部品は画面の内容のまま
  conflicts: string[]; // 両方が変えた部品の id
  taken: number; // 外部の変更を取り込んだ部品の数（追加・変更・削除）
}

/** 数値の誤差やキーの順番に左右されない比較用の文字列 */
function key(v: unknown): string {
  return JSON.stringify(v, (_k, x) => {
    if (typeof x === "number") return Math.round(x * 1e6) / 1e6 + 0; // + 0 で -0 を 0 に
    if (x && typeof x === "object" && !Array.isArray(x)) {
      return Object.fromEntries(Object.entries(x).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)));
    }
    return x;
  });
}

export function samePart(a: PartSpec | undefined, b: PartSpec | undefined): boolean {
  if (!a || !b) return a === b;
  return key(a) === key(b);
}

export function sameAssembly(a: AssemblySpec, b: AssemblySpec): boolean {
  return a.parts.length === b.parts.length && a.parts.every((p, i) => samePart(p, b.parts[i]));
}

export function merge(base: AssemblySpec, mine: AssemblySpec, theirs: AssemblySpec): MergeResult {
  const byId = (a: AssemblySpec) => new Map(a.parts.map((p) => [p.id, p]));
  const b = byId(base);
  const m = byId(mine);
  const t = byId(theirs);

  const conflicts: string[] = [];
  let taken = 0;
  const pick = (id: string): PartSpec | undefined => {
    const bp = b.get(id);
    const mp = m.get(id);
    const tp = t.get(id);
    if (samePart(mp, tp)) return mp; // 同じ変更（か、どちらも変えていない）
    if (samePart(mp, bp)) {
      taken++;
      return tp; // 外だけが変えた（削除なら undefined）
    }
    if (samePart(tp, bp)) return mp; // 画面だけが変えた
    conflicts.push(id);
    return mp;
  };

  // 並び順は画面の順。外で増えた部品は、外のファイルで直前にある部品の後ろに入れる
  const parts: PartSpec[] = [];
  for (const p of mine.parts) {
    const q = pick(p.id);
    if (q) parts.push(q);
  }
  theirs.parts.forEach((p, i) => {
    if (m.has(p.id)) return;
    const q = pick(p.id);
    if (!q) return;
    const prevId = theirs.parts
      .slice(0, i)
      .reverse()
      .find((x) => parts.some((y) => y.id === x.id))?.id;
    const at = prevId ? parts.findIndex((y) => y.id === prevId) + 1 : 0;
    parts.splice(at, 0, q);
  });

  return { merged: { ...mine, parts }, conflicts, taken };
}

/** 衝突した部品を外部の内容にそろえる（外で消されていれば消す） */
export function takeTheirs(asm: AssemblySpec, theirs: AssemblySpec, ids: string[]): AssemblySpec {
  const t = new Map(theirs.parts.map((p) => [p.id, p]));
  const parts: PartSpec[] = [];
  for (const p of asm.parts) {
    if (!ids.includes(p.id)) parts.push(p);
    else if (t.has(p.id)) parts.push(t.get(p.id)!);
  }
  // 画面で消した部品が外で変えられていた場合は、外の内容で戻す
  for (const id of ids) {
    if (!parts.some((p) => p.id === id) && t.has(id)) parts.push(t.get(id)!);
  }
  return { ...asm, parts };
}
