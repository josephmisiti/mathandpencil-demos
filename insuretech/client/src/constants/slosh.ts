export const SLOSH_CATEGORIES = [
  "Category1",
  "Category2",
  "Category3",
  "Category4",
  "Category5"
] as const;

export type SloshCategory = (typeof SLOSH_CATEGORIES)[number];

export const SLOSH_CATEGORY_COLORS: Record<SloshCategory, [number, number, number]> = {
  Category1: [59, 130, 246],
  Category2: [147, 51, 234],
  Category3: [249, 115, 22],
  Category4: [16, 185, 129],
  Category5: [239, 68, 68]
};

export const SLOSH_CATEGORY_ALPHA: Record<SloshCategory, number> = {
  Category1: 0.75,
  Category2: 0.6,
  Category3: 0.45,
  Category4: 0.32,
  Category5: 0.2
};

export const SLOSH_CATEGORY_LABELS: Record<SloshCategory, string> = {
  Category1: "Category 1 surge extent",
  Category2: "Category 2 surge extent",
  Category3: "Category 3 surge extent",
  Category4: "Category 4 surge extent",
  Category5: "Category 5 surge extent"
};

export function categoryColorWithAlpha(category: SloshCategory, alpha?: number): string {
  const [r, g, b] = SLOSH_CATEGORY_COLORS[category];
  const resolvedAlpha = alpha ?? SLOSH_CATEGORY_ALPHA[category];
  return `rgba(${r}, ${g}, ${b}, ${resolvedAlpha})`;
}
