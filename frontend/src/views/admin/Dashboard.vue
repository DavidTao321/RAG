<template>
  <div class="dashboard">
    <!-- KPI 概览 -->
    <el-row :gutter="14">
      <el-col v-for="kpi in kpis" :key="kpi.label" :span="6">
        <el-card shadow="never" class="kpi-card">
          <div class="kpi-label">{{ kpi.label }}</div>
          <div class="kpi-value">{{ kpi.value }}</div>
          <div class="kpi-sub">{{ kpi.sub }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14" style="margin-top: 14px">
      <!-- 问答趋势 -->
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <span>问答趋势（近 {{ days }} 天）</span>
              <el-radio-group v-model="days" size="small" @change="loadTrend">
                <el-radio-button :value="7">7天</el-radio-button>
                <el-radio-button :value="30">30天</el-radio-button>
                <el-radio-button :value="90">90天</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <div ref="trendEl" class="chart-box"></div>
        </el-card>
      </el-col>

      <!-- 性能指标 -->
      <el-col :span="10">
        <el-card shadow="never">
          <template #header><span>性能指标（论文数据）</span></template>
          <div class="cache-hit">
            <div class="cache-label">语义缓存命中率</div>
            <div class="cache-value">{{ (perf.cache_hit_rate * 100).toFixed(1) }}%</div>
            <el-progress
              :percentage="Math.round(perf.cache_hit_rate * 100)"
              :stroke-width="10"
              color="#2a78d6"
            />
            <div class="cache-sub">命中请求端到端耗时 &lt;100ms，未命中走完整检索生成链路</div>
          </div>
          <el-descriptions :column="1" border size="small" class="perf-table">
            <el-descriptions-item label="问答总量">{{ perf.total_qa }} 次</el-descriptions-item>
            <el-descriptions-item label="平均检索耗时">{{ perf.avg_retrieval_ms }} ms</el-descriptions-item>
            <el-descriptions-item label="平均重排耗时">{{ perf.avg_rerank_ms }} ms</el-descriptions-item>
            <el-descriptions-item label="平均生成耗时">{{ perf.avg_llm_ms }} ms</el-descriptions-item>
            <el-descriptions-item label="平均端到端耗时">{{ perf.avg_total_ms }} ms</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { getPerformance, getQaTrend, getStatsOverview } from '../../api/stats'

// 图表配色（dataviz 规范：双系列相邻色对蓝/橙，已验证通过）
const COLOR_TOTAL = '#2a78d6' // 问答总量
const COLOR_HIT = '#eb6834' // 缓存命中量

const overview = ref(null)
const perf = ref({ cache_hit_rate: 0, total_qa: 0, avg_retrieval_ms: 0, avg_rerank_ms: 0, avg_llm_ms: 0, avg_total_ms: 0 })
const days = ref(30)
const trend = ref([])
const trendEl = ref(null)
let chart = null

const kpis = computed(() => {
  const o = overview.value
  if (!o) return []
  const likeRate = o.feedback_like + o.feedback_dislike
    ? ((o.feedback_like / (o.feedback_like + o.feedback_dislike)) * 100).toFixed(0) + '%'
    : '—'
  return [
    { label: '注册用户', value: o.user_count, sub: '含管理员' },
    { label: '知识库文档', value: o.document_count, sub: `${o.chunk_count} 个知识分块` },
    { label: '累计问答', value: o.qa_count, sub: '含缓存命中' },
    { label: '用户反馈', value: `👍${o.feedback_like} / 👎${o.feedback_dislike}`, sub: `好评率 ${likeRate}` },
  ]
})

const loadAll = async () => {
  try {
    const [ov, p] = await Promise.all([getStatsOverview(), getPerformance()])
    overview.value = ov
    perf.value = p
  } catch (e) {
    console.error(e)
    ElMessage.error('看板数据加载失败，请稍后重试')
  }
  await loadTrend()
}

const loadTrend = async () => {
  try {
    trend.value = await getQaTrend(days.value)
  } catch (e) {
    console.error(e)
    ElMessage.error('趋势数据加载失败，请稍后重试')
  }
}

const renderChart = () => {
  if (!trendEl.value) return
  if (!chart) chart = echarts.init(trendEl.value)
  const dates = trend.value.map((t) => t.date.slice(5))
  chart.setOption({
    grid: { left: 44, right: 20, top: 36, bottom: 30 },
    legend: { data: ['问答量', '缓存命中量'], top: 4 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#c3c2b7' } },
      axisLabel: { color: '#898781' },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: '#e1e0d9' } },
      axisLabel: { color: '#898781' },
    },
    series: [
      {
        name: '问答量',
        type: 'line',
        smooth: false,
        symbolSize: 8,
        lineStyle: { width: 2, color: COLOR_TOTAL },
        itemStyle: { color: COLOR_TOTAL },
        data: trend.value.map((t) => t.count),
      },
      {
        name: '缓存命中量',
        type: 'line',
        smooth: false,
        symbolSize: 8,
        lineStyle: { width: 2, color: COLOR_HIT },
        itemStyle: { color: COLOR_HIT },
        data: trend.value.map((t) => t.cache_hit_count),
      },
    ],
  })
}

watch(trend, () => renderChart())

const onResize = () => chart && chart.resize()

onMounted(() => {
  loadAll()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>

<style scoped>
.kpi-card {
  text-align: center;
}

.kpi-label {
  font-size: 13px;
  color: #898781;
}

.kpi-value {
  font-size: 30px;
  font-weight: 700;
  margin: 6px 0;
  color: #0b0b0b;
  font-variant-numeric: tabular-nums;
}

.kpi-sub {
  font-size: 12px;
  color: #898781;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-box {
  height: 320px;
}

.cache-hit {
  text-align: center;
  padding: 4px 0 16px;
}

.cache-label {
  font-size: 13px;
  color: #898781;
}

.cache-value {
  font-size: 34px;
  font-weight: 700;
  color: #0b0b0b;
  margin: 4px 0 10px;
  font-variant-numeric: tabular-nums;
}

.cache-sub {
  font-size: 12px;
  color: #898781;
  margin-top: 8px;
}

.perf-table {
  margin-top: 8px;
}
</style>
