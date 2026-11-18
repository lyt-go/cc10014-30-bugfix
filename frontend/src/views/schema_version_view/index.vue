<template>
  <section class="page" data-module="schema_version_view">
    <header class="page-head">
      <div>
        <h2>结构版本诊断视图</h2>
        <p class="page-desc">按自然版本顺序展示同名表的结构版本，标注当前版本来源（手工/血缘推导）与版本冲突处理结果。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" data-testid="refresh-view" type="button" :disabled="refreshing" @click="refreshView">
          {{ refreshing ? '刷新中…' : '刷新结构' }}
        </button>
        <button class="btn" data-testid="export" type="button" @click="exportRows">导出诊断清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :data-testid="`filter-${field}`" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" data-testid="query" type="submit">查询</button>
      <button class="btn ghost" data-testid="reset" type="button" @click="resetFilters">重置条件</button>
    </form>

    <form class="filter-bar" @submit.prevent="refreshView">
      <label class="filter-item">
        <span>表名称（可选）</span>
        <input v-model="refreshTable" data-testid="refresh-table" placeholder="留空则刷新全部表" />
      </label>
      <label class="filter-item">
        <span>业务日期</span>
        <input v-model="refreshBizDate" data-testid="refresh-biz-date" type="date" />
      </label>
      <button class="btn primary" data-testid="refresh-submit" type="submit" :disabled="refreshing">刷新结构</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="String(row.id)"
          :data-testid="`row-${row.id}`"
          :data-status="String(row.status)"
          :class="{ 'row-current': row['是否当前'] === '是', 'row-conflict': row['冲突标记'] === '版本冲突' }"
        >
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              class="link"
              type="button"
              :data-testid="`action-${row.id}-标记复核`"
              @click="runAction('标记复核', row)"
            >
              标记复核
            </button>
            <button class="link" type="button" :data-testid="`history-${row.id}`" @click="openHistory(row)">
              历史回查
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无诊断数据，可点击刷新结构生成诊断视图</td>
        </tr>
      </tbody>
    </table>

    <div v-if="showHistory" class="modal-backdrop" data-testid="history-modal">
      <div class="modal">
        <h3>历史回查：{{ historyRow?.['视图编号'] }}</h3>
        <table class="data-table">
          <thead>
            <tr><th>快照序号</th><th>快照时间</th><th>是否当前</th><th>当前来源</th><th>冲突标记</th><th>记录状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in historyItems" :key="item.version">
              <td>{{ item.version }}</td>
              <td>{{ item.timestamp }}</td>
              <td>{{ item.data['是否当前'] ?? '—' }}</td>
              <td>{{ item.data['当前来源'] || '—' }}</td>
              <td>{{ item.data['冲突标记'] ?? '—' }}</td>
              <td>{{ item.data['记录状态'] ?? '—' }}</td>
            </tr>
            <tr v-if="!historyItems.length">
              <td colspan="6" class="empty-state">该记录暂无历史快照</td>
            </tr>
          </tbody>
        </table>
        <div class="page-actions">
          <button class="btn" type="button" data-testid="close-history" @click="showHistory = false">关闭</button>
        </div>
      </div>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条诊断记录</span>
      <span v-if="successMessage" class="success-text">{{ successMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type HistoryItem = { version: number; timestamp: string; data: Record<string, string | number | null> }

const ENDPOINT = '/api/schema_version_view'
const columns = ["视图编号", "表名称", "定义版本", "自然顺序", "是否当前", "版本来源", "当前来源", "冲突标记", "冲突处理", "业务日期", "跨月标记", "记录状态"]
const filterFields = ["表名称", "版本来源", "是否当前", "冲突标记", "记录状态"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const filters = ref<Record<string, string>>({})
const refreshing = ref(false)
const refreshTable = ref('')
const refreshBizDate = ref('')
const showHistory = ref(false)
const historyRow = ref<Row | null>(null)
const historyItems = ref<HistoryItem[]>([])
const summary = ref<Record<string, number | string>>({})

const stats = computed(() => [
  { label: '覆盖表数', value: summary.value['覆盖表数'] ?? 0 },
  { label: '版本记录数', value: summary.value['版本记录数'] ?? 0 },
  { label: '手工当前', value: summary.value['手工当前数'] ?? 0 },
  { label: '血缘当前', value: summary.value['血缘当前数'] ?? 0 },
  { label: '版本冲突', value: summary.value['版本冲突数'] ?? 0 },
  { label: '未完成', value: summary.value['未完成数'] ?? 0 },
])

function resetFilters() {
  filters.value = {}
  void reload()
}

async function exportRows() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value).toString()
  try {
    const response = await request(`${ENDPOINT}/export?${query}`)
    if (!response.ok) throw new Error('导出失败，请稍后重试')
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = 'schema_version_view.csv'
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导出失败'
  }
}

async function refreshView() {
  refreshing.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const body: Record<string, string> = {}
    if (refreshTable.value.trim()) body['表名称'] = refreshTable.value.trim()
    if (refreshBizDate.value) body['业务日期'] = refreshBizDate.value
    const response = await request(`${ENDPOINT}/refresh`, {
      method: 'POST', body: JSON.stringify(body),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) throw new Error(payload.message || '刷新失败')
    successMessage.value = payload.message || '结构版本诊断视图已刷新'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '刷新失败'
  } finally {
    refreshing.value = false
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('诊断视图动作未生效，请稍后重试')
    }
    successMessage.value = `诊断记录已${action}`
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '诊断视图操作失败'
  }
}

async function openHistory(row: Row) {
  errorMessage.value = ''
  historyRow.value = row
  historyItems.value = []
  showHistory.value = true
  try {
    const response = await request(`${ENDPOINT}/${row.id}/history`)
    if (!response.ok) throw new Error('历史快照读取失败')
    const payload = await response.json()
    historyItems.value = payload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '历史快照读取失败'
  }
}

async function reloadSummary() {
  try {
    const response = await request(`${ENDPOINT}/summary`)
    if (response.ok) summary.value = await response.json()
  } catch {
    summary.value = {}
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('诊断视图列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '诊断视图列表读取失败'
  }
  await reloadSummary()
}

onMounted(reload)
</script>

<style scoped>
.row-current td {
  background: #ecfdf5;
}
.row-conflict td {
  background: #fff7ed;
}
.row-current.row-conflict td {
  background: #fef3c7;
}
.success-text {
  color: #047857;
}
</style>
