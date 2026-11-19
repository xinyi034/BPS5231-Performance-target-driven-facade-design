# 自动化代码入口索引

## 批量运行入口
`scripts/run_facadeai_rhino.py`
- `main()`：初始化运行环境、打开GHX、关闭旧控制开关、循环指定Index。
- `verify_selected_case()`：核对Grasshopper当前选中的设计参数。
- `verify_export()`：等待并核验新生成的HBJSON和OSW。
- `call_case_runner()`：调用外部Python运行单组处理器。

## 单组处理
`scripts/facadeai_case.py`
- `main()`：检查断点、判断是否已有可复用结果、启动单组pipeline、写CSV和Excel。
- `read_result_rows()`：按design_id恢复已有结果。
- `write_csv()`：原子写入CSV checkpoint。
- `sync_workbook()`：按design_id回写Excel。

## 模拟与SQL验证
`scripts/facadeai_pipeline.py`
- `read_cases()`：检查160行输入与Index 80安全锚点。
- `read_hbjson_identity()` / `workflow_references()`：检查模型身份与OSW引用。
- `run_case()`：调用OpenStudio运行workflow。
- `verify_energyplus_run()`：检查完成标记、日志严重错误和SQL新鲜度。
- `extract_sql()`：从EnergyPlus SQL提取面积、总场地能耗并计算EUI。
- `verified_resume_row()`：决定是否允许跳过已完成案例。

## 结果汇总与预检
- `scripts/assemble_results.py`：合并两种来源，保留数据来源标签。
- `scripts/validate_package.py`：运行前检查文件、依赖、索引和结果一致性。
