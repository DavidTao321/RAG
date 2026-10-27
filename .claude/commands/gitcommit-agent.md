---
description: 带质量门禁存档：并行跑单元测试与质量检查，通过后 git-save 提交推送
---

调用 Agent 工具（subagent_type: gitcommit-agent）处理本次存档需求；它会先并行派发 tester 与 quality-engineer 检查（不通过自动修复一轮再复检），两个门禁标记都通过后走 git-save 技能提交推送，完成后把结果原样转达给用户。
