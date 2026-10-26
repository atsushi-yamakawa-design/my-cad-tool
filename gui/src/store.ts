// 画面の状態。アセンブリJSONが唯一の正で、Undo/Redo は JSON のスナップショットで行う

import { create } from "zustand";
import { api, ApiError, clearMeshCache } from "./api";
import { merge, sameAssembly, takeTheirs } from "./merge";
import { cleanMm, rotateWorld } from "./transform";
import type { AssemblySpec, Catalog, Issue, PartSpec, Vec3 } from "./types";

const HISTORY_LIMIT = 200;
export const NAME_RE = /^[\w-]+$/;

function emptyAssembly(name = "untitled"): AssemblySpec {
  return { version: 1, units: "mm", up: "Z", name, parts: [] };
}

export type Tool = "move" | "rotate";
export const SNAP_CHOICES = [0, 1, 5, 10, 20];

/** 画面の好み（スナップ幅など）はブラウザに覚えておく。使えないときは既定値 */
function loadPref<T>(key: string, fallback: T): T {
  try {
    const v = window.localStorage.getItem(`alucad.${key}`);
    return v === null ? fallback : (JSON.parse(v) as T);
  } catch {
    return fallback;
  }
}
function savePref(key: string, value: unknown) {
  try {
    window.localStorage.setItem(`alucad.${key}`, JSON.stringify(value));
  } catch {
    /* 覚えられなくても動作には困らない */
  }
}

function uniqueId(base: string, taken: Set<string>): string {
  if (!taken.has(base)) return base;
  let n = 2;
  while (taken.has(`${base}${n}`)) n++;
  return `${base}${n}`;
}

function nextId(type: string, parts: PartSpec[]): string {
  const taken = new Set(parts.map((p) => p.id));
  let n = 1;
  while (taken.has(`${type}${n}`)) n++;
  return `${type}${n}`;
}

interface State {
  catalog: Catalog | null;
  designs: string[];
  name: string; // デザイン名（designs/<name>.json）
  asm: AssemblySpec;
  selected: string | null;
  dirty: boolean;
  past: AssemblySpec[];
  future: AssemblySpec[];
  issues: Issue[];
  notice: { text: string; kind: "info" | "error" } | null;
  stamp: string | null; // 開いているデザインファイルの版の印（読み込み・保存したとき）
  base: AssemblySpec | null; // stamp の時点のファイルの内容（外部の変更とのマージの基準）
  partsStamp: string | null; // parts/ フォルダの版の印
  meshEpoch: number; // 形状を取り直すたびに増やす
  conflict: { ids: string[]; theirs: AssemblySpec } | null; // 外部とこちらの両方が変えた部品
  tool: Tool; // 3D 上の矢印で「移動」するか「回転」するか
  snap: number; // グリッドスナップの間隔（mm、0 で無し）

  poll: () => Promise<void>;
  reloadFromDisk: () => Promise<void>;
  mergeFromDisk: () => Promise<boolean>;
  keepMine: () => void;
  takeTheirs: () => void;

  init: () => Promise<void>;
  openDesign: (name: string) => Promise<void>;
  newDesign: () => void;
  setName: (name: string) => void;
  save: () => Promise<boolean>;
  build: () => Promise<void>;

  commit: (asm: AssemblySpec) => void;
  addPart: (type: string) => Promise<void>;
  updatePart: (id: string, patch: Partial<PartSpec>) => void;
  renamePart: (id: string, newId: string) => boolean;
  removePart: (id: string) => void;
  explode: (id: string) => Promise<void>;
  select: (id: string | null) => void;
  setTool: (tool: Tool) => void;
  setSnap: (snap: number) => void;
  nudge: (axis: 0 | 1 | 2, steps: number) => void;
  rotate90: (axis: 0 | 1 | 2, sign?: 1 | -1) => void;
  undo: () => void;
  redo: () => void;

  setIssues: (issues: Issue[]) => void;
  notify: (text: string, kind?: "info" | "error") => void;
}

export const useStore = create<State>((set, get) => ({
  catalog: null,
  designs: [],
  name: "untitled",
  asm: emptyAssembly(),
  selected: null,
  dirty: false,
  past: [],
  future: [],
  issues: [],
  notice: null,
  stamp: null,
  base: null,
  partsStamp: null,
  meshEpoch: 0,
  conflict: null,
  tool: "move",
  snap: loadPref("snap", 5),

  init: async () => {
    const [catalog, { designs }] = await Promise.all([api.catalog(), api.designs()]);
    set({ catalog, designs });
    if (designs.includes("stand")) await get().openDesign("stand");
  },

  openDesign: async (name) => {
    try {
      const { assembly, stamp } = await api.load(name);
      set({ asm: assembly, base: assembly, name, stamp, selected: null, dirty: false, past: [], future: [], conflict: null });
    } catch (e) {
      get().notify((e as Error).message, "error");
    }
  },

  newDesign: () =>
    set({
      asm: emptyAssembly(),
      name: "untitled",
      stamp: null,
      base: null,
      selected: null,
      dirty: false,
      past: [],
      future: [],
      conflict: null,
    }),

  /** 1秒ごとに呼ぶ。デザインファイルや parts/ が外で変わっていたら追従する */
  poll: async () => {
    const s = get();
    const w = await api.watch(s.name);

    if (s.partsStamp !== null && w.parts !== s.partsStamp) {
      clearMeshCache();
      const catalog = await api.catalog();
      set({ catalog, meshEpoch: get().meshEpoch + 1 });
      const errs = Object.entries(w.parts_errors);
      if (errs.length) get().notify(`parts/${errs[0][0]} を読み込めません: ${errs[0][1]}`, "error");
      else get().notify("parts/ の部品を読み込み直しました");
    }
    set({ partsStamp: w.parts });

    // 開いているデザインのファイルが外で書き換わった
    if (s.stamp && w.design && w.design !== s.stamp && !s.conflict) {
      if (s.dirty) await get().mergeFromDisk();
      else {
        await get().reloadFromDisk();
        get().notify(`${s.name}.json が外部で変更されたので読み込み直しました`);
      }
    }
  },

  reloadFromDisk: async () => {
    const { name, selected } = get();
    const { assembly, stamp } = await api.load(name);
    set({
      asm: assembly,
      base: assembly,
      stamp,
      dirty: false,
      conflict: null,
      past: [...get().past, get().asm].slice(-HISTORY_LIMIT), // 読み込み直しも Undo で戻せる
      future: [],
      selected: assembly.parts.some((p) => p.id === selected) ? selected : null,
    });
  },

  /** 外部の変更をこちらの未保存の変更と部品ごとに合わせる。衝突がなければ true */
  mergeFromDisk: async () => {
    const { name } = get();
    const { assembly: theirs, stamp } = await api.load(name);
    const { asm, base, selected, past } = get(); // 読み込み中に画面で変えた分も含める
    const { merged, conflicts, taken } = merge(base ?? { ...theirs, parts: [] }, asm, theirs);
    set({
      asm: merged,
      base: theirs,
      stamp,
      dirty: !sameAssembly(merged, theirs),
      conflict: conflicts.length ? { ids: conflicts, theirs } : null,
      past: sameAssembly(merged, asm) ? past : [...past, asm].slice(-HISTORY_LIMIT), // マージも Undo で戻せる
      future: [],
      selected: merged.parts.some((p) => p.id === selected) ? selected : null,
    });
    if (!conflicts.length) {
      get().notify(`${name}.json の外部の変更（${taken}個の部品）を、こちらの未保存の変更と合わせました`);
    }
    return !conflicts.length;
  },

  /** 衝突した部品はこちらの内容を残す（次の保存で書き込む） */
  keepMine: () => set({ conflict: null, dirty: true }),

  /** 衝突した部品を外部の内容にする */
  takeTheirs: () => {
    const { conflict, asm, past, selected } = get();
    if (!conflict) return;
    const next = takeTheirs(asm, conflict.theirs, conflict.ids);
    set({
      asm: next,
      past: [...past, asm].slice(-HISTORY_LIMIT),
      future: [],
      conflict: null,
      dirty: !sameAssembly(next, conflict.theirs),
      selected: next.parts.some((p) => p.id === selected) ? selected : null,
    });
  },

  // 名前を変えると別のファイルになるので、版の印はリセット
  setName: (name) => set({ name, dirty: true, stamp: null, base: null, conflict: null }),

  save: async () => {
    const { name } = get();
    if (!NAME_RE.test(name)) {
      get().notify("デザイン名に使えるのは英数字・_・- だけです", "error");
      return false;
    }
    if (!get().stamp && get().designs.includes(name) && !window.confirm(`${name}.json はすでにあります。上書きしますか？`)) {
      return false;
    }
    try {
      const res = await withMerge(() => api.save(name, { ...get().asm, name }, get().stamp));
      if (!res) return false;
      const { designs } = await api.designs();
      set({ designs });
      get().notify(`保存しました: designs/${name}.json`);
      return true;
    } catch (e) {
      get().notify((e as Error).message, "error");
      return false;
    }
  },

  build: async () => {
    const { name } = get();
    if (!NAME_RE.test(name)) {
      get().notify("デザイン名に使えるのは英数字・_・- だけです", "error");
      return;
    }
    if (get().issues.some((i) => i.level === "error")) {
      get().notify("チェックでエラーがあるので書き出しを中止しました", "error");
      return;
    }
    try {
      const res = await withMerge(() => api.build(name, { ...get().asm, name }, get().stamp));
      if (!res) return;
      const { designs } = await api.designs();
      set({ designs });
      const files = res.files.map((f) => f.split("/").pop()).join(", ");
      get().notify(`designs/out/ に書き出しました: ${files}`);
    } catch (e) {
      get().notify((e as Error).message, "error");
    }
  },

  commit: (asm) => {
    const { past, asm: prev } = get();
    set({ asm, past: [...past, prev].slice(-HISTORY_LIMIT), future: [], dirty: true });
  },

  addPart: async (type) => {
    try {
      const { params } = await api.validate(type, {});
      const { asm } = get();
      const id = nextId(type, asm.parts);
      const part: PartSpec = { id, type, params, pos: [0, 0, 0], rot: [0, 0, 0] };
      get().commit({ ...asm, parts: [...asm.parts, part] });
      set({ selected: id });
    } catch (e) {
      get().notify((e as Error).message, "error");
    }
  },

  updatePart: (id, patch) => {
    const { asm } = get();
    get().commit({ ...asm, parts: asm.parts.map((p) => (p.id === id ? { ...p, ...patch } : p)) });
  },

  renamePart: (id, newId) => {
    const { asm, selected } = get();
    if (!newId || newId === id) return true;
    if (newId.includes("/") || asm.parts.some((p) => p.id === newId)) return false;
    get().commit({ ...asm, parts: asm.parts.map((p) => (p.id === id ? { ...p, id: newId } : p)) });
    if (selected === id) set({ selected: newId });
    return true;
  },

  removePart: (id) => {
    const { asm } = get();
    get().commit({ ...asm, parts: asm.parts.filter((p) => p.id !== id) });
    set({ selected: null });
  },

  explode: async (id) => {
    const { asm } = get();
    const kit = asm.parts.find((p) => p.id === id);
    if (!kit) return;
    try {
      const { parts } = await api.explode(kit);
      const taken = new Set(asm.parts.filter((p) => p.id !== id).map((p) => p.id));
      const fresh = parts.map((p) => {
        const pid = uniqueId(p.id, taken);
        taken.add(pid);
        return { ...p, id: pid };
      });
      get().commit({ ...asm, parts: [...asm.parts.filter((p) => p.id !== id), ...fresh] });
      set({ selected: null });
      get().notify(`${id} を ${fresh.length} 個の部品に分解しました`);
    } catch (e) {
      get().notify((e as Error).message, "error");
    }
  },

  select: (id) => set({ selected: id }),

  setTool: (tool) => set({ tool }),

  setSnap: (snap) => {
    savePref("snap", snap);
    set({ snap });
  },

  /** 選んでいる部品をスナップ間隔ぶん動かす（スナップ無しなら 1mm） */
  nudge: (axis, steps) => {
    const { selected, asm, snap } = get();
    const part = asm.parts.find((p) => p.id === selected);
    if (!part) return;
    const pos = [...part.pos] as Vec3;
    pos[axis] = cleanMm(pos[axis] + steps * (snap || 1));
    get().updatePart(part.id, { pos });
  },

  /** 選んでいる部品を、ワールドの軸まわりに 90° 回す */
  rotate90: (axis, sign = 1) => {
    const { selected, asm } = get();
    const part = asm.parts.find((p) => p.id === selected);
    if (!part) return;
    get().updatePart(part.id, { rot: rotateWorld(part.rot, axis, 90 * sign) });
  },

  undo: () => {
    const { past, future, asm, selected } = get();
    if (!past.length) return;
    const prev = past[past.length - 1];
    set({
      asm: prev,
      past: past.slice(0, -1),
      future: [asm, ...future],
      dirty: true,
      selected: prev.parts.some((p) => p.id === selected) ? selected : null,
    });
  },

  redo: () => {
    const { past, future, asm, selected } = get();
    if (!future.length) return;
    const next = future[0];
    set({
      asm: next,
      past: [...past, asm],
      future: future.slice(1),
      dirty: true,
      selected: next.parts.some((p) => p.id === selected) ? selected : null,
    });
  },

  setIssues: (issues) => set({ issues }),

  notify: (text, kind = "info") => {
    set({ notice: { text, kind } });
    window.setTimeout(() => {
      if (get().notice?.text === text) set({ notice: null });
    }, kind === "error" ? 8000 : 4000);
  },
}));

/**
 * 保存（か書き出し）をする。外部で変わっていて止められたら（409）、マージしてからもう一度だけ試す。
 * 衝突が残ったら保存せずに null（画面に衝突の確認が出る）
 */
async function withMerge<T extends { stamp: string; assembly: AssemblySpec }>(send: () => Promise<T>): Promise<T | null> {
  for (let attempt = 0; ; attempt++) {
    const sent = useStore.getState().asm;
    try {
      const res = await send();
      // 保存した内容（サーバーで整えたもの）を基準にする。保存中に画面で変えていたらそちらを残す
      const now = useStore.getState().asm;
      useStore.setState({
        stamp: res.stamp,
        base: res.assembly,
        asm: now === sent ? res.assembly : { ...now, name: res.assembly.name },
        dirty: now !== sent,
      });
      return res;
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 409) || attempt > 0) throw e;
      if (!(await useStore.getState().mergeFromDisk())) return null;
    }
  }
}

export function componentDef(type: string) {
  return useStore.getState().catalog?.components.find((c) => c.name === type);
}
