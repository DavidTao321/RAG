---
description: 叫出 quality-engineer 专职助手做代码质量检查（安全审计/注释体检/其它质量扫描）
---

调用 Agent 工具（subagent_type: quality-engineer）处理用户本次的质量检查需求，把检查范围交代清楚（用户指定文件/目录还是全项目）；quality-engineer 会先加载 security-audit 与 comments-check 两个技能手册再动手，默认只出报告不改代码，完成后把它的质量工程师报告原样转达给用户。
