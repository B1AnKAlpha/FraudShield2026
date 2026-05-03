<template>
  <section class="legacy-card placeholder-page">
    <div class="legacy-card-title">{{ title }}</div>
    <div class="placeholder-copy">
      <p>{{ subtitle }}</p>
      <p>这一页保留原版导航位置，后续继续按旧功能迁移。</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

const title = computed(() => String(route.meta.title ?? "模块迁移中"));
const subtitle = computed(() => String(route.meta.subtitle ?? "模块迁移中"));
</script>
