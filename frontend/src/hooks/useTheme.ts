import { useEffect } from "react";

const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");

function applyTheme() {
  const dark = systemTheme.matches;
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.querySelector('meta[name="theme-color"]')?.setAttribute(
    "content", dark ? "#101827" : "#f5f7fb",
  );
}

// Apply before React renders, including while the initial data is loading.
applyTheme();

export function useTheme() {
  useEffect(() => {
    applyTheme();
    systemTheme.addEventListener("change", applyTheme);
    return () => systemTheme.removeEventListener("change", applyTheme);
  }, []);
}
