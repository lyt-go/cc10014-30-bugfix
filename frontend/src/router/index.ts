import { createRouter, createWebHistory } from 'vue-router'

import Overview from '@/views/Overview.vue'
const RawIngest = () => import('@/views/raw_ingest/index.vue')
const ColumnMapping = () => import('@/views/column_mapping/index.vue')
const CleanseRule = () => import('@/views/cleanse_rule/index.vue')
const DedupConfig = () => import('@/views/dedup_config/index.vue')
const OdsLayer = () => import('@/views/ods_layer/index.vue')
const DwdLayer = () => import('@/views/dwd_layer/index.vue')
const DwsLayer = () => import('@/views/dws_layer/index.vue')
const DimModel = () => import('@/views/dim_model/index.vue')
const SnapshotMgr = () => import('@/views/snapshot_mgr/index.vue')
const PartitionMgr = () => import('@/views/partition_mgr/index.vue')
const QualityCheck = () => import('@/views/quality_check/index.vue')
const LineageTrack = () => import('@/views/lineage_track/index.vue')
const BackfillJob = () => import('@/views/backfill_job/index.vue')
const TableCompare = () => import('@/views/table_compare/index.vue')
const SchemaRegistry = () => import('@/views/schema_registry/index.vue')
const SchemaVersionView = () => import('@/views/schema_version_view/index.vue')
const DataPublish = () => import('@/views/data_publish/index.vue')
const TransformDag = () => import('@/views/transform_dag/index.vue')
const ColdArchive = () => import('@/views/cold_archive/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    { path: '/raw_ingest', name: 'raw_ingest', component: RawIngest },
    { path: '/column_mapping', name: 'column_mapping', component: ColumnMapping },
    { path: '/cleanse_rule', name: 'cleanse_rule', component: CleanseRule },
    { path: '/dedup_config', name: 'dedup_config', component: DedupConfig },
    { path: '/ods_layer', name: 'ods_layer', component: OdsLayer },
    { path: '/dwd_layer', name: 'dwd_layer', component: DwdLayer },
    { path: '/dws_layer', name: 'dws_layer', component: DwsLayer },
    { path: '/dim_model', name: 'dim_model', component: DimModel },
    { path: '/snapshot_mgr', name: 'snapshot_mgr', component: SnapshotMgr },
    { path: '/partition_mgr', name: 'partition_mgr', component: PartitionMgr },
    { path: '/quality_check', name: 'quality_check', component: QualityCheck },
    { path: '/lineage_track', name: 'lineage_track', component: LineageTrack },
    { path: '/backfill_job', name: 'backfill_job', component: BackfillJob },
    { path: '/table_compare', name: 'table_compare', component: TableCompare },
    { path: '/schema_registry', name: 'schema_registry', component: SchemaRegistry },
    { path: '/schema_version_view', name: 'schema_version_view', component: SchemaVersionView },
    { path: '/data_publish', name: 'data_publish', component: DataPublish },
    { path: '/transform_dag', name: 'transform_dag', component: TransformDag },
    { path: '/cold_archive', name: 'cold_archive', component: ColdArchive },
  ],
})

export default router
