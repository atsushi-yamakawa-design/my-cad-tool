// Python 側（alucad）と同じ形のデータ

export type Vec3 = [number, number, number];
export type Params = Record<string, unknown>;

export interface PartSpec {
  id: string;
  type: string;
  params: Params;
  pos: Vec3;
  rot: Vec3; // XYZ オイラー角（度）
}

export interface AssemblySpec {
  version: number;
  units: string;
  up: string;
  name: string;
  parts: PartSpec[];
}

export interface ParamDef {
  name: string;
  type: "float" | "int" | "str" | "bool" | "list";
  default: unknown;
  unit: string;
  min: number | null;
  max: number | null;
  choices: unknown[] | null;
  label: string;
}

export interface ComponentDef {
  name: string;
  label: string;
  category: "frame" | "plate" | "print" | "kit" | string;
  description: string;
  user: boolean; // parts/ フォルダの自作部品
  params: ParamDef[];
}

export interface MaterialDef {
  label: string;
  t: number;
  kerf: number;
  color: string;
}

export interface Catalog {
  components: ComponentDef[];
  materials: Record<string, MaterialDef>;
  filaments: Record<string, { label: string; color: string }>;
  bed: [number, number];
}

export type MeshData =
  | { kit: false; category: string; mat: string | null; color: string; vertices: number[]; indices: number[] }
  | { kit: true; children: PartSpec[] };

export interface Issue {
  level: "error" | "warning";
  part: string;
  message: string;
}

export interface Bom {
  name: string;
  frames: { profile: string; length: number; qty: number }[];
  plates: Record<string, { name: string; w: number; h: number }[]>;
  sheets: Record<string, number>;
  bolts: { size: string; length: number; qty: number }[];
  joints: { kind: string; size: string; profile: string; qty: number }[];
  prints: { label: string; filament: string; size: [number, number, number]; qty: number }[];
}

export interface WatchState {
  design: string | null; // デザインファイルの版の印
  parts: string; // parts/ フォルダの版の印
  parts_errors: Record<string, string>;
}
