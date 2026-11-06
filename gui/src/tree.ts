// 部品の木（グループの入れ子）。部品は「パス」で指す: "rollers/roller_l" のように id を「/」でつなぐ。
// グループ（type "group"）の中身は JSON の params.children にあるので編集できる。
// キットの中身はパラメータから自動で作られるので、パスで指せる（選択・表示切替）が編集はできない

import * as THREE from "three";
import { fetchMesh } from "./api";
import { cleanMm, degToEuler, eulerToDeg } from "./transform";
import type { PartSpec } from "./types";

export const GROUP = "group";

export const isGroup = (p: PartSpec) => p.type === GROUP;

/** グループの中身（グループでなければ null） */
export function groupChildren(p: PartSpec): PartSpec[] | null {
  return isGroup(p) ? ((p.params.children as PartSpec[] | undefined) ?? []) : null;
}

export function withChildren(p: PartSpec, children: PartSpec[]): PartSpec {
  return { ...p, params: { ...p.params, children } };
}

export const splitPath = (path: string) => path.split("/");
export const parentPath = (path: string) => splitPath(path).slice(0, -1).join("/");
export const lastId = (path: string) => splitPath(path).slice(-1)[0];
export const joinPath = (parent: string, id: string) => (parent ? `${parent}/${id}` : id);

/** JSON の中にある部品（トップかグループの中）。キットの中身や無いパスは undefined */
export function findNode(parts: PartSpec[], path: string): PartSpec | undefined {
  let list: PartSpec[] | null = parts;
  let node: PartSpec | undefined;
  for (const id of splitPath(path)) {
    node = list?.find((p) => p.id === id);
    if (!node) return undefined;
    list = groupChildren(node);
  }
  return node;
}

/** path の兄弟（同じ親の中身）。親が JSON の中に無ければ null */
export function siblingsOf(parts: PartSpec[], path: string): PartSpec[] | null {
  const parent = parentPath(path);
  if (!parent) return parts;
  const node = findNode(parts, parent);
  return node ? groupChildren(node) : null;
}

/** path の部品を fn の結果に置き換えた新しい木（null なら消す） */
export function mapNode(parts: PartSpec[], path: string, fn: (p: PartSpec) => PartSpec | PartSpec[] | null): PartSpec[] {
  const [id, ...rest] = splitPath(path);
  return parts.flatMap((p) => {
    if (p.id !== id) return [p];
    if (!rest.length) {
      const r = fn(p);
      return r === null ? [] : Array.isArray(r) ? r : [r];
    }
    const kids = groupChildren(p);
    return kids ? [withChildren(p, mapNode(kids, rest.join("/"), fn))] : [p];
  });
}

/** 親（"" ならトップ）の中身を fn で置き換えた新しい木 */
export function mapChildren(parts: PartSpec[], parent: string, fn: (kids: PartSpec[]) => PartSpec[]): PartSpec[] {
  if (!parent) return fn(parts);
  return mapNode(parts, parent, (g) => withChildren(g, fn(groupChildren(g) ?? [])));
}

export function uniqueId(base: string, taken: Set<string>): string {
  if (!taken.has(base)) return base;
  const stem = base.replace(/\d+$/, "");
  let n = 2;
  while (taken.has(`${stem}${n}`)) n++;
  return `${stem}${n}`;
}

/** 中身の木（キットの中身はサーバーに聞く）。グループでもキットでもなければ null */
export async function childrenOf(p: PartSpec): Promise<PartSpec[] | null> {
  const kids = groupChildren(p);
  if (kids) return kids;
  const data = await fetchMesh(p.type, p.params);
  return data.kit ? data.children : null;
}

/** キットの中身も含めて path の部品を探す（読み取り専用の表示用） */
export async function resolveNode(parts: PartSpec[], path: string): Promise<PartSpec | undefined> {
  let list: PartSpec[] | null = parts;
  let node: PartSpec | undefined;
  for (const id of splitPath(path)) {
    node = list?.find((p) => p.id === id);
    if (!node) return undefined;
    list = await childrenOf(node).catch(() => null);
  }
  return node;
}

function matrixOf(p: PartSpec): THREE.Matrix4 {
  const q = new THREE.Quaternion().setFromEuler(degToEuler(p.rot));
  return new THREE.Matrix4().compose(new THREE.Vector3(...p.pos), q, new THREE.Vector3(1, 1, 1));
}

function placeBy(p: PartSpec, m: THREE.Matrix4): PartSpec {
  const pos = new THREE.Vector3();
  const q = new THREE.Quaternion();
  m.decompose(pos, q, new THREE.Vector3());
  const rot = eulerToDeg(new THREE.Euler().setFromQuaternion(q, "XYZ"));
  return { ...p, pos: [cleanMm(pos.x), cleanMm(pos.y), cleanMm(pos.z)], rot };
}

/** グループの中身を、グループの外（親の座標）での位置・回転にして返す */
export function ungroupChildren(g: PartSpec): PartSpec[] {
  if (g.pos.every((v) => v === 0) && g.rot.every((v) => v === 0)) return groupChildren(g) ?? []; // 書き方をそのまま残す
  const m = matrixOf(g);
  return (groupChildren(g) ?? []).map((c) => placeBy(c, m.clone().multiply(matrixOf(c))));
}
