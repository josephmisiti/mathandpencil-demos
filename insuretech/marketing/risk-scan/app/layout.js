export const metadata = {
  title: "risk-scan - Event Notification System | InsureTech Demo",
  description:
    "From a single address or coordinate to comprehensive property intelligence—AI-driven roof analytics, hazard data, and deep research reports in seconds.",
};

import "./globals.scss";

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
