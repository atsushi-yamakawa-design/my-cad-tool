// 3D ビュー。部品は「Python が作ったメッシュ（ローカル座標）」を pos / rot で置くだけ。
// 移動・回転はブラウザの中だけで済ませ、手を離したときに1回だけ JSON に書く（Undo 1回分）

import { Edges, GizmoHelper, GizmoViewport, Grid, OrbitControls, TransformControls } from "@react-three/drei";
import { Canvas, type ThreeEvent } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { fetchMesh } from "../api";
import { useStore } from "../store";
import { cleanMm, DEG, degToEuler, eulerToDeg } from "../transform";
import type { MeshData, Params, PartSpec, Vec3 } from "../types";

const ROTATE_SNAP = 15; // 3D 上で回すときの刻み（度）。90° ちょうどは R キーやボタンで
const FRAME_COLOR = "#b9bec7";
const SELECT_COLOR = "#2f7cf6";

export function Viewport() {
  const parts = useStore((s) => s.asm.parts);
  const selected = useStore((s) => s.selected);
  const select = useStore((s) => s.select);
  const snap = useStore((s) => s.snap);
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
      <color attach="background" args={["#eef0f3"]} />
      <hemisphereLight args={["#ffffff", "#b0b4bb", 1.2]} />
      <directionalLight position={[400, -500, 900]} intensity={1.6} />
      <directionalLight position={[-500, 300, 200]} intensity={0.5} />
      {/* drei の Grid は XZ 平面なので、Z が上の座標系に合わせて寝かせる */}
      <Grid
        rotation={[Math.PI / 2, 0, 0]}
        cellSize={snap >= 5 ? snap : 10}
        sectionSize={100}
        cellColor="#cfd3da"
        sectionColor="#a9afb9"
        infiniteGrid
        fadeDistance={4000}
      />
      {parts.map((p) => (
        <PartNode key={p.id} spec={p} rootId={p.id} groupRef={p.id === selected ? setTarget : undefined} />
      ))}
      {target && selected && <Gizmo target={target} id={selected} hot={gizmoHot} upAt={gizmoUpAt} />}
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
    const part = useStore.getState().asm.parts.find((p) => p.id === id);
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

/** 部品1つ。キットなら中身を再帰的に置く。クリックするとキット全体（rootId）を選ぶ */
function PartNode({
  spec,
  rootId,
  groupRef,
}: {
  spec: PartSpec;
  rootId: string;
  groupRef?: (g: THREE.Group | null) => void;
}) {
  const data = useMesh(spec.type, spec.params);
  const selected = useStore((s) => s.selected === rootId);
  const select = useStore((s) => s.select);

  const onClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    select(rootId);
  };

  return (
    <group ref={groupRef} position={spec.pos} rotation={degToEuler(spec.rot)}>
      {data?.kit &&
        data.children.map((c, i) => <PartNode key={`${c.id}-${i}`} spec={c} rootId={rootId} />)}
      {data && !data.kit && (
        <MeshView
          data={data}
          color={data.color || FRAME_COLOR}
          selected={selected}
          onClick={onClick}
        />
      )}
    </group>
  );
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
      <Edges threshold={25} color={selected ? SELECT_COLOR : "#4a505a"} />
    </mesh>
  );
}

/** 形状を取りに行く。新しい形が届くまでは前の形を表示したままにする */
function useMesh(type: string, params: Params): MeshData | null {
  const [data, setData] = useState<MeshData | null>(null);
  const notify = useStore((s) => s.notify);
  const epoch = useStore((s) => s.meshEpoch); // parts/ が書き換わったら取り直す
  const key = epoch + type + JSON.stringify(params);
  useEffect(() => {
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
