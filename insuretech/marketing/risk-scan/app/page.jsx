import Link from "next/link";

export default function HomePage() {
  return (
    <div className="hero-section">
      <div className="overlay" />
      <div className="content">
        <div className="logo">
          <h1>risk-scan</h1>
          <p className="tagline">Event Notification System</p>
        </div>

        <div className="main-content">
          <h2>AI-Powered Property Intelligence</h2>
          <p className="description">
            From a single address or coordinate to comprehensive property intelligence—AI-driven roof analytics,
            hazard data, and deep research reports in seconds
          </p>
          <div className="cta-buttons">
            <Link href="/learn-more" className="btn btn-primary">
              Request Demo
            </Link>
            <Link href="/learn-more" className="btn btn-secondary">
              Learn More
            </Link>
          </div>
        </div>

        <div className="features">
          <div className="feature-card">
            <h3>🏠 AI Roof Analytics</h3>
            <p>Computer vision analysis of roof characteristics, materials, and construction quality</p>
          </div>
          <div className="feature-card">
            <h3>🌊 Hazard Intelligence</h3>
            <p>Distance to coast, flood zone classifications, and comprehensive risk scoring</p>
          </div>
          <div className="feature-card">
            <h3>🏗️ Construction Insights</h3>
            <p>Detailed site characteristics and structural data for accurate risk assessment</p>
          </div>
          <div className="feature-card">
            <h3>🤖 Deep Research Reports</h3>
            <p>Submit an address or lat/long, receive comprehensive research reports powered by advanced AI reasoning</p>
          </div>
        </div>
      </div>
    </div>
  );
}
