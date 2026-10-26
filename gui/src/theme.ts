// 画面のテーマ（ライト／ダーク）。設定はブラウザに覚えておき、<html data-theme="..."> に反映する。
// 色そのものは styles.css のトークンと、下の VIEW_COLORS（3D ビュー用）にある

import { create } from "zustand";

export type ThemePref = "system" | "light" | "dark";
export type Theme = "light" | "dark";

const KEY = "alucad.theme"; // index.html の読み込み前スクリプトも同じキーを読む

/** 3D ビューの色。CSS 変数は three.js から読めないので、ここに並べる */
export const VIEW_COLORS = {
  light: { bg: "#eef0f3", ground: "#b0b4bb", cell: "#cfd3da", section: "#a9afb9", edge: "#4a505a" },
  dark: { bg: "#1b1e23", ground: "#3a3f47", cell: "#2a2e35", section: "#3e444d", edge: "#24282e" },
} as const;

const media = window.matchMedia("(prefers-color-scheme: dark)");

function loadPref(): ThemePref {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function resolve(pref: ThemePref): Theme {
  if (pref === "system") return media.matches ? "dark" : "light";
  return pref;
}

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme;
}

interface ThemeState {
  pref: ThemePref;
  theme: Theme;
  setPref: (pref: ThemePref) => void;
}

export const useTheme = create<ThemeState>((set) => ({
  pref: loadPref(),
  theme: resolve(loadPref()),
  setPref: (pref) => {
    try {
      if (pref === "system") window.localStorage.removeItem(KEY);
      else window.localStorage.setItem(KEY, pref);
    } catch {
      /* 覚えられなくても、今の画面には反映する */
    }
    set({ pref, theme: resolve(pref) });
  },
}));

// 「システムに合わせる」のときは、Mac の外観設定が変わったら追従する
media.addEventListener("change", () => {
  const { pref } = useTheme.getState();
  if (pref === "system") useTheme.setState({ theme: resolve(pref) });
});

apply(useTheme.getState().theme);
useTheme.subscribe((s) => apply(s.theme));
