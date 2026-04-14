import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
  },
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;

          if (id.includes('reactflow')) return 'reactflow';
          if (id.includes('recharts')) return 'recharts';
          if (id.includes('react-router-dom')) return 'router';
          if (id.includes('react-hot-toast')) return 'toast';
          if (id.includes('lucide-react')) return 'icons';

          return 'vendor';
        },
      },
    },
  },
});
