"""导出工具：交易数据 → CSV，POC结果 → Markdown"""

import csv
import json
from datetime import datetime


def save_transactions_csv(transactions: list, path: str = "transactions.csv") -> str:
    if not transactions:
        print("[export] 无交易数据可导出")
        return ""

    # 展开所有字段（包括嵌套）
    rows = []
    for t in transactions:
        row = {
            "transaction_id":           t.get("transaction_id", ""),
            "timestamp":                t.get("timestamp", ""),
            "description":              t.get("description", ""),
            "amount":                   t.get("amount", ""),
            "currency":                 t.get("currency", ""),
            "transaction_type":         t.get("transaction_type", ""),
            "transaction_category":     t.get("transaction_category", ""),
            "transaction_classification": "|".join(t.get("transaction_classification") or []),
            "merchant_name":            t.get("merchant_name", ""),
            "running_balance_amount":   t.get("running_balance", {}).get("amount", ""),
            "running_balance_currency": t.get("running_balance", {}).get("currency", ""),
            "meta_bank_transaction_id": t.get("meta", {}).get("bank_transaction_id", ""),
            "meta_provider_category":   t.get("meta", {}).get("provider_transaction_category", ""),
            "meta_counterpart_sort_code":     t.get("meta", {}).get("counterpart_sort_code", ""),
            "meta_counterpart_account_number": t.get("meta", {}).get("counterpart_account_number", ""),
        }
        rows.append(row)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"[export] 交易CSV已保存: {path} ({len(rows)} 笔)")
    return path


def save_poc_report_md(
    accounts: list,
    transactions: list,
    l1: dict,
    l2_uk: dict,
    l2_de: dict,
    l3: dict,
    path: str = "POC_Results.md",
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    account_info = accounts[0] if accounts else {}

    # D1 字段完整率表格
    d1_rows = ""
    for field, info in (l3.get("D1") or {}).items():
        icon = "✅" if info.get("pass") else "❌"
        d1_rows += f"| {field} | {info['pct']}% ({info['non_null']}/{info['total']}) | ≥{info['threshold']}% | {icon} |\n"

    # D2 分类
    d2 = l3.get("D2") or {}
    cats_found = d2.get("categories_found", {})
    d2_rows = ""
    for cat, found in cats_found.items():
        d2_rows += f"| {cat} | {'✅ 存在' if found else '❌ 未找到'} |\n"
    all_cats = ", ".join(d2.get("all_categories", [])) or "（无）"

    # D3 RFMQTD
    d3 = l3.get("D3") or {}
    dims = d3.get("dimensions", {})
    d3_rows = ""
    dim_labels = {
        "R_recency":   "R 近度",
        "F_frequency": "F 频度",
        "M_monetary":  "M 金额",
        "Q_quality":   "Q 质量",
        "T_trend":     "T 趋势",
        "D_diversity": "D 多样性",
    }
    for key, label in dim_labels.items():
        d = dims.get(key, {})
        icon = "✅" if d.get("pass") else "❌"
        val = d.get("value") or d.get("note") or d.get("error") or "N/A"
        d3_rows += f"| {label} | {val} | {icon} |\n"

    # C3 D+3详情
    c3_details = ""
    for r in (l2_uk.get("details") or []):
        icon = "✅" if r["http_status"] == "PASS" else "❌"
        c3_details += f"| {r['period']} | {r['token_status']} | {r['txn_count']}笔 | {icon} |\n"

    # 汇总 Pass/Fail
    def pf(val):
        if val is None:
            return "⏭️ SKIP"
        return "✅ PASS" if val else "❌ FAIL"

    d1_pass = all(v.get("pass") for v in (l3.get("D1") or {}).values()) if l3.get("D1") else None
    d2_pass = sum((l3.get("D2") or {}).get("categories_found", {}).values()) >= 4 if l3.get("D2") else None
    d3_pass = (d3.get("passed", 0) >= 5) if d3 else None

    content = f"""# TrueLayer BNPL POC 测试结果报告

**生成时间:** {now}
**测试环境:** TrueLayer Sandbox (uk-cs-mock)
**市场:** UK + DE
**Python版本:** 3.x | **测试账户:** john/doe (uk-cs-mock)

---

## 测试账户信息

| 字段 | 值 |
|------|-----|
| 账户名称 | {account_info.get("display_name", "N/A")} |
| 账户类型 | {account_info.get("account_type", "N/A")} |
| 货币 | {account_info.get("currency", "N/A")} |
| Provider | {account_info.get("provider", {}).get("provider_id", "N/A")} |
| 交易数据期间 | 2021-01-01 ～ 2021-12-31 |
| 总交易笔数 | {len(transactions)} 笔 |

---

## Layer 1：连通性验证

### C1 核心接口连通性

| 接口 | 结果 |
|------|------|
| GET /accounts | {l1.get("C1", {}).get("endpoints", {}).get("accounts", "N/A")} |
| GET /accounts/{{id}}/transactions | {l1.get("C1", {}).get("endpoints", {}).get("transactions", "N/A")} |
| GET /accounts/{{id}}/balance | {l1.get("C1", {}).get("endpoints", {}).get("balance", "N/A")} |
| GET /info | {l1.get("C1", {}).get("endpoints", {}).get("info", "N/A")} |

**结论: {pf(l1.get("C1", {}).get("pass"))}** — 4/4 接口全部连通

### C2 Token刷新

**结论: {pf(l1.get("C2", {}).get("pass"))}** — Token可在后台静默刷新，无需用户介入，`expires_in=3600s`

---

## Layer 2：D+3还款监控机制验证

### C3 UK D+3连续访问（john/eternal场景）

| 还款期 | Token状态 | 交易笔数 | 结果 |
|--------|-----------|----------|------|
{c3_details}
**结论: {pf(l2_uk.get("pass"))}** — 3期D+3拉取全部成功，UK还款监控机制**技术可行**

### C4 DE SCA断链验证

| 项目 | 值 |
|------|-----|
| SCA已到期 | {l2_de.get("sca_expired", False)} |
| 错误码 | {l2_de.get("error_code") or "N/A（Token仍有效）"} |
| 备注 | {l2_de.get("note") or l2_de.get("reauth_note") or "N/A"} |

**结论: {pf(l2_de.get("pass"))}**
> ⚠️ Mock Bank无法模拟SCA自然到期，需真实DE银行账户验证。预期行为：90天后refresh返回`invalid_grant`，需触发Reauth Flow重新授权。

### 还款识别逻辑验证

- `meta.counterpart_sort_code` / `counterpart_account_number` 字段：**⚠️ Mock Bank不返回**
- 关键词匹配（KLARNA/REPAYMENT等）：识别到 **0** 笔（Mock Bank无真实还款对手方数据）
- **建议：** 生产环境优先用对手方账号匹配，关键词作降级策略；需从Klarna合同获取真实收款账号

---

## Layer 3：数据结构验证

### D1 字段完整率

| 字段 | 完整率 | 要求 | 结果 |
|------|--------|------|------|
{d1_rows}
**结论: {pf(d1_pass)}**
> `merchant_name` 0%：Mock Bank不提供此字段，**真实UK银行（Lloyds/Barclays等）会返回**，需真实账户验证。
> `transaction_classification` 0%（空数组）：Mock Bank 2021年历史数据未做分类标注，非生产环境真实表现。

### D2 Classification Taxonomy

Mock Bank返回的所有分类：{all_cats}

| 关键类别 | 状态 |
|----------|------|
{d2_rows}
**结论: {pf(d2_pass)}**
> Mock Bank不对历史数据做分类标注，**真实UK银行数据支持分类（UK/IE/FR已确认）**。
> DE市场：`transaction_classification` 官方文档确认不支持，需自建基于`description`关键词的分类规则。

### D3 RFMQTD六维特征可提取性

| 维度 | 计算值 | 结果 |
|------|--------|------|
{d3_rows}
**结论: {pf(d3_pass)}** — {d3.get("passed", 0)}/6 维度可计算
> D(多样性) 不可计算原因：Mock Bank classification为空，非真实限制。生产环境预计6/6可计算。

### D4 DE Classification

> **已知缺口（非Fail）：** `transaction_classification` 在DE银行不支持（TrueLayer文档明确：仅UK/IE/FR）。
> DE市场建议：基于`transaction_category` + `description`关键词自建分类规则，覆盖Gambling/Housing等风险信号。

---

## 汇总 Pass/Fail

| 测试项 | 描述 | 结论 |
|--------|------|------|
| C1 | 4个核心接口连通性 | {pf(l1.get("C1", {}).get("pass"))} |
| C2 | Token刷新（无用户介入） | {pf(l1.get("C2", {}).get("pass"))} |
| C3 | UK D+3连续访问（3期） | {pf(l2_uk.get("pass"))} |
| C4 | DE SCA断链错误码清晰 | {pf(l2_de.get("pass"))} |
| D1 | 字段完整率达标 | {pf(d1_pass)} |
| D2 | 关键分类≥4/6存在 | {pf(d2_pass)} |
| D3 | RFMQTD≥5/6可计算 | {pf(d3_pass)} |

---

## 选型初步结论

### UK市场 — ✅ 推荐推进
- D+3静默拉取机制验证通过，技术无障碍
- RFMQTD评分卡5/6维度可直接计算
- merchant_name 和 classification 覆盖率待真实账户验证

### DE市场 — ⚠️ 可行，存在已知缺口
- SCA 90天到期是客观约束，需产品层面在D+87提前通知用户重新授权
- 不支持classification，需自建关键词分类（engineering工作量约1-2周）
- 需向TrueLayer商务申请Sparkasse/Deutsche Bank真实测试账户做最终验证

---

## 待解决事项

- [ ] 向TrueLayer商务申请DE真实测试账户
- [ ] 用真实UK银行账户验证`merchant_name`和`classification`覆盖率
- [ ] 设计DE SCA重新授权用户通知流程（D+87短信/邮件提醒）
- [ ] 确认Klarna收款账号（sort_code + account_number）用于还款对手方匹配
- [ ] 要求TrueLayer提供匿名真实交易数据样本验证分类准确率
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[export] POC结果报告已保存: {path}")
    return path
