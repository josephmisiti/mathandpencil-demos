import { useState } from 'react';
import { Globe, Anchor, Code, Mail, CheckCircle2, MapPin, Waves, Zap } from 'lucide-react';
import { supabase } from './lib/supabase';

function App() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    company: '',
    message: ''
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const { error } = await supabase
        .from('contact_submissions')
        .insert([formData]);

      if (error) throw error;

      setSubmitSuccess(true);
      setFormData({ name: '', email: '', company: '', message: '' });
      setTimeout(() => setSubmitSuccess(false), 5000);
    } catch (error) {
      console.error('Error submitting form:', error);
      alert('There was an error submitting your message. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white relative overflow-hidden">
      {/* World Map Background */}
      <div className="absolute inset-0 opacity-15">
        <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2000 1000" preserveAspectRatio="xMidYMid slice">
          <defs>
            <linearGradient id="mapGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="rgb(234, 179, 8)" stopOpacity="0.6" />
              <stop offset="50%" stopColor="rgb(250, 204, 21)" stopOpacity="0.6" />
              <stop offset="100%" stopColor="rgb(234, 179, 8)" stopOpacity="0.6" />
            </linearGradient>
          </defs>

          {/* Simplified world continents */}
          {/* North America */}
          <path d="M 250,200 L 280,180 L 320,185 L 350,170 L 380,175 L 410,160 L 440,170 L 460,190 L 470,220 L 480,250 L 470,280 L 450,310 L 420,340 L 390,360 L 360,370 L 330,365 L 310,350 L 290,330 L 270,310 L 255,285 L 245,255 L 240,225 Z"
                fill="url(#mapGradient)" stroke="rgb(234, 179, 8)" strokeWidth="1.5" opacity="0.8"/>

          {/* South America */}
          <path d="M 420,400 L 440,390 L 460,395 L 475,410 L 485,440 L 490,480 L 485,520 L 475,560 L 460,590 L 440,610 L 420,620 L 400,615 L 385,600 L 375,580 L 370,550 L 375,520 L 385,490 L 400,460 L 410,430 Z"
                fill="url(#mapGradient)" stroke="rgb(234, 179, 8)" strokeWidth="1.5" opacity="0.8"/>

          {/* Europe */}
          <path d="M 900,180 L 940,175 L 980,185 L 1010,200 L 1030,220 L 1040,245 L 1035,270 L 1020,290 L 1000,305 L 970,315 L 940,320 L 910,315 L 885,300 L 870,280 L 865,255 L 870,230 L 885,205 Z"
                fill="url(#mapGradient)" stroke="rgb(234, 179, 8)" strokeWidth="1.5" opacity="0.8"/>

          {/* Africa */}
          <path d="M 950,350 L 980,340 L 1010,345 L 1040,360 L 1060,385 L 1075,420 L 1080,460 L 1075,500 L 1060,540 L 1040,575 L 1010,600 L 980,615 L 950,620 L 920,615 L 895,600 L 875,580 L 860,550 L 855,515 L 860,480 L 875,445 L 895,410 L 920,380 Z"
                fill="url(#mapGradient)" stroke="rgb(234, 179, 8)" strokeWidth="1.5" opacity="0.8"/>

          {/* Asia */}
          <path d="M 1100,160 L 1160,155 L 1220,165 L 1280,180 L 1340,200 L 1400,210 L 1450,220 L 1490,240 L 1520,270 L 1540,310 L 1545,350 L 1535,390 L 1510,420 L 1475,440 L 1430,450 L 1380,455 L 1330,450 L 1280,435 L 1230,415 L 1180,390 L 1140,360 L 1110,325 L 1090,285 L 1085,240 L 1090,200 Z"
                fill="url(#mapGradient)" stroke="rgb(234, 179, 8)" strokeWidth="1.5" opacity="0.8"/>

          {/* Australia */}
          <path d="M 1400,600 L 1450,595 L 1500,605 L 1540,625 L 1565,655 L 1575,690 L 1570,725 L 1550,750 L 1520,765 L 1480,770 L 1440,765 L 1405,750 L 1380,725 L 1370,695 L 1375,660 L 1390,625 Z"
                fill="url(#mapGradient)" stroke="rgb(234, 179, 8)" strokeWidth="1.5" opacity="0.8"/>

          {/* Latitude/Longitude lines */}
          <line x1="0" y1="250" x2="2000" y2="250" stroke="rgba(234, 179, 8, 0.2)" strokeWidth="1" strokeDasharray="5,5"/>
          <line x1="0" y1="500" x2="2000" y2="500" stroke="rgba(234, 179, 8, 0.3)" strokeWidth="1.5" strokeDasharray="5,5"/>
          <line x1="0" y1="750" x2="2000" y2="750" stroke="rgba(234, 179, 8, 0.2)" strokeWidth="1" strokeDasharray="5,5"/>

          <line x1="500" y1="0" x2="500" y2="1000" stroke="rgba(234, 179, 8, 0.2)" strokeWidth="1" strokeDasharray="5,5"/>
          <line x1="1000" y1="0" x2="1000" y2="1000" stroke="rgba(234, 179, 8, 0.2)" strokeWidth="1" strokeDasharray="5,5"/>
          <line x1="1500" y1="0" x2="1500" y2="1000" stroke="rgba(234, 179, 8, 0.2)" strokeWidth="1" strokeDasharray="5,5"/>
        </svg>
      </div>

      {/* Content */}
      <div className="relative z-10">
        {/* Header */}
        <header className="border-b border-slate-800/50 backdrop-blur-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <div className="flex items-center gap-3">
              <Anchor className="w-8 h-8 text-yellow-400" />
              <h1 className="text-2xl font-bold bg-gradient-to-r from-yellow-400 to-amber-400 bg-clip-text text-transparent">
                Distance to Coast
              </h1>
            </div>
          </div>
        </header>

        {/* Hero Section */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 md:py-32">
          <div className="text-center max-w-4xl mx-auto">
            <div className="inline-flex items-center gap-2 bg-yellow-500/10 border border-yellow-500/20 rounded-full px-4 py-2 mb-8">
              <Globe className="w-4 h-4 text-yellow-400" />
              <span className="text-sm text-yellow-300">Global Coastline Data API</span>
            </div>

            <h2 className="text-5xl md:text-7xl font-bold mb-6 leading-tight">
              Calculate Distance to
              <span className="block bg-gradient-to-r from-yellow-400 via-amber-300 to-yellow-400 bg-clip-text text-transparent">
                Any Coastline
              </span>
            </h2>

            <p className="text-xl text-slate-300 mb-12 leading-relaxed">
              Access precise distance calculations to coastal boundaries for any location worldwide.
              Power your applications with our comprehensive API covering every country's coastline.
            </p>

            <div className="flex flex-wrap gap-4 justify-center">
              <a href="#api" className="group px-8 py-4 bg-gradient-to-r from-yellow-500 to-amber-500 rounded-lg font-semibold hover:shadow-lg hover:shadow-yellow-500/50 transition-all duration-300 hover:scale-105">
                Explore API
              </a>
              <a href="#contact" className="px-8 py-4 bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-lg font-semibold hover:bg-slate-800 transition-all duration-300">
                Get in Touch
              </a>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-2xl p-8 hover:border-yellow-500/50 transition-all duration-300">
              <div className="w-12 h-12 bg-yellow-500/10 rounded-lg flex items-center justify-center mb-6">
                <MapPin className="w-6 h-6 text-yellow-400" />
              </div>
              <h3 className="text-xl font-bold mb-3">Global Coverage</h3>
              <p className="text-slate-400 leading-relaxed">
                Access coastline data for every country in the world. From island nations to vast continental shores, we've got you covered.
              </p>
            </div>

            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-2xl p-8 hover:border-amber-500/50 transition-all duration-300">
              <div className="w-12 h-12 bg-amber-500/10 rounded-lg flex items-center justify-center mb-6">
                <Waves className="w-6 h-6 text-amber-400" />
              </div>
              <h3 className="text-xl font-bold mb-3">Custom Coastlines</h3>
              <p className="text-slate-400 leading-relaxed">
                Need to work with specific coastal boundaries? Our API supports custom coastline definitions tailored to your use case.
              </p>
            </div>

            <div className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-2xl p-8 hover:border-yellow-500/50 transition-all duration-300">
              <div className="w-12 h-12 bg-yellow-500/10 rounded-lg flex items-center justify-center mb-6">
                <Zap className="w-6 h-6 text-yellow-400" />
              </div>
              <h3 className="text-xl font-bold mb-3">Developer Friendly</h3>
              <p className="text-slate-400 leading-relaxed">
                RESTful API with comprehensive documentation, code examples, and SDKs. Get up and running in minutes.
              </p>
            </div>
          </div>
        </section>

        {/* API Section */}
        <section id="api" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="bg-gradient-to-br from-slate-900/50 to-slate-800/30 backdrop-blur-sm border border-slate-800 rounded-2xl p-8 md:p-12">
            <div className="grid md:grid-cols-2 gap-12 items-center">
              <div>
                <h3 className="text-3xl md:text-4xl font-bold mb-6">Powerful API</h3>
                <p className="text-slate-300 mb-6 leading-relaxed">
                  Our Distance to Coast API provides fast, accurate calculations for any coordinate on Earth.
                  Get instant distance measurements to the nearest coastline, with support for various units and precision levels.
                </p>
                <ul className="space-y-3 text-slate-300">
                  <li className="flex items-start gap-3">
                    <CheckCircle2 className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                    <span>Sub-kilometer accuracy for all queries</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle2 className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                    <span>Support for multiple coordinate formats</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle2 className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                    <span>Batch processing for multiple locations</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <CheckCircle2 className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                    <span>Custom coastline boundary definitions</span>
                  </li>
                </ul>
              </div>
              <div className="bg-slate-950/50 rounded-xl p-6 border border-slate-800">
                <div className="flex items-center gap-2 mb-4">
                  <div className="flex gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-red-500"></div>
                    <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                    <div className="w-3 h-3 rounded-full bg-green-500"></div>
                  </div>
                  <span className="text-xs text-slate-500 ml-auto">example.sh</span>
                </div>
                <pre className="text-sm text-slate-300 overflow-x-auto">
                  <code>{`curl -X GET \\
  'https://api.distancetocoast.com/v1/distance' \\
  -H 'Authorization: Bearer YOUR_API_KEY' \\
  -d '{
    "latitude": 40.7128,
    "longitude": -74.0060,
    "country": "US"
  }'`}</code>
                </pre>
              </div>
            </div>
          </div>
        </section>

        {/* Contact Section */}
        <section id="contact" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-12">
              <div className="inline-flex items-center gap-2 bg-yellow-500/10 border border-yellow-500/20 rounded-full px-4 py-2 mb-6">
                <Mail className="w-4 h-4 text-yellow-400" />
                <span className="text-sm text-yellow-300">Get Started</span>
              </div>
              <h3 className="text-3xl md:text-4xl font-bold mb-4">Ready to Integrate?</h3>
              <p className="text-slate-300">
                Contact us for API access, custom solutions, or any questions about our services.
              </p>
            </div>

            {submitSuccess && (
              <div className="mb-6 p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg flex items-center gap-3 text-yellow-300">
                <CheckCircle2 className="w-5 h-5" />
                <span>Thank you! We'll get back to you soon.</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="bg-slate-900/50 backdrop-blur-sm border border-slate-800 rounded-2xl p-8">
              <div className="space-y-6">
                <div>
                  <label htmlFor="name" className="block text-sm font-medium mb-2">
                    Name *
                  </label>
                  <input
                    type="text"
                    id="name"
                    name="name"
                    required
                    value={formData.name}
                    onChange={handleChange}
                    className="w-full px-4 py-3 bg-slate-950/50 border border-slate-800 rounded-lg focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-transparent transition-all"
                    placeholder="John Doe"
                  />
                </div>

                <div>
                  <label htmlFor="email" className="block text-sm font-medium mb-2">
                    Email *
                  </label>
                  <input
                    type="email"
                    id="email"
                    name="email"
                    required
                    value={formData.email}
                    onChange={handleChange}
                    className="w-full px-4 py-3 bg-slate-950/50 border border-slate-800 rounded-lg focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-transparent transition-all"
                    placeholder="john@example.com"
                  />
                </div>

                <div>
                  <label htmlFor="company" className="block text-sm font-medium mb-2">
                    Company
                  </label>
                  <input
                    type="text"
                    id="company"
                    name="company"
                    value={formData.company}
                    onChange={handleChange}
                    className="w-full px-4 py-3 bg-slate-950/50 border border-slate-800 rounded-lg focus:outline-none focus:ring-2 focus:ring-yellow-500 focus:border-transparent transition-all"
                    placeholder="Your Company"
                  />
                </div>

                <div>
                  <label htmlFor="message" className="block text-sm font-medium mb-2">
                    Message *
                  </label>
                  <textarea
                    id="message"
                    name="message"
                    required
                    value={formData.message}
                    onChange={handleChange}
                    rows={5}
                    className="w-full px-4 py-3 bg-slate-950/50 border border-slate-800 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all resize-none"
                    placeholder="Tell us about your use case..."
                  />
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full px-8 py-4 bg-gradient-to-r from-yellow-500 to-amber-500 rounded-lg font-semibold hover:shadow-lg hover:shadow-yellow-500/50 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-[1.02]"
                >
                  {isSubmitting ? 'Sending...' : 'Send Message'}
                </button>
              </div>
            </form>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-slate-800/50 mt-20">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div className="flex flex-col md:flex-row justify-between items-center gap-4">
              <div className="flex items-center gap-3">
                <Anchor className="w-6 h-6 text-yellow-400" />
                <span className="text-slate-400">© 2025 Distance to Coast. All rights reserved.</span>
              </div>
              <div className="flex gap-6 text-slate-400">
                <a href="#" className="hover:text-yellow-400 transition-colors">Documentation</a>
                <a href="#" className="hover:text-yellow-400 transition-colors">API Status</a>
                <a href="#contact" className="hover:text-yellow-400 transition-colors">Contact</a>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default App;
