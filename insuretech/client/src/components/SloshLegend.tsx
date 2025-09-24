import {
  SLOSH_CATEGORIES,
  SLOSH_CATEGORY_LABELS,
  SloshCategory,
  categoryColorWithAlpha
} from "../constants/slosh";

type SloshLegendProps = {
  enabledCategories: Partial<Record<SloshCategory, boolean>>;
  className?: string;
};

export default function SloshLegend({ enabledCategories, className }: SloshLegendProps) {
  const positionClasses = className ?? "absolute bottom-4 right-4 z-20";
  const baseClasses = "w-72 rounded-lg border border-slate-200 bg-white/95 p-4 shadow-lg backdrop-blur";
  const finalClassName = `${positionClasses} ${baseClasses}`.trim();

  return (
    <aside className={finalClassName}>
      <h3 className="mb-3 text-sm font-semibold text-slate-700">SLOSH Surge Legend</h3>
      <ul className="space-y-2">
        {SLOSH_CATEGORIES.map((category) => {
          const isActive = enabledCategories[category] ?? false;
          const swatchColor = categoryColorWithAlpha(category, isActive ? undefined : 0.18);

          const textClass = isActive ? "text-slate-600" : "text-slate-400";
          const borderClass = isActive ? "border-slate-200" : "border-slate-200/70";

          return (
            <li key={category} className={`flex items-center gap-3 text-xs ${textClass}`}>
              <span
                className={`inline-block h-3 w-6 rounded-sm border ${borderClass}`}
                style={{ backgroundColor: swatchColor }}
              />
              <span className="leading-snug">{SLOSH_CATEGORY_LABELS[category]}</span>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-[11px] italic text-slate-400">
        Storm surge polygons highlight potential inundation for the selected SLOSH category.
      </p>
    </aside>
  );
}
