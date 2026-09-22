# Stage 3 逐条审核工具

双击 formal_experiment/START_STAGE3_REVIEW.cmd，或运行：

    python formal_experiment/scripts/stage3_binding_review_tool.py

每次看一条，点“确认并下一条”自动保存。下拉框可改动作和执行者，备注可不填；无法对应的引用可以留空。“不接受并下一条”也会记录你的明确决定。“跳过 / 下一条”不记为已审核。

关闭后再打开，自动到第一条未审核项。30 条都有明确决定后直接显示“审核完成”，无需额外导出。上一条可返回修改。

结果自动保存在 data/development/human_review/stage3_binding_review_decisions_v1.json；覆盖前保存上一版至同目录的 stage3_binding_review_backups/。程序启动、浏览和跳过不会创建人工决定。原 proposal、blank、benchmark、Gold 不修改。

顺序项默认只确认流程先后。只有你主动选择“我确认法规要求这个先后顺序”，并选定两个不同的现有规则动作，才记录法规顺序。审核完成表示 30 条意见均已记录，允许接受空引用或拒绝候选，不自动声明绑定齐全或发布 Gold。

仅依赖 Python 自带的 tkinter；无网络、LLM/API 或 .env 读取。进度绑定本次审核稿与 blank 的原始文件 SHA256；源文件变化或另一窗口保存时拒绝覆盖。
