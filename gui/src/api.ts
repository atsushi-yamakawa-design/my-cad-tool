// Python サーバーとのやりとり。エラーはサーバーの日本語メッセージをそのまま投げる

import type { AssemblySpec, Bom, Catalog, Issue, MeshData, Params, PartSpec } from "./types";

async function call<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: unknown }).detail;
    throw new Error(typeof detail === "string" ? detail : `サーバーエラー (${res.status})`);
  }
  return data as T;
}

export const api = {
  catalog: () => call<Catalog>("GET", "/api/catalog"),
  validate: (type: string, params: Params) =>
    call<{ params: Params }>("POST", "/api/validate", { type, params }),
  mesh: (type: string, params: Params) => call<MeshData>("POST", "/api/mesh", { type, params }),
  explode: (part: PartSpec) => call<{ parts: PartSpec[] }>("POST", "/api/explode", part),
  check: (asm: AssemblySpec) => call<{ issues: Issue[] }>("POST", "/api/check", asm),
  bom: (asm: AssemblySpec) => call<Bom & { markdown: string }>("POST", "/api/bom", asm),
  designs: () => call<{ designs: string[]; dir: string }>("GET", "/api/designs"),
  load: (name: string) => call<AssemblySpec>("GET", `/api/designs/${encodeURIComponent(name)}`),
  save: (name: string, asm: AssemblySpec) =>
    call<{ saved: string }>("PUT", `/api/designs/${encodeURIComponent(name)}`, asm),
  build: (name: string, asm: AssemblySpec) =>
    call<{ files: string[]; warnings: string[] }>(
      "POST",
      `/api/designs/${encodeURIComponent(name)}/build`,
      asm,
    ),
};

// 形状は「種類＋パラメータ」ごとに1回だけ取りに行く（移動・回転では取りに行かない）
const meshCache = new Map<string, Promise<MeshData>>();

export function meshKey(type: string, params: Params): string {
  return type + JSON.stringify(params);
}

export function fetchMesh(type: string, params: Params): Promise<MeshData> {
  const key = meshKey(type, params);
  let p = meshCache.get(key);
  if (!p) {
    p = api.mesh(type, params);
    p.catch(() => meshCache.delete(key));
    meshCache.set(key, p);
  }
  return p;
}
