import { useEffect } from "react";
import { BottomPanel } from "./components/BottomPanel";
import { Palette } from "./components/Palette";
import { PropertyPanel } from "./components/PropertyPanel";
import { Toolbar } from "./components/Toolbar";
import { Viewport } from "./components/Viewport";
import { useStore } from "./store";

export function App() {
  const notice = useStore((s) => s.notice);
  const ready = useStore((s) => s.catalog !== null);

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
    <div className="app">
      <Toolbar />
      <Palette />
      <main className="viewport">{ready && <Viewport />}</main>
      <PropertyPanel />
      <BottomPanel />
      {notice && <div className={`notice ${notice.kind}`}>{notice.text}</div>}
    </div>
  );
}
