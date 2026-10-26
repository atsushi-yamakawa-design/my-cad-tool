// 位置・回転の計算。回転は JSON と同じ XYZ オイラー角（度）で受け渡す

import * as THREE from "three";
import type { Vec3 } from "./types";

export const DEG = Math.PI / 180;

/** 度の値を見やすく丸める（89.99999 → 90、-0 → 0、-180 → 180） */
export function cleanDeg(v: number): number {
  let d = Math.round(v * 1e4) / 1e4;
  if (Math.abs(d - Math.round(d)) < 1e-3) d = Math.round(d);
  if (d <= -180) d += 360;
  if (d > 180) d -= 360;
  return d === 0 ? 0 : d;
}

export function cleanMm(v: number): number {
  const d = Math.round(v * 1e4) / 1e4;
  return d === 0 ? 0 : d;
}

export function eulerToDeg(e: THREE.Euler): Vec3 {
  const r = new THREE.Euler().setFromQuaternion(new THREE.Quaternion().setFromEuler(e), "XYZ");
  return [cleanDeg(r.x / DEG), cleanDeg(r.y / DEG), cleanDeg(r.z / DEG)];
}

export function degToEuler(rot: Vec3): THREE.Euler {
  return new THREE.Euler(rot[0] * DEG, rot[1] * DEG, rot[2] * DEG, "XYZ");
}

/** 今の向きから、ワールドの X/Y/Z 軸まわりに deg 度だけ回した向き */
export function rotateWorld(rot: Vec3, axis: 0 | 1 | 2, deg: number): Vec3 {
  const ax = new THREE.Vector3().setComponent(axis, 1);
  const q = new THREE.Quaternion().setFromAxisAngle(ax, deg * DEG).multiply(new THREE.Quaternion().setFromEuler(degToEuler(rot)));
  return eulerToDeg(new THREE.Euler().setFromQuaternion(q, "XYZ"));
}
