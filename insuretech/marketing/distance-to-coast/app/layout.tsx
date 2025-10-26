export const metadata = {
  title: 'Distance to Coast',
  description: 'Calculate distance to any coastline via API',
};

import './globals.css';
import type { ReactNode } from 'react';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

