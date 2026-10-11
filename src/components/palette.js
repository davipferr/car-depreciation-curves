// Validated palette (light + dark steps of the same hues). Categorical slots are
// assigned in this fixed order, never cycled; forms where every pair is visible
// at once (scatter, choropleth) use at most the first three.
const CATEGORICAL = {
  light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
  dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
};

// Sequential blue, light -> dark (steps 100..700).
const BLUES = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"];

export function palette(dark = false) {
  return {
    categorical: dark ? CATEGORICAL.dark : CATEGORICAL.light,
    accent: dark ? CATEGORICAL.dark[0] : CATEGORICAL.light[0],
    muted: dark ? "#5f5e5a" : "#c3c2b7",
    // n evenly spaced steps of the blue ramp (for quantile/threshold scales).
    // In dark mode the ramp is reversed so "more" is still "more contrast".
    blues(n) {
      const ramp = dark ? [...BLUES].reverse() : BLUES;
      return Array.from({length: n}, (_, i) => ramp[Math.round((i * (ramp.length - 1)) / (n - 1))]);
    },
    diverging: {
      neg: dark ? "#e66767" : "#e34948",
      mid: dark ? "#383835" : "#f0efec",
      pos: dark ? "#3987e5" : "#2a78d6"
    },
    noData: dark ? "#2b2b29" : "#e8e7e3"
  };
}
