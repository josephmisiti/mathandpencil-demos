import { useMemo, useState } from "react";

interface MapControlsProps {
  highResEnabled: boolean;
  onHighResToggle: (enabled: boolean) => void;
  highResLoading?: boolean;
  highResError?: string | null;
}

export default function MapControls({
  highResEnabled,
  onHighResToggle,
  highResLoading = false,
  highResError = null
}: MapControlsProps) {
  const [isOpen, setIsOpen] = useState(false);

  const isDisabled = highResLoading;

  const statusMessage = useMemo(() => {
    if (highResLoading) return "Loading EagleView imagery…";
    if (highResError) return highResError;
    return "";
  }, [highResError, highResLoading]);

  const handleToggle = () => {
    if (isDisabled) return;
    onHighResToggle(!highResEnabled);
  };

  return (
    <div className="absolute top-4 right-4 z-20">
      <div className="bg-white rounded-lg shadow-lg border border-gray-200 min-w-64">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full px-4 py-3 text-left font-medium text-gray-700 hover:bg-gray-50 rounded-t-lg flex items-center justify-between"
        >
          <span>Map Controls</span>
          <svg
            className={`w-4 h-4 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {isOpen && (
          <div className="border-t border-gray-200">
            <div className="px-4 py-3">
              <div className="flex items-center justify-between">
                <label htmlFor="high-res-toggle" className="text-sm font-medium text-gray-700">
                  High Res Imagery
                </label>
                <button
                  id="high-res-toggle"
                  type="button"
                  onClick={handleToggle}
                  disabled={isDisabled}
                  aria-pressed={highResEnabled}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                    highResEnabled ? "bg-blue-600" : "bg-gray-300"
                  } ${isDisabled ? "opacity-60 cursor-not-allowed" : ""}`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                      highResEnabled ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>
              {statusMessage && (
                <p className="mt-2 text-xs text-gray-500">
                  {statusMessage}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
