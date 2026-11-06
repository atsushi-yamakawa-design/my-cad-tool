// 3D ビュー。部品は「Python が作ったメッシュ（ローカル座標）」を pos / rot で置くだけ。
// 移動・回転はブラウザの中だけで済ませ、手を離したときに1回だけ JSON に書く（Undo 1回分）

import { Edges, GizmoHelper, GizmoViewport, Grid, OrbitControls, TransformControls } from "@react-three/drei";
import { Canvas, type ThreeEvent } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { fetchMesh } from "../api";
import { useStore } from "../store";
import { useTheme, VIEW_COLORS } from "../theme";
import { cleanMm, DEG, degToEuler, eulerToDeg } from "../transform";
import { findNode, groupChildren, joinPath, splitPath } from "../tree";
import type { MeshData, Params, PartSpec, Vec3 } from "../types";

const ROTATE_SNAP = 15; // 3D 上で回すときの刻み（度）。90° ちょうどは R キーやボタンで
const FRAME_COLOR = "#b9bec7";
const SELECT_COLOR = "#2f7cf6";

export function Viewport() {
  const parts = useStore((s) => s.asm.parts);
  const selected = useStore((s) => s.selected);
  const single = useStore((s) => s.multi.length === 0);
  // 矢印を出すのは、1つだけ選んでいて、それが JSON の中にある（キットの中身でない）とき
  const editable = useStore((s) => (s.selected ? !!findNode(s.asm.parts, s.selected) : false));
  const select = useStore((s) => s.select);
  const snap = useStore((s) => s.snap);
  const colors = VIEW_COLORS[useTheme((s) => s.theme)];
  // 選んでいる部品の group。矢印（TransformControls）はこれを直接動かす
  const [target, setTarget] = useState<THREE.Object3D | null>(null);
  // 矢印をつかんでいる間と離した直後は、空クリック扱いで選択を外さない（離したときにも click が飛んでくるため）
  const gizmoHot = useRef(false);
  const gizmoUpAt = useRef(0);
  const missed = () => {
    if (!gizmoHot.current && performance.now() - gizmoUpAt.current > 300) select(null);
  };

  return (
    <Canvas
      camera={{ position: [450, -600, 420], up: [0, 0, 1], fov: 35, near: 1, far: 20000 }}
      onPointerMissed={missed}
    >
      <color attach="background" args={[colors.bg]} />
      <hemisphereLight args={["#ffffff", colors.ground, 1.2]} />
      <directionalLight position={[400, -500, 900]} intensity={1.6} />
      <directionalLight position={[-500, 300, 200]} intensity={0.5} />
      {/* drei の Grid は XZ 平面なので、Z が上の座標系に合わせて寝かせる */}
      <Grid
        rotation={[Math.PI / 2, 0, 0]}
        cellSize={snap >= 5 ? snap : 10}
        sectionSize={100}
        cellColor={colors.cell}
        sectionColor={colors.section}
        infiniteGrid
        fadeDistance={4000}
      />
      {parts.map((p) => (
        <PartNode key={p.id} spec={p} path={p.id} setTarget={setTarget} />
      ))}
      {target && selected && editable && single && <Gizmo target={target} id={selected} hot={gizmoHot} upAt={gizmoUpAt} />}
      <OrbitControls makeDefault />
      <GizmoHelper alignment="bottom-right" margin={[64, 64]}>
        <GizmoViewport labelColor="white" axisHeadScale={0.9} />
      </GizmoHelper>
    </Canvas>
  );
}

/** 移動・回転の矢印。ドラッグ中は three.js の物体だけを動かし、離したら位置と回転を JSON に確定する */
function Gizmo({
  target,
  id,
  hot,
  upAt,
}: {
  target: THREE.Object3D;
  id: string;
  hot: React.RefObject<boolean>;
  upAt: React.RefObject<number>;
}) {
  const tool = useStore((s) => s.tool);
  const snap = useStore((s) => s.snap);
  const updatePart = useStore((s) => s.updatePart);

  const onMouseUp = () => {
    hot.current = false;
    upAt.current = performance.now();
    const part = findNode(useStore.getState().asm.parts, id);
    if (!part) return;
    const pos = target.position.toArray().map(cleanMm) as Vec3;
    // 向きが変わっていなければ、JSON の書き方（同じ向きでも角度の組は何通りかある）をそのまま残す
    const turned = target.quaternion.angleTo(new THREE.Quaternion().setFromEuler(degToEuler(part.rot))) > 1e-6;
    const rot = turned ? eulerToDeg(target.rotation) : part.rot;
    const moved = pos.some((v, i) => Math.abs(v - part.pos[i]) > 1e-6);
    if (moved || turned) updatePart(id, { pos, rot });
  };

  return (
    <TransformControls
      object={target}
      mode={tool === "move" ? "translate" : "rotate"}
      space="world"
      translationSnap={snap || null}
      rotationSnap={ROTATE_SNAP * DEG}
      size={0.8}
      onMouseDown={() => (hot.current = true)}
      onMouseUp={onMouseUp}
    />
  );
}

/**
 * 部品1つ。グループ・キットなら中身を再帰的に置く。
 * クリックすると一番上の部品を選ぶ。選んでいる部品の中をクリックすると、1つ下の階層を選ぶ（グループの中に入っていく）
 */
function PartNode({
  spec,
  path,
  setTarget,
}: {
  spec: PartSpec;
  path: string;
  setTarget: (g: THREE.Group | null) => void;
}) {
  const kids = groupChildren(spec);
  const data = useMesh(spec.type, spec.params, kids === null);
  const children = kids ?? (data?.kit ? data.children : null);
  const isTarget = useStore((s) => s.selected === path);
  const highlighted = useStore((s) => [s.selected, ...s.multi].some((q) => q && (path === q || path.startsWith(q + "/"))));
  const hidden = useStore((s) => s.hidden.includes(path));

  const onClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    const { selected, select } = useStore.getState();
    const add = e.shiftKey || e.metaKey || e.ctrlKey;
    select(clickTarget(path, selected, add), add);
  };

  return (
    <group
      ref={isTarget ? setTarget : undefined}
      position={spec.pos}
      rotation={degToEuler(spec.rot)}
      visible={!hidden}
    >
      {children?.map((c, i) => <PartNode key={`${c.id}-${i}`} spec={c} path={joinPath(path, c.id)} setTarget={setTarget} />)}
      {data && !data.kit && (
        <MeshView data={data} color={data.color || FRAME_COLOR} selected={highlighted} onClick={onClick} />
      )}
    </group>
  );
}

/** クリックした形（leaf のパス）から、選ぶ部品のパスを決める */
function clickTarget(leaf: string, selected: string | null, add: boolean): string {
  const ids = splitPath(leaf);
  if (selected && !add && (leaf === selected || leaf.startsWith(selected + "/"))) {
    // 選んでいる部品の中 → 1つ下の階層へ（いちばん下ならそのまま）
    return ids.slice(0, Math.min(ids.length, splitPath(selected).length + 1)).join("/");
  }
  // 足すときは、選んでいる部品と同じ階層の部品を選ぶ（同じグループの兄弟をまとめて選べるように）
  const depth = add && selected ? splitPath(selected).length : 1;
  return ids.slice(0, Math.min(ids.length, depth)).join("/");
}

function MeshView({
  data,
  color,
  selected,
  onClick,
}: {
  data: Extract<MeshData, { kit: false }>;
  color: string;
  selected: boolean;
  onClick: (e: ThreeEvent<MouseEvent>) => void;
}) {
  const edge = VIEW_COLORS[useTheme((s) => s.theme)].edge;
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(data.vertices, 3));
    g.setIndex(data.indices);
    g.computeVertexNormals();
    return g;
  }, [data]);
  useEffect(() => () => geometry.dispose(), [geometry]);

  return (
    <mesh geometry={geometry} onClick={onClick}>
      <meshStandardMaterial
        color={color}
        emissive={selected ? SELECT_COLOR : "#000000"}
        emissiveIntensity={selected ? 0.45 : 0}
        roughness={0.6}
        metalness={0.05}
        polygonOffset
        polygonOffsetFactor={1}
        polygonOffsetUnits={1}
      />
      <Edges threshold={25} color={selected ? SELECT_COLOR : edge} />
    </mesh>
  );
}

/** 形状を取りに行く。新しい形が届くまでは前の形を表示したままにする */
function useMesh(type: string, params: Params, enabled = true): MeshData | null {
  const [data, setData] = useState<MeshData | null>(null);
  const notify = useStore((s) => s.notify);
  const epoch = useStore((s) => s.meshEpoch); // parts/ が書き換わったら取り直す
  const key = enabled ? epoch + type + JSON.stringify(params) : "";
  useEffect(() => {
    if (!enabled) return setData(null); // グループは中身を画面側で置くので、形を取りに行かない
    let alive = true;
    fetchMesh(type, params)
      .then((d) => alive && setData(d))
      .catch((e: Error) => alive && notify(`${type}: ${e.message}`, "error"));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return data;
}
