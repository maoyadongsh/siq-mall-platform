import { createApp } from 'vue'
import 'element-plus/theme-chalk/base.css'
import 'element-plus/es/components/message/style/css'

import App from './App.vue'
import router from './router'
import pinia from './stores'

import '@/styles/index.scss'

const app = createApp(App)
app.use(pinia)
app.use(router)
app.mount('#app')
