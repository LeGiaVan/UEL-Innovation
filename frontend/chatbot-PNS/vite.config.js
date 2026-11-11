import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig(({mode}) => {
 const env=loadEnv(mode,process.cwd(),'')
 return {plugins:[react()],server:{host:'127.0.0.1',port:5176,proxy:{'/api':{target:env.API_PROXY_TARGET || 'http://127.0.0.1:30957',changeOrigin:true}}}}
})
