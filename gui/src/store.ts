// 画面の状態。アセンブリJSONが唯一の正で、Undo/Redo は JSON のスナップショットで行う

import { create } from "zustand";
import { api } from "./api";
import type { AssemblySpec, Catalog, Issue, PartSpec } from "./types";

const HISTORY_LIMIT = 200;
export const NAME_RE = /^[\w-]+$/;

function emptyAssembly(name = "untitled"): AssemblySpec {
  return { version: 1, units: "mm", up: "Z", name, parts: [] };
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

  init: async () => {
    const [catalog, { designs }] = await Promise.all([api.catalog(), api.designs()]);
    set({ catalog, designs });
    if (designs.includes("stand")) await get().openDesign("stand");
  },

  openDesign: async (name) => {
    try {
      const asm = await api.load(name);
      set({ asm, name, selected: null, dirty: false, past: [], future: [] });
    } catch (e) {
      get().notify((e as Error).message, "error");
    }
  },

  newDesign: () =>
    set({ asm: emptyAssembly(), name: "untitled", selected: null, dirty: false, past: [], future: [] }),

  setName: (name) => set({ name, dirty: true }),

  save: async () => {
    const { name, asm } = get();
    if (!NAME_RE.test(name)) {
      get().notify("デザイン名に使えるのは英数字・_・- だけです", "error");
      return false;
    }
    try {
      await api.save(name, { ...asm, name });
      const { designs } = await api.designs();
      set({ dirty: false, designs, asm: { ...asm, name } });
      get().notify(`保存しました: designs/${name}.json`);
      return true;
    } catch (e) {
      get().notify((e as Error).message, "error");
      return false;
    }
  },

  build: async () => {
    const { name, asm } = get();
    if (!NAME_RE.test(name)) {
      get().notify("デザイン名に使えるのは英数字・_・- だけです", "error");
      return;
    }
    if (get().issues.some((i) => i.level === "error")) {
      get().notify("チェックでエラーがあるので書き出しを中止しました", "error");
      return;
    }
    try {
      const res = await api.build(name, { ...asm, name });
      const { designs } = await api.designs();
      set({ dirty: false, designs });
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

export function componentDef(type: string) {
  return useStore.getState().catalog?.components.find((c) => c.name === type);
}
