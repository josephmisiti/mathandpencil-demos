const LEGEND_ITEMS = [
  {
    label: "High risk (A, AE, AH, AO)",
    color: "rgba(59,130,246,0.71)",
  },
  {
    label: "Coastal high risk (V, VE)",
    color: "rgba(239,68,68,0.75)",
  },
  {
    label: "0.2% annual chance (Zone X)",
    color: "rgba(249,115,22,0.63)",
  },
  {
    label: "Other FEMA zones",
    color: "rgba(168,162,158,0.51)",
  },
];

type FloodZoneLegendProps = {
  className?: string;
};

export default function FloodZoneLegend({ className }: FloodZoneLegendProps = {}) {
  const positionClasses = className ?? "absolute bottom-4 right-4 z-20";
  const baseClasses = "w-64 rounded-lg border border-slate-200 bg-white/95 p-4 shadow-lg backdrop-blur";
  const finalClassName = `${positionClasses} ${baseClasses}`.trim();

  return (
    <aside className={finalClassName}>
      <h3 className="mb-3 text-sm font-semibold text-slate-700">Flood Zone Legend</h3>
      <ul className="space-y-2">
        {LEGEND_ITEMS.map((item) => (
          <li key={item.label} className="flex items-center gap-3 text-xs text-slate-600">
            <span
              className="inline-block h-3 w-6 rounded-sm border border-slate-200"
              style={{ backgroundColor: item.color }}
            />
            <span className="leading-snug">{item.label}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] italic text-slate-400">
        Flood zone polygons appear only when the layer is enabled.
      </p>
    </aside>
  );
}
