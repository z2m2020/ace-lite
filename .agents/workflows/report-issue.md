# Issue Reporting Workflow

## Goal

Provide a low-friction, repeatable path for turning runtime pain points into structured issue assets.

## Fast Path

1. First record the business-facing issue report:

```
ace-lite feedback report-issue \
  --title "<short title>" \
  --query "<query text>" \
  --repo "<repo>" \
  --actual-behavior "<observed behavior>"
```

2. If this is a tooling or runtime defect, mirror it into a developer issue:

```
ace-lite feedback report-dev-issue \
  --title "<same title>" \
  --reason-code general \
  --repo "<repo>"
```

3. When a fix or mitigation is available, record it and link the fix:

```
ace-lite feedback report-dev-fix \
  --reason-code general \
  --repo "<repo>" \
  --resolution-note "<what changed>"

ace-lite feedback apply-dev-fix \
  --issue-id "<dev issue id>" \
  --fix-id "<dev fix id>"
```

4. Finally, use the dev fix to close the linked issue report:

```
ace-lite feedback resolve-issue-from-dev-fix \
  --issue-id "<issue report id>" \
  --fix-id "<dev fix id>"
```

## Suggested Template Fields

- `title`
- `query`
- `actual_behavior`
- `expected_behavior`
- `category`
- `severity`
- `repro_steps`
- `attachments`
