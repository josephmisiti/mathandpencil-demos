import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    include: ['fabric'],
  },
  define: {
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'production'),
  },
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      external: [],
      output: {
        manualChunks: {
          'google-maps': ['@vis.gl/react-google-maps'],
          'deck-gl': ['deck.gl'],
          'loaders': ['@loaders.gl/mvt'],
          'vendor': ['react', 'react-dom'],
        }
      }
    }
  }
})
