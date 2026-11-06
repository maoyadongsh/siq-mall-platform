<template>
  <div class="mall-layout">
    <header class="mall-layout__header">
      <div class="mall-layout__brand">优选商城</div>
      <nav class="mall-layout__nav">
        <router-link class="mall-layout__link" to="/">首页</router-link>
      </nav>
    </header>

    <main class="mall-layout__main">
      <router-view />
    </main>

    <footer class="mall-layout__footer">优选商城 · 迭代一 基础框架</footer>
  </div>
</template>

<style scoped>
.mall-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--mall-bg);
}

.mall-layout__header {
  display: flex;
  align-items: center;
  gap: var(--mall-spacing-lg);
  height: 60px;
  padding: 0 var(--mall-spacing-xl);
  background: #fff;
  border-bottom: 1px solid var(--mall-border);
}

.mall-layout__brand {
  font-size: 18px;
  font-weight: 600;
  color: var(--mall-color-primary);
}

.mall-layout__nav {
  display: flex;
  gap: var(--mall-spacing-md);
}

.mall-layout__link {
  color: var(--mall-text);
  text-decoration: none;
}

.mall-layout__link:hover {
  color: var(--mall-color-primary);
}

.mall-layout__main {
  flex: 1;
  padding: var(--mall-spacing-xl);
}

.mall-layout__footer {
  padding: var(--mall-spacing-md) var(--mall-spacing-xl);
  text-align: center;
  color: var(--mall-text-secondary);
  font-size: 12px;
}
</style>
