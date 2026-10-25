import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import * as THREE from "three";
import { App } from "./App";
import "./styles.css";

// alucad は Z が上（build123d と同じ）。three.js の既定（Y が上）を合わせる
THREE.Object3D.DEFAULT_UP.set(0, 0, 1);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
