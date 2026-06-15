import { fileURLToPath } from 'node:url'
import vue from '@vitejs/plugin-vue'

// Plain object (not `defineConfig` from vitest/config): importing vitest's config
// types clashes with vite's bundled http-proxy/@types/node under vue-tsc --build.
// Vitest reads this object at runtime regardless.
export default {
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.{test,spec}.ts'],
  },
}
