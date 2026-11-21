// Colour roles for charts. Pathway colours follow the IPCC AR6 scenario
// palette (SSP1-2.6 navy, SSP2-4.5 orange, SSP1-1.9 cyan, SSP3-7.0 red,
// SSP5-8.5 dark red) plus a green and a purple, ordered so neighbours stay
// distinct with colour-blind vision. Checked with a palette validator on both
// surfaces: light adjacent CVD ΔE ≥ 11.6, normal-vision ≥ 20.6; dark CVD ≥ 8.9,
// normal-vision ≥ 16.7. The navy is one step lighter than the IPCC value so it
// does not read as black. Pathways keep their slot by position in the bundle,
// so a colour never moves when others are hidden; past seven, use "Other".

import { useEffect, useState } from "react";

const LIGHT = ["#2e5f94", "#3a8a3f", "#f79420", "#00adcf", "#e71d25", "#8d5ba6", "#951b1e"];
const DARK = ["#4f86c6", "#2a7a4a", "#d47811", "#0093b0", "#e5393f", "#a57bbd", "#c0504d"];
export const MAX_SLOTS = LIGHT.length;
export const OTHER_GREY = { light: "#8c918f", dark: "#7b827f" };

export function isDark(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

/** Slot colour for the i-th entity. Past seven it returns the "Other" grey. */
export function seriesColor(i: number): string {
  const pal = isDark() ? DARK : LIGHT;
  return i >= 0 && i < pal.length ? pal[i] : isDark() ? OTHER_GREY.dark : OTHER_GREY.light;
}

export function token(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

export interface ChartTheme {
  ink: string;
  muted: string;
  grid: string;
  surface: string;
  font: string;
}

export function chartTheme(): ChartTheme {
  return {
    ink: token("--ink", "#16302f"),
    muted: token("--muted", "#5a6b67"),
    grid: token("--rule", "#dde3df"),
    surface: token("--surface", "#fbfcfb"),
    font: token("--font-body", "system-ui, sans-serif"),
  };
}

/** Re-render on OS light/dark switch. */
export function useColorScheme(): boolean {
  const [dark, setDark] = useState(isDark());
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!mq) return;
    const on = () => setDark(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return dark;
}
