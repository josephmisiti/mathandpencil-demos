// Shared color constants for the application
export const COLORS = {
  // Background colors
  panelBackground: 'bg-white',

  // Border colors
  panelBorder: 'border-gray-200',

  // Shadow
  panelShadow: 'shadow-lg',

  // Rounded corners
  panelRounded: 'rounded-lg',

  // Navigation background
  navigationBackground: 'bg-white',
} as const;

// For inline styles when Tailwind classes aren't sufficient
export const INLINE_COLORS = {
  panelBackground: '#ffffff',
  navigationBackground: '#ffffff',
} as const;
