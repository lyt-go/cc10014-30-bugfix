<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">数仓分层治理平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向数据入库、清洗转换、分层建模、质量校验与血缘追踪的分层数仓治理平台。</span>
        <span class="head-user">当前值班：{{ store.operator }} · {{ store.shiftLabel }}</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const navItems = [{ label: "运营概览", path: "/" }, { label: "原始入库", path: "/raw_ingest" }, { label: "字段映射", path: "/column_mapping" }, { label: "清洗策略", path: "/cleanse_rule" }, { label: "去重配置", path: "/dedup_config" }, { label: "贴源层管理", path: "/ods_layer" }, { label: "明细层管理", path: "/dwd_layer" }, { label: "汇总层管理", path: "/dws_layer" }, { label: "维度建模", path: "/dim_model" }, { label: "快照管理", path: "/snapshot_mgr" }, { label: "分区治理", path: "/partition_mgr" }, { label: "质量稽核", path: "/quality_check" }, { label: "血缘追踪", path: "/lineage_track" }, { label: "补数调度", path: "/backfill_job" }, { label: "表级比对", path: "/table_compare" }, { label: "结构注册", path: "/schema_registry" }, { label: "结构版本诊断", path: "/schema_version_view" }, { label: "数据发布", path: "/data_publish" }, { label: "转换编排", path: "/transform_dag" }, { label: "冷热归档", path: "/cold_archive" }]
</script>
