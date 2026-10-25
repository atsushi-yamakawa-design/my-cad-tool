// 下のパネル: 加工前チェックと部品表。アセンブリが変わるたびに少し待ってから取り直す

import { useEffect, useState } from "react";
import { api } from "../api";
import { useStore } from "../store";
import type { Bom } from "../types";

type Tab = "check" | "bom";

export function BottomPanel({ collapsed, onToggle }: { collapsed: boolean; onToggle: (v: boolean) => void }) {
  const [tab, setTab] = useState<Tab>("check");
  const choose = (t: Tab) => {
    if (t === tab) onToggle(!collapsed); // 選択中のタブをもう一度押すと畳む・開く
    else {
      setTab(t);
      onToggle(false);
    }
  };
  const asm = useStore((s) => s.asm);
  const issues = useStore((s) => s.issues);
  const setIssues = useStore((s) => s.setIssues);
  const select = useStore((s) => s.select);
  const materials = useStore((s) => s.catalog?.materials);
  const [bom, setBom] = useState<Bom | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      try {
        setIssues((await api.check(asm)).issues);
        if (tab === "bom") setBom(await api.bom(asm));
        setError("");
      } catch (e) {
        setError((e as Error).message);
      }
    }, 500);
    return () => window.clearTimeout(timer);
  }, [asm, tab, setIssues]);

  return (
    <section className="panel bottom">
      <nav className="tabs">
        <button className={tab === "check" && !collapsed ? "on" : ""} onClick={() => choose("check")}>
          チェック {issues.length ? `(${issues.length})` : ""}
        </button>
        <button className={tab === "bom" && !collapsed ? "on" : ""} onClick={() => choose("bom")}>
          部品表
        </button>
        <button className="collapse" onClick={() => onToggle(!collapsed)} title={collapsed ? "パネルを開く" : "パネルを畳む"}>
          {collapsed ? "▲" : "▼"}
        </button>
      </nav>
      <div className="bottom-body">
        {error && <p className="field-error">{error}</p>}
        {tab === "check" &&
          (issues.length ? (
            <ul className="issues">
              {issues.map((i, k) => (
                <li key={k} className={i.level} onClick={() => select(i.part.split("/")[0])}>
                  <b>{i.level === "error" ? "エラー" : "注意"}</b> {i.part}: {i.message}
                </li>
              ))}
            </ul>
          ) : (
            <p className="hint">問題は見つかりませんでした（加工エリア・穴と縁の間隔・細い部分・めり込み）。</p>
          ))}
        {tab === "bom" && bom && (
          <div className="bom">
            {bom.frames.length > 0 && (
              <table>
                <caption>アルミフレーム</caption>
                <tbody>
                  {bom.frames.map((f, i) => (
                    <tr key={i}>
                      <td>{f.profile}</td>
                      <td className="r">{f.length} mm</td>
                      <td className="r">× {f.qty}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {Object.keys(bom.sheets).length > 0 && (
              <table>
                <caption>板</caption>
                <tbody>
                  {Object.entries(bom.sheets).map(([m, n]) => (
                    <tr key={m}>
                      <td>{materials?.[m]?.label ?? m}</td>
                      <td className="r">{bom.plates[m]?.length ?? 0} パーツ</td>
                      <td className="r">{n} シート</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {bom.prints.length > 0 && (
              <table>
                <caption>3Dプリント部品</caption>
                <tbody>
                  {bom.prints.map((p, i) => (
                    <tr key={i}>
                      <td>{p.label}</td>
                      <td>{p.filament}</td>
                      <td className="r">× {p.qty}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {(bom.bolts.length > 0 || bom.joints.length > 0) && (
              <table>
                <caption>ネジ類（目安）</caption>
                <tbody>
                  {bom.bolts.map((b, i) => (
                    <tr key={`b${i}`}>
                      <td>ボルト</td>
                      <td>
                        {b.size}×{b.length}
                      </td>
                      <td className="r">× {b.qty}</td>
                    </tr>
                  ))}
                  {bom.joints.map((j, i) => (
                    <tr key={`j${i}`}>
                      <td>{{ tnut: "Tナット", tap: "端面タップ", nut: "ナット" }[j.kind] ?? j.kind}</td>
                      <td>
                        {j.size} {j.profile}
                      </td>
                      <td className="r">× {j.qty}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
