// 画面の状態。アセンブリJSONが唯一の正で、Undo/Redo は JSON のスナップショットで行う

import { create } from "zustand";
import { api, ApiError, clearMeshCache } from "./api";
import { merge, sameAssembly, takeTheirs } from "./merge";
import { cleanMm, rotateWorld } from "./transform";
import {
  findNode,
  GROUP,
  groupChildren,
  isGroup,
  joinPath,
  lastId,
  mapChildren,
  mapNode,
  parentPath,
  siblingsOf,
  splitPath,
  ungroupChildren,
  uniqueId,
} from "./tree";
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

/** h が from のどれか（かその中）なら、to で付け替えたパスにする */
function movePath(h: string, from: string[], to: (p: string) => string): string {
  const hit = from.find((p) => h === p || h.startsWith(p + "/"));
  return hit ? to(hit) + h.slice(hit.length) : h;
}

/** 読み込み直しや Undo のあとも、同じ部品（の一番上）がまだあれば選んだままにする */
function keepSelection(asm: AssemblySpec, selected: string | null): string | null {
  return selected && asm.parts.some((p) => p.id === splitPath(selected)[0]) ? selected : null;
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
  selected: string | null; // 選んでいる部品のパス（"rollers/roller_l" のように id を「/」でつなぐ）
  multi: string[]; // Shift/⌘ で一緒に選んだ部品のパス（selected は含まない）
  hidden: string[]; // 画面で隠している部品のパス（書き出しには関係しない。デザインごとにブラウザに覚える）
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
  updatePart: (path: string, patch: Partial<PartSpec>) => void;
  renamePart: (path: string, newId: string) => boolean;
  removePart: (path: string) => void;
  removeSelected: () => void;
  toGroup: (path: string) => Promise<void>;
  group: () => void;
  ungroup: (path: string) => void;
  registerComponent: (path: string) => Promise<void>;
  select: (path: string | null, add?: boolean) => void;
  toggleHidden: (path: string) => void;
  setHiddenPaths: (hidden: string[]) => void;
  setTool: (tool: Tool) => void;
  setSnap: (snap: number) => void;
  nudge: (axis: 0 | 1 | 2, steps: number) => void;
  rotate90: (axis: 0 | 1 | 2, sign?: 1 | -1) => void;
  undo: () => void;
  redo: () => void;

  setIssues: (issues: Issue[]) => void;
  notify: (text: string, kind?: "info" | "error") => void;
}

/**
 * 新規や名前を変えたデザイン（まだファイルと結び付いていない）を保存するとき、同じ名前のファイルがあれば確認する。
 * 一覧は画面を開いたあとに Claude などが足したファイルもあるので、毎回サーバーに聞き直す
 */
async function confirmOverwrite(): Promise<boolean> {
  const { name, stamp } = useStore.getState();
  if (stamp) return true; // 開いたファイルへの保存。外での変更は版の印（409）で守られている
  const { designs } = await api.designs();
  useStore.setState({ designs });
  return !designs.includes(name) || window.confirm(`${name}.json はすでにあります。上書きしますか？`);
}

export const useStore = create<State>((set, get) => ({
  catalog: null,
  designs: [],
  name: "untitled",
  asm: emptyAssembly(),
  selected: null,
  multi: [],
  hidden: [],
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
    // 前回開いていたデザインを開く。なくなっていたら stand（それもなければ空のまま）
    const last = loadPref<string | null>("lastDesign", null);
    const first = last && designs.includes(last) ? last : designs.includes("stand") ? "stand" : null;
    if (first) await get().openDesign(first);
  },

  openDesign: async (name) => {
    try {
      const { assembly, stamp } = await api.load(name);
      set({ asm: assembly, base: assembly, name, stamp, selected: null, multi: [], dirty: false, past: [], future: [], conflict: null });
      set({ hidden: loadPref<string[]>(`hidden.${name}`, []) });
      savePref("lastDesign", name);
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
      multi: [],
      hidden: [],
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
      if (errs.length) get().notify(`${errs[0][0]} を読み込めません: ${errs[0][1]}`, "error");
      else get().notify("parts/・projects/ の部品を読み込み直しました");
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
      selected: keepSelection(assembly, selected),
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
      selected: keepSelection(merged, selected),
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
      selected: keepSelection(next, selected),
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
    try {
      if (!(await confirmOverwrite())) return false;
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
      if (!(await confirmOverwrite())) return;
      const res = await withMerge(() => api.build(name, { ...get().asm, name }, get().stamp));
      if (!res) return;
      const { designs } = await api.designs();
      set({ designs });
      const files = res.files.map((f) => f.split("/").pop()).join(", ");
      const dir = res.files[0]?.split("/").slice(-3, -1).join("/") ?? "";
      get().notify(`${dir}/ に書き出しました: ${files}`);
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
      set({ selected: id, multi: [] });
    } catch (e) {
      get().notify((e as Error).message, "error");
    }
  },

  updatePart: (path, patch) => {
    const { asm } = get();
    if (!findNode(asm.parts, path)) return; // キットの中身は変えられない
    get().commit({ ...asm, parts: mapNode(asm.parts, path, (p) => ({ ...p, ...patch })) });
  },

  renamePart: (path, newId) => {
    const { asm, selected, hidden } = get();
    const id = lastId(path);
    if (!newId || newId === id) return true;
    const sibs = siblingsOf(asm.parts, path);
    if (!sibs || newId.includes("/") || sibs.some((p) => p.id === newId)) return false;
    get().commit({ ...asm, parts: mapNode(asm.parts, path, (p) => ({ ...p, id: newId })) });
    const moved = joinPath(parentPath(path), newId);
    const re = (q: string) => (q === path ? moved : q.startsWith(path + "/") ? moved + q.slice(path.length) : q);
    if (selected) set({ selected: re(selected) });
    get().setHiddenPaths(hidden.map(re));
    return true;
  },

  removePart: (path) => {
    const { asm } = get();
    if (!findNode(asm.parts, path)) return;
    get().commit({ ...asm, parts: mapNode(asm.parts, path, () => null) });
    set({ selected: null, multi: [] });
  },

  /** 選んでいる部品を全部消す（キットの中身は消せないので飛ばす） */
  removeSelected: () => {
    const { asm, selected, multi } = get();
    const paths = [...multi, ...(selected ? [selected] : [])].filter((p) => findNode(asm.parts, p));
    if (!paths.length) return;
    let parts = asm.parts;
    for (const p of paths) parts = mapNode(parts, p, () => null);
    get().commit({ ...asm, parts });
    set({ selected: null, multi: [] });
  },

  /** キット（か登録したグループ部品）を、同じ形のグループにする。中身を動かせるようになる */
  toGroup: async (path) => {
    const { asm } = get();
    const node = findNode(asm.parts, path);
    if (!node) return;
    try {
      const { part } = await api.toGroup(node);
      get().commit({ ...get().asm, parts: mapNode(get().asm.parts, path, () => part) });
      get().notify(`${node.id} をグループにしました（中身を選んで動かせます）`);
    } catch (e) {
      get().notify((e as Error).message, "error");
    }
  },

  /** 選んでいる部品（同じグループの中のもの）を新しいグループにまとめる */
  group: () => {
    const { asm, selected, multi } = get();
    const paths = [...multi, ...(selected ? [selected] : [])];
    if (!paths.length) return;
    const parent = parentPath(paths[0]);
    if (paths.some((p) => parentPath(p) !== parent || !findNode(asm.parts, p))) {
      get().notify("同じグループの中の部品だけをまとめられます（キットの中身はまとめられません）", "error");
      return;
    }
    const ids = new Set(paths.map(lastId));
    let newPath = "";
    const parts = mapChildren(asm.parts, parent, (kids) => {
      const picked = kids.filter((k) => ids.has(k.id));
      const rest = kids.filter((k) => !ids.has(k.id));
      const gid = uniqueId("group1", new Set(rest.map((k) => k.id)));
      newPath = joinPath(parent, gid);
      const g: PartSpec = { id: gid, type: GROUP, params: { children: picked }, pos: [0, 0, 0], rot: [0, 0, 0] };
      const at = kids.findIndex((k) => ids.has(k.id));
      const out = kids.filter((k, i) => !ids.has(k.id) || i === at);
      return out.map((k) => (ids.has(k.id) ? g : k));
    });
    get().commit({ ...asm, parts });
    set({ selected: newPath, multi: [] });
    // 隠していた部品は、グループの中に入っても隠したまま
    get().setHiddenPaths(get().hidden.map((h) => movePath(h, paths, (p) => joinPath(newPath, lastId(p)))));
  },

  /** グループを解いて、中身を1つ上の階層に出す（位置・回転はそのまま見えるように直す） */
  ungroup: (path) => {
    const { asm } = get();
    const g = findNode(asm.parts, path);
    if (!g || !isGroup(g)) return;
    const parent = parentPath(path);
    const taken = new Set((siblingsOf(asm.parts, path) ?? []).filter((k) => k.id !== g.id).map((k) => k.id));
    const renamed = new Map<string, string>();
    const kids = ungroupChildren(g).map((k) => {
      const id = uniqueId(k.id, taken);
      taken.add(id);
      renamed.set(joinPath(path, k.id), joinPath(parent, id));
      return { ...k, id };
    });
    get().commit({ ...asm, parts: mapNode(asm.parts, path, () => kids) });
    get().setHiddenPaths(
      get().hidden.filter((h) => h !== path).map((h) => movePath(h, [...renamed.keys()], (p) => renamed.get(p)!)),
    );
    const paths = kids.map((k) => joinPath(parent, k.id)); // 出した中身をまとめて選んでおく
    set({ selected: paths[0] ?? null, multi: paths.slice(1) });
  },

  /** グループを parts/<名前>.json に書いて、パレットから使える部品にする */
  registerComponent: async (path) => {
    const node = findNode(get().asm.parts, path);
    const kids = node && groupChildren(node);
    if (!node || !kids?.length) {
      get().notify("中身のあるグループを選んでください", "error");
      return;
    }
    const name = window.prompt("部品名（英数字・_・-。parts/<部品名>.json になります）", node.id)?.trim();
    if (!name) return;
    if (!NAME_RE.test(name)) {
      get().notify("部品名に使えるのは英数字・_・- だけです", "error");
      return;
    }
    const label = window.prompt("パレットに出す名前（日本語でよい）", name)?.trim() || name;
    try {
      await api.registerComponent(name, label, kids);
      clearMeshCache();
      set({ catalog: await api.catalog() });
      get().notify(`parts/${name}.json に登録しました。パレットの「グループ」から使えます`);
    } catch (e) {
      get().notify((e as Error).message, "error");
    }
  },

  /** 選ぶ。add なら Shift/⌘ クリックのように、選んでいるものに足す（もう選んでいれば外す） */
  select: (path, add = false) => {
    const { selected, multi } = get();
    if (!add || !path || !selected) return set({ selected: path, multi: [] });
    if (path === selected) {
      const [next, ...rest] = multi;
      return set({ selected: next ?? null, multi: rest });
    }
    if (multi.includes(path)) return set({ multi: multi.filter((p) => p !== path) });
    set({ selected: path, multi: [...multi, selected] });
  },

  toggleHidden: (path) => {
    const { hidden } = get();
    get().setHiddenPaths(hidden.includes(path) ? hidden.filter((p) => p !== path) : [...hidden, path]);
  },

  setHiddenPaths: (hidden) => {
    savePref(`hidden.${get().name}`, hidden);
    set({ hidden });
  },

  setTool: (tool) => set({ tool }),

  setSnap: (snap) => {
    savePref("snap", snap);
    set({ snap });
  },

  /** 選んでいる部品をスナップ間隔ぶん動かす（スナップ無しなら 1mm） */
  nudge: (axis, steps) => {
    const { selected, asm, snap } = get();
    const part = selected ? findNode(asm.parts, selected) : undefined;
    if (!part || !selected) return;
    const pos = [...part.pos] as Vec3;
    pos[axis] = cleanMm(pos[axis] + steps * (snap || 1));
    get().updatePart(selected, { pos });
  },

  /** 選んでいる部品を、ワールドの軸まわりに 90° 回す */
  rotate90: (axis, sign = 1) => {
    const { selected, asm } = get();
    const part = selected ? findNode(asm.parts, selected) : undefined;
    if (!part || !selected) return;
    get().updatePart(selected, { rot: rotateWorld(part.rot, axis, 90 * sign) });
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
      selected: keepSelection(prev, selected),
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
      selected: keepSelection(next, selected),
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
      savePref("lastDesign", useStore.getState().name); // 新しい名前で保存したときも次回はそれを開く
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
