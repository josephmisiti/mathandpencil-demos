# React Google Maps POC - Codex Prompt

## Project Overview

Create a React application with TypeScript and Vite for visualizing locations on Google Maps with address search functionality.

## Technical Requirements

### Stack

- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite
- **Maps**: Google Maps JavaScript API
- **Styling**: Tailwind CSS (or CSS modules)

### Required Dependencies

```json
{
  "@vis.gl/react-google-maps": "^1.0.0",
  "react-places-autocomplete": "^7.3.0"
}
```

## Core Features

### 1. Landing Page

- Clean, minimal design with a centered search interface
- Search input field with placeholder text: "Search for an address..."
- Map container that initially shows a default location (e.g., San Francisco)

### 2. Address Search & Autocomplete

- Implement Google Places Autocomplete using `react-places-autocomplete`
- Show dropdown suggestions as user types
- Handle selection of autocomplete suggestions
- Extract latitude and longitude coordinates from selected place

### 3. Map Visualization

- Use `@vis.gl/react-google-maps` for map rendering
- Display selected location with a Google Maps marker
- Center map on selected coordinates with appropriate zoom level
- Show info window/popup with address details when marker is clicked

### 4. State Management

- Use React hooks (useState, useEffect) for local state
- Track: current search term, selected coordinates, map center, marker visibility
- No external state management libraries needed for POC

## Implementation Details

### Component Structure

```
src/
├── components/
│   ├── AddressSearch.tsx    # Autocomplete search component
│   ├── MapView.tsx          # Google Maps display component
│   └── MarkerInfo.tsx       # Marker popup component
├── types/
│   └── location.ts          # TypeScript interfaces
├── App.tsx                  # Main app component
└── main.tsx                # Vite entry point
```

### Key TypeScript Interfaces

```typescript
interface Location {
  lat: number;
  lng: number;
  address: string;
  placeId?: string;
}

interface MapProps {
  center: Location;
  markers: Location[];
  zoom?: number;
}
```

## Constraints & Assumptions

### POC Limitations

- **No API calls**: Everything is ephemeral (no data persistence)
- **No authentication**: Direct Google Maps API usage with API key
- **No routing**: Single page application
- **No error handling**: Basic implementation only
- **No testing**: Focus on core functionality

### Environment Setup

- Requires Google Maps API key with the following APIs enabled:
  - Maps JavaScript API
  - Places API
- API key should be stored in `.env` file: `VITE_GOOGLE_MAPS_API_KEY`

## User Flow

1. User lands on homepage with empty map (default location)
2. User clicks on search input field
3. User types address and sees autocomplete suggestions
4. User selects an address from dropdown
5. Map centers on selected location and displays marker
6. User can click marker to see address details
7. User can search for new address (previous marker is replaced)

## Success Criteria

- ✅ Clean, responsive UI
- ✅ Working Google Places autocomplete
- ✅ Accurate coordinate extraction
- ✅ Map centering and marker placement
- ✅ TypeScript compilation without errors
- ✅ Vite dev server runs without issues

## Next Steps (V1 Planning)

After POC completion, V1 will include:

- Data persistence (database integration)
- User authentication
- Multiple markers support
- Search history
- Favorite locations
- API endpoints for location management
