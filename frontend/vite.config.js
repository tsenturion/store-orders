import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ command }) => ({
  plugins: [vue(), tailwindcss()],
  base: command === 'build' ? '/static/' : '/',
  build: { outDir: '../polka/static', emptyOutDir: true },
  server: { proxy: { '/api': 'http://127.0.0.1:8000', '/health': 'http://127.0.0.1:8000' } },
}));
