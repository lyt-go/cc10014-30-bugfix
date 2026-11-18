"""接口出入参模型：列表分页、动作结果与各模块的明细结构。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    """登记或修改一条业务记录时提交的字段集合。"""

    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class ActionPayload(BaseModel):
    """状态动作使用独立契约，避免与登记的 values 载荷混用。"""

    action: str
    remark: str | None = None



class RawIngestEntry(BaseModel):
    """入库批次明细结构。"""

    field_0: str | None = None  # 批次编号
    field_1: str | None = None  # 来源系统
    field_2: str | None = None  # 文件格式
    field_3: str | None = None  # 原始行数
    field_4: str | None = None  # 入库时间
    field_5: str | None = None  # 字符编码
    field_6: str | None = None  # 校验摘要
    field_7: str | None = None  # 落地路径

class ColumnMappingEntry(BaseModel):
    """映射规则明细结构。"""

    field_0: str | None = None  # 规则编号
    field_1: str | None = None  # 源字段名
    field_2: str | None = None  # 目标字段名
    field_3: str | None = None  # 数据类型
    field_4: str | None = None  # 默认值
    field_5: str | None = None  # 转换函数
    field_6: str | None = None  # 规则版本
    field_7: str | None = None  # 生效日期

class CleanseRuleEntry(BaseModel):
    """清洗策略明细结构。"""

    field_0: str | None = None  # 策略编号
    field_1: str | None = None  # 目标字段
    field_2: str | None = None  # 空值处理
    field_3: str | None = None  # 异常阈值
    field_4: str | None = None  # 正则表达式
    field_5: str | None = None  # 替换值
    field_6: str | None = None  # 策略版本
    field_7: str | None = None  # 执行顺序

class DedupConfigEntry(BaseModel):
    """去重配置明细结构。"""

    field_0: str | None = None  # 配置编号
    field_1: str | None = None  # 业务键列
    field_2: str | None = None  # 排序字段
    field_3: str | None = None  # 保留策略
    field_4: str | None = None  # 时间窗口
    field_5: str | None = None  # 相似度阈值
    field_6: str | None = None  # 配置版本
    field_7: str | None = None  # 目标数据集

class OdsLayerEntry(BaseModel):
    """贴源表明细结构。"""

    field_0: str | None = None  # 表编号
    field_1: str | None = None  # 来源系统
    field_2: str | None = None  # 表名称
    field_3: str | None = None  # 分区字段
    field_4: str | None = None  # 存储格式
    field_5: str | None = None  # 保留天数
    field_6: str | None = None  # 压缩算法
    field_7: str | None = None  # 创建批次

class DwdLayerEntry(BaseModel):
    """明细表明细结构。"""

    field_0: str | None = None  # 表编号
    field_1: str | None = None  # 父层来源
    field_2: str | None = None  # 表名称
    field_3: str | None = None  # 粒度说明
    field_4: str | None = None  # 分区字段
    field_5: str | None = None  # 关联键列
    field_6: str | None = None  # 刷新水位
    field_7: str | None = None  # 创建批次

class DwsLayerEntry(BaseModel):
    """汇总表明细结构。"""

    field_0: str | None = None  # 表编号
    field_1: str | None = None  # 统计粒度
    field_2: str | None = None  # 汇总维度
    field_3: str | None = None  # 度量字段
    field_4: str | None = None  # 聚合函数
    field_5: str | None = None  # 时间范围
    field_6: str | None = None  # 刷新周期
    field_7: str | None = None  # 创建批次

class DimModelEntry(BaseModel):
    """维度模型明细结构。"""

    field_0: str | None = None  # 模型编号
    field_1: str | None = None  # 维度名称
    field_2: str | None = None  # 自然键列
    field_3: str | None = None  # 代理键列
    field_4: str | None = None  # 缓慢变化策略
    field_5: str | None = None  # 生效日期
    field_6: str | None = None  # 失效日期
    field_7: str | None = None  # 刷新周期

class SnapshotMgrEntry(BaseModel):
    """数据快照明细结构。"""

    field_0: str | None = None  # 快照编号
    field_1: str | None = None  # 目标数据集
    field_2: str | None = None  # 快照时间
    field_3: str | None = None  # 数据行数
    field_4: str | None = None  # 存储路径
    field_5: str | None = None  # 压缩算法
    field_6: str | None = None  # 保留天数
    field_7: str | None = None  # 快照版本

class PartitionMgrEntry(BaseModel):
    """分区策略明细结构。"""

    field_0: str | None = None  # 策略编号
    field_1: str | None = None  # 目标表名
    field_2: str | None = None  # 分区字段
    field_3: str | None = None  # 分区粒度
    field_4: str | None = None  # 保留天数
    field_5: str | None = None  # 冷热阈值
    field_6: str | None = None  # 预建数量
    field_7: str | None = None  # 目录规则

class QualityCheckEntry(BaseModel):
    """稽核规则明细结构。"""

    field_0: str | None = None  # 规则编号
    field_1: str | None = None  # 校验表名
    field_2: str | None = None  # 校验字段
    field_3: str | None = None  # 校验表达式
    field_4: str | None = None  # 阈值下界
    field_5: str | None = None  # 阈值上界
    field_6: str | None = None  # 阻断级别
    field_7: str | None = None  # 采样比例

class LineageTrackEntry(BaseModel):
    """血缘链路明细结构。"""

    field_0: str | None = None  # 链路编号
    field_1: str | None = None  # 上游表名
    field_2: str | None = None  # 下游表名
    field_3: str | None = None  # 来源字段
    field_4: str | None = None  # 目标字段
    field_5: str | None = None  # 转换逻辑
    field_6: str | None = None  # 采集批次
    field_7: str | None = None  # 链路版本

class BackfillJobEntry(BaseModel):
    """补数任务明细结构。"""

    field_0: str | None = None  # 任务编号
    field_1: str | None = None  # 目标表名
    field_2: str | None = None  # 起始日期
    field_3: str | None = None  # 截止日期
    field_4: str | None = None  # 并行度
    field_5: str | None = None  # 覆盖策略
    field_6: str | None = None  # 完成水位
    field_7: str | None = None  # 失败区间

class TableCompareEntry(BaseModel):
    """比对任务明细结构。"""

    field_0: str | None = None  # 任务编号
    field_1: str | None = None  # 左表名称
    field_2: str | None = None  # 右表名称
    field_3: str | None = None  # 比对字段
    field_4: str | None = None  # 比对方式
    field_5: str | None = None  # 差异阈值
    field_6: str | None = None  # 采样比例
    field_7: str | None = None  # 比对批次

class SchemaRegistryEntry(BaseModel):
    """结构定义明细结构。"""

    field_0: str | None = None  # 定义编号
    field_1: str | None = None  # 表名称
    field_2: str | None = None  # 字段名称
    field_3: str | None = None  # 字段类型
    field_4: str | None = None  # 可空标识
    field_5: str | None = None  # 默认值
    field_6: str | None = None  # 定义版本
    field_7: str | None = None  # 生效批次

class SchemaVersionViewEntry(BaseModel):
    """结构版本诊断记录明细结构。"""

    field_0: str | None = None  # 视图编号
    field_1: str | None = None  # 表名称
    field_2: str | None = None  # 定义版本
    field_3: str | None = None  # 自然顺序
    field_4: str | None = None  # 是否当前
    field_5: str | None = None  # 版本来源
    field_6: str | None = None  # 当前来源
    field_7: str | None = None  # 冲突标记


class DataPublishEntry(BaseModel):
    """发布版本明细结构。"""

    field_0: str | None = None  # 版本编号
    field_1: str | None = None  # 数据集名称
    field_2: str | None = None  # 发布范围
    field_3: str | None = None  # 查询参数
    field_4: str | None = None  # 响应字段
    field_5: str | None = None  # 缓存秒数
    field_6: str | None = None  # 分页上限
    field_7: str | None = None  # 消费应用

class TransformDagEntry(BaseModel):
    """转换节点明细结构。"""

    field_0: str | None = None  # 节点编号
    field_1: str | None = None  # 输入表名
    field_2: str | None = None  # 输出表名
    field_3: str | None = None  # 转换脚本
    field_4: str | None = None  # 执行顺序
    field_5: str | None = None  # 依赖节点
    field_6: str | None = None  # 失败策略
    field_7: str | None = None  # 调度周期

class ColdArchiveEntry(BaseModel):
    """归档策略明细结构。"""

    field_0: str | None = None  # 策略编号
    field_1: str | None = None  # 目标表名
    field_2: str | None = None  # 冷数据阈值
    field_3: str | None = None  # 归档路径
    field_4: str | None = None  # 压缩算法
    field_5: str | None = None  # 归档格式
    field_6: str | None = None  # 保留天数
    field_7: str | None = None  # 恢复超时
