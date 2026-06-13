import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/intern'
  },
  {
    path: '/intern',
    name: 'InternDashboard',
    component: () => import('@/views/InternDashboard.vue')
  },
  {
    path: '/intern/map',
    name: 'GrowthMap',
    component: () => import('@/views/GrowthMap.vue')
  },
  {
    path: '/mentor',
    name: 'MentorDashboard',
    component: () => import('@/views/MentorDashboard.vue')
  },
  {
    path: '/hr',
    name: 'HRDashboard',
    component: () => import('@/views/HRDashboard.vue')
  },
  {
    path: '/sandbox',
    name: 'SandboxPanel',
    component: () => import('@/views/SandboxPanel.vue')
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
