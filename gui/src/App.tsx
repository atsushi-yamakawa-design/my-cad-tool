import { useEffect, useState } from "react";
import { BottomPanel } from "./components/BottomPanel";
import { Palette } from "./components/Palette";
import { PropertyPanel } from "./components/PropertyPanel";
import { Toolbar } from "./components/Toolbar";
import { Viewport } from "./components/Viewport";
import { useStore } from "./store";

export function App() {
  const notice = useStore((s) => s.notice);
  const ready = useStore((s) => s.catalog !== null);
  const conflict = useStore((s) => s.conflict);
  const name = useStore((s) => s.name);
  const [bottomCollapsed, setBottomCollapsed] = useState(false);

  // 1秒ごとに、デザインファイルと parts/ が外で変わっていないか確認する（Claude Code などが書き換えたとき用）
  useEffect(() => {
    if (!ready) return;
    let busy = false;
    const timer = window.setInterval(async () => {
      if (busy) return;
      busy = true;
      try {
        await useStore.getState().poll();
      } catch {
        /* サーバーが止まっているときは黙って待つ */
      } finally {
        busy = false;
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [ready]);

  useEffect(() => {
    useStore
      .getState()
      .init()
      .catch((e: Error) => useStore.getState().notify(`サーバーに接続できません: ${e.message}`, "error"));
  }, []);

  // キーボードショートカット（入力欄の中では効かない）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const s = useStore.getState();
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void s.save();
        return;
      }
      const typing = (e.target as HTMLElement).closest("input, textarea, select");
      if (typing) return;
      if (mod && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) s.redo();
        else s.undo();
      } else if ((e.key === "Delete" || e.key === "Backspace") && s.selected) {
        e.preventDefault();
        s.removePart(s.selected);
      } else if (e.key === "Escape") {
        s.select(null);
      } else if (mod || e.altKey) {
        return;
      } else if (e.key.toLowerCase() === "w") {
        s.setTool("move");
      } else if (e.key.toLowerCase() === "e") {
        s.setTool("rotate");
      } else if (e.key.toLowerCase() === "r" && s.selected) {
        // R: 上から見て反時計回りに 90°（Shift で逆回り）
        s.rotate90(2, e.shiftKey ? -1 : 1);
      } else if (e.key.startsWith("Arrow") && s.selected) {
        // 矢印キー: 床の上で前後左右に動かす（Shift で 10 倍）。PageUp/Down で上下
        e.preventDefault();
        const step = e.shiftKey ? 10 : 1;
        if (e.key === "ArrowLeft") s.nudge(0, -step);
        if (e.key === "ArrowRight") s.nudge(0, step);
        if (e.key === "ArrowUp") s.nudge(1, step);
        if (e.key === "ArrowDown") s.nudge(1, -step);
      } else if ((e.key === "PageUp" || e.key === "PageDown") && s.selected) {
        e.preventDefault();
        s.nudge(2, (e.shiftKey ? 10 : 1) * (e.key === "PageUp" ? 1 : -1));
      }
    };
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (useStore.getState().dirty) e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, []);

  return (
    <div className={`app ${bottomCollapsed ? "bottom-collapsed" : ""}`}>
      <Toolbar />
      <Palette />
      <main className="viewport">{ready && <Viewport />}</main>
      <PropertyPanel />
      <BottomPanel collapsed={bottomCollapsed} onToggle={setBottomCollapsed} />
      {conflict && (
        <div className="conflict">
          <span>
            {name}.json の外部（Claude Code など）の変更を合わせました。ただし {conflict.ids.join("、")}{" "}
            はこちらでも変えています。どちらにしますか？
          </span>
          <button onClick={() => useStore.getState().takeTheirs()}>外部の内容にする</button>
          <button onClick={() => useStore.getState().keepMine()}>こちらの内容を残す</button>
        </div>
      )}
      {notice && <div className={`notice ${notice.kind}`}>{notice.text}</div>}
    </div>
  );
}
