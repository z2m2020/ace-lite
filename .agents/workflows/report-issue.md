# 问题反馈工作流

## 目标

提供一条低摩擦、可重复执行的路径，把运行时痛点沉淀为结构化 issue 资产。

## 快速路径

1. 先记录业务侧 issue report：

```
ace-lite feedback report-issue \
  --title "<short title>" \
  --query "<query text>" \
  --repo "<repo>" \
  --actual-behavior "<observed behavior>"
```

2. 如果这是工具链或运行时缺陷，再镜像到 developer issue：

```
ace-lite feedback report-dev-issue \
  --title "<same title>" \
  --reason-code general \
  --repo "<repo>"
```

3. 当 fix 或缓解措施可用时，记录并关联 fix：

```
ace-lite feedback report-dev-fix \
  --reason-code general \
  --repo "<repo>" \
  --resolution-note "<what changed>"

ace-lite feedback apply-dev-fix \
  --issue-id "<dev issue id>" \
  --fix-id "<dev fix id>"
```

4. 最后用 dev fix 反向关闭关联 issue report：

```
ace-lite feedback resolve-issue-from-dev-fix \
  --issue-id "<issue report id>" \
  --fix-id "<dev fix id>"
```

## 建议模板字段

- `title`
- `query`
- `actual_behavior`
- `expected_behavior`
- `category`
- `severity`
- `repro_steps`
- `attachments`
