---
name: dummy-writer
description: A minimal skill for testing the evolution framework. Generates a structured markdown report.
---

# Dummy Writer

Generate a markdown report file at the requested path. The report must have three sections.

## Required Sections

The output file must contain these three H2 sections in order:

1. **## 摘要** — A one-paragraph executive summary (at least 3 sentences, no more than 5)
2. **## 分析** — Analysis with at least 2 bullet points using `- ` format
3. **## 建议** — Recommendations with at least 2 numbered items using `1. ` format

## Format Rules

- Each section title must use exactly `## ` prefix
- Sections must appear in the order: 摘要, 分析, 建议
- No extra H2 sections beyond these three
- The file must be valid markdown

## Content Quality

- 摘要 must be specific, not generic. Avoid phrases like "这是一个很重要的主题"
- 分析 bullet points must each start with a bold key insight: `- **关键词**：具体分析`
- 建议 must be actionable (can be executed, not abstract principles)
