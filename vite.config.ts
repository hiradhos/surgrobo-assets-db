import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import sirv from 'sirv'

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'medshapenet-static',
      configureServer(server) {
        const assetsDir = path.resolve(__dirname, 'medshapenet_assets')
        server.middlewares.use('/medshapenet_assets', sirv(assetsDir, { dev: true }))
      },
    },
  ],
})
