# React Google Maps POC

A React application with TypeScript and Vite for visualizing locations on Google Maps with address search functionality.

## Features

- 🗺️ Interactive Google Maps integration
- 🔍 Address search with autocomplete
- 📍 Marker placement and info windows
- 📱 Responsive design with Tailwind CSS
- ⚡ Fast development with Vite

## Prerequisites

- Node.js (v18 or higher)
- Yarn package manager
- Google Maps API Key with the following APIs enabled:
  - Maps JavaScript API
  - Places API

## Setup

1. Clone the repository and install dependencies:
```bash
yarn install
```

2. Copy the environment template and add your Google Maps API key:
```bash
cp .env.example .env
```

3. Edit the `.env` file and replace `your_google_maps_api_key_here` with your actual Google Maps API key:
```
VITE_GOOGLE_MAPS_API_KEY=your_actual_api_key_here
```

## Development

Start the development server:
```bash
yarn dev
```

The application will be available at `http://localhost:5173`

## Build

Create a production build:
```bash
yarn build
```

## Project Structure

```
src/
├── components/
│   ├── AddressSearch.tsx    # Autocomplete search component
│   ├── MapView.tsx          # Google Maps display component
│   └── MarkerInfo.tsx       # Marker popup component
├── types/
│   └── location.ts          # TypeScript type definitions
├── App.tsx                  # Main app component
└── main.tsx                # Vite entry point
```

## Usage

1. Open the application in your browser
2. Click on the search input field
3. Type an address to see autocomplete suggestions
4. Select an address from the dropdown
5. The map will center on the selected location and display a marker
6. Click the marker to see address details in an info window

## Technologies Used

- React 18 with TypeScript
- Vite for build tooling
- @vis.gl/react-google-maps for Google Maps integration
- react-places-autocomplete for address search
- Tailwind CSS for styling

## API Key Setup

To get your Google Maps API key:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Maps JavaScript API and Places API
4. Create credentials (API Key)
5. Restrict your API key for security (optional but recommended)