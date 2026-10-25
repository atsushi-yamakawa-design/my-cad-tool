// 3D ビュー。部品は「Python が作ったメッシュ（ローカル座標）」を pos / rot で置くだけ

import { Edges, GizmoHelper, GizmoViewport, Grid, OrbitControls } from "@react-three/drei";
import { Canvas, type ThreeEvent } from "@react-three/fiber";
import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { fetchMesh } from "../api";
import { useStore } from "../store";
import type { MeshData, Params, PartSpec } from "../types";

const DEG = Math.PI / 180;
const FRAME_COLOR = "#b9bec7";
const SELECT_COLOR = "#2f7cf6";

export function Viewport() {
  const parts = useStore((s) => s.asm.parts);
  const select = useStore((s) => s.select);

  return (
    <Canvas
      camera={{ position: [450, -600, 420], up: [0, 0, 1], fov: 35, near: 1, far: 20000 }}
      onPointerMissed={() => select(null)}
    >
      <color attach="background" args={["#eef0f3"]} />
      <hemisphereLight args={["#ffffff", "#b0b4bb", 1.2]} />
      <directionalLight position={[400, -500, 900]} intensity={1.6} />
      <directionalLight position={[-500, 300, 200]} intensity={0.5} />
      {/* drei の Grid は XZ 平面なので、Z が上の座標系に合わせて寝かせる */}
      <Grid
        rotation={[Math.PI / 2, 0, 0]}
        cellSize={20}
        sectionSize={100}
        cellColor="#cfd3da"
        sectionColor="#a9afb9"
        infiniteGrid
        fadeDistance={4000}
      />
      {parts.map((p) => (
        <PartNode key={p.id} spec={p} rootId={p.id} />
      ))}
      <OrbitControls makeDefault />
      <GizmoHelper alignment="bottom-right" margin={[64, 64]}>
        <GizmoViewport labelColor="white" axisHeadScale={0.9} />
      </GizmoHelper>
    </Canvas>
  );
}

/** 部品1つ。キットなら中身を再帰的に置く。クリックするとキット全体（rootId）を選ぶ */
function PartNode({ spec, rootId }: { spec: PartSpec; rootId: string }) {
  const data = useMesh(spec.type, spec.params);
  const selected = useStore((s) => s.selected === rootId);
  const select = useStore((s) => s.select);
  const materials = useStore((s) => s.catalog?.materials);

  const onClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    select(rootId);
  };

  return (
    <group position={spec.pos} rotation={new THREE.Euler(spec.rot[0] * DEG, spec.rot[1] * DEG, spec.rot[2] * DEG, "XYZ")}>
      {data?.kit &&
        data.children.map((c, i) => <PartNode key={`${c.id}-${i}`} spec={c} rootId={rootId} />)}
      {data && !data.kit && (
        <MeshView
          data={data}
          color={data.category === "frame" ? FRAME_COLOR : (data.mat && materials?.[data.mat]?.color) || "#d8c7a3"}
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
  const key = type + JSON.stringify(params);
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
