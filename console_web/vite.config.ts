import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backend = env.AITEST_CONSOLE_BACKEND

  return {
    plugins: [vue()],
    build: {
      outDir: '../aitest_kit/console/web',
      emptyOutDir: true,
      sourcemap: false,
    },
    server: backend
      ? {
          proxy: {
            '/api': backend,
          },
        }
      : undefined,
    test: {
      environment: 'happy-dom',
      globals: true,
      include: ['src/**/*.test.ts'],
    },
  }
})
