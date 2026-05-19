# TrueLayer BNPL POC — 待确认问题清单（Q&A）

**发起方:** POC Team
**日期:** 2025-05
**背景:** 基于 Sandbox POC 测试结果（uk-cs-mock，1788笔交易），整理需向 TrueLayer 澄清的关键问题

---

## 一、数据字段覆盖率（高优先级）

**Q1: `merchant_name` 在真实 UK 银行的覆盖率是多少？**

POC 中 Mock Bank 未返回 `merchant_name`（0%）。该字段用于还款识别辅助和 IBS 特征提取。
- 主流 UK 银行（Lloyds、Barclays、HSBC、Monzo、Starling）的实际覆盖率各是多少？
- 是否有按银行维度的字段覆盖率文档或数据样本？

---

**Q2: `transaction_classification` 在真实 UK 银行的覆盖率和准确率？**

Mock Bank 返回空数组，无法验证分类质量。
- 主流 UK 银行的 `transaction_classification` 实际填充率？
- Gambling、Housing、Income 等关键类别在真实数据中的识别准确率大概是多少？
- 是否可提供一份匿名脱敏的真实交易样本（≥500笔）供内部验证？

---

**Q3: `meta.counterpart_sort_code` / `counterpart_account_number` 哪些 UK 银行会返回？**

还款识别的最优策略是对手方账号精确匹配，但 Mock Bank 未返回此字段。
- 请提供支持返回 counterpart 字段的 UK 银行列表
- 如主流银行均不返回，关键词匹配是否为唯一可靠手段？

---

## 二、DE 市场（高优先级）

**Q4: 能否提供 DE 真实银行的测试账户？**

Sandbox 只有 `uk-cs-mock`，无法验证 DE 银行真实行为。
- 能否开通 Sparkasse 或 Deutsche Bank 的 Sandbox / Public Beta 测试账户？
- DE 主流银行（Sparkasse、Deutsche Bank、Commerzbank）的字段覆盖情况如何，特别是 `running_balance` 和 `meta.counterpart_iban`？

---

**Q5: DE 市场 SCA 到期的完整错误流程和 Reauth 机制？**

POC 中无法模拟 SCA 自然到期（需等 token 过期约 90 天）。
- Token 到期后 refresh 返回的具体 HTTP 状态码和 error body 格式？
- Reauth Flow 的标准实现方式（`/reauthuri` 端点的参数和返回格式）？
- 用户完成 Reauth 后，旧的 `account_id` 是否保持不变，历史数据是否仍可访问？

---

**Q6: DE 各银行的历史交易数据深度？**

文档提到部分 DE 银行（如 Volksbanken）仅支持 90 天历史数据。
- 请提供主要 DE 银行的历史数据深度列表（Sparkasse、Deutsche Bank、ING、Commerzbank）
- BNPL D+3 监控需持续访问数据，90 天限制是否影响长期运营？

---

## 三、生产环境稳定性

**Q7: 交易数据的延迟和刷新频率？**

D+3 监控要求在还款日能及时拿到当天出账数据。
- 交易数据从银行到 TrueLayer API 的典型延迟是多少（实时/T+1/T+2）？
- 是否支持 Webhook 推送新交易事件，避免轮询？

---

**Q8: API 速率限制和并发能力？**

BNPL 业务在还款日会批量拉取大量用户数据。
- 单账户的调用频率上限？
- 多账户并发调用的 QPS 上限？
- 是否有批量拉取接口（Batch API）？

---

## 四、商务与合规

**Q9: 生产环境接入的前置条件和审核周期？**

- 从 Sandbox 升级到 Production 需要哪些资质文件（营业执照、FCA 授权等）？
- 审核周期大概多久？

---

**Q10: 数据使用授权范围？**

- 用户通过 OAuth 授权后，数据可存储多久？
- 是否允许将交易数据用于信用评分模型训练？
- GDPR / UK GDPR 合规责任如何划分（Controller vs Processor）？

---

---

## 五、Risk Insights API（高优先级）

**Q11: Financial Risk Insights 是否为独立付费产品？如何开通？**

TrueLayer 文档中提及 Insights API，但相关页面需登录访问。
- Risk Insights 是否需要单独签合同或开通额外权限？
- 对应的 OAuth scope 名称是什么（如 `insights` / `risk_insights`）？
- Sandbox 环境是否支持 Risk Insights 端点？

---

**Q12: Risk Insights API 返回哪些字段？**

目前我们通过 `/transactions` 数据自建了以下代理指标：
- 收入稳定性（月收入变异系数 CV）
- 透支风险（负余额占比）
- 赌博行为（classification + 关键词双策略）
- 还款能力（月均净现金流）
- 账户活跃度

请确认官方 Risk Insights API 是否提供上述指标的标准化版本，以及是否有额外字段（如信用评分、欺诈风险分、收入来源分类等）？

---

## 优先级汇总

| 问题 | 优先级 | 影响 |
|------|--------|------|
| Q1 merchant_name 覆盖率 | 🔴 高 | IBS 特征工程 |
| Q2 classification 准确率 + 样本数据 | 🔴 高 | IBS 评分卡质量 |
| Q3 counterpart 字段支持银行列表 | 🔴 高 | 还款识别准确率 |
| Q4 DE 真实测试账户 | 🔴 高 | DE 市场可行性最终验证 |
| Q5 DE SCA Reauth 完整流程 | 🔴 高 | DE D+3 机制设计 |
| Q6 DE 历史数据深度 | 🟡 中 | DE 长期运营规划 |
| Q7 数据延迟 + Webhook | 🟡 中 | D+3 实时性 |
| Q8 速率限制 + 并发 | 🟡 中 | 生产容量规划 |
| Q9 Production 接入条件 | 🟡 中 | 项目排期 |
| Q10 数据使用授权 + GDPR | 🟢 低 | 合规备案 |
| Q11 Risk Insights 开通方式 + scope | 🔴 高 | 风险决策能力 |
| Q12 Risk Insights 字段清单 | 🔴 高 | 评分卡设计 |
