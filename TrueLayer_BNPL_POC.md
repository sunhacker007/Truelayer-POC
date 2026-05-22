# TrueLayer Open Banking POC — BNPL专项
**版本:** v1.0 | **周期:** 2周 | **市场:** UK + DE | **密级:** 机密

---

## 0. 前置说明：Sandbox的边界与补偿策略

TrueLayer Sandbox **只提供一个Mock Bank**（`provider: uk-cs-mock`），不提供真实DE银行的沙盒环境。这意味着：

| 测试内容 | Sandbox可做？ | 说明 |
|---|---|---|
| OAuth2 flow / token获取 | ✅ | Mock Bank完整模拟 |
| API接口连通性 | ✅ | Sandbox endpoint与生产同结构 |
| 响应字段结构验证 | ✅ | Mock Bank返回标准字段 |
| DE银行SCA flow | ⚠️ | 需TrueLayer开通DE Sandbox账户，或直接用DE公测环境真实账户 |
| 分类准确率（真实噪音） | ❌ | Mock数据太干净，需真实匿名数据补充 |
| 跨银行覆盖差异 | ❌ | Sandbox只有Mock Bank一家 |

**补偿策略：**
- DE银行测试：向TrueLayer商务申请DE Sparkasse/Deutsche Bank的真实Sandbox账户，或在Public Beta环境用真实测试账户走一次完整flow
- 数据质量：要求TrueLayer提供真实匿名交易数据样本（商务谈判标准要求）
- 分类准确率：用公司内部已有的脱敏银行对账单手动调用enrichment接口验证

---

## 1. 环境准备（Day 1，前提）

### 1.1 账户开通
1. 注册 [TrueLayer Console](https://console.truelayer.com) Sandbox账户
2. 创建Application，记录 `client_id` 和 `client_secret`
3. 在Console → Permissions勾选以下scopes：
   - `accounts` `transactions` `balance` `offline_access` `info`
4. 注册 `redirect_uri`，例如 `https://localhost:3000/callback`
5. 下载 [Sandbox Postman Collection](https://docs.truelayer.com/docs/collections)

### 1.2 Mock用户说明
TrueLayer提供多组Mock凭据用于不同测试场景：

| Username | Password | 用途 |
|---|---|---|
| `john` | `doe` | 标准成功认证，返回示例交易数据 |
| `john` | `eternal` | 认证后`connection extend`返回`no_action_needed`（模拟UK永久token场景） |
| `john` | `iban` | 返回带有效IBAN的账户数据（DE场景模拟） |
| `john1`~`john100` | `doe1`~`doe100` | 多用户并发测试 |

> **POC关键选择：** D+3连续访问测试用`john/eternal`（模拟UK无需重认证场景）；DE SCA断链测试用`john/doe`（`connection extend`返回`authentication_needed`，模拟SCA到期）

---

## 2. 第一层：连通性验证（Day 1-2）

### 2.1 OAuth2完整Flow

**步骤：**

```
Step 1: 构建Auth Link
GET https://auth.truelayer-sandbox.com/
  ?response_type=code
  &client_id={client_id}
  &scope=accounts transactions balance offline_access info
  &redirect_uri=https://localhost:3000/callback
  &providers=uk-cs-mock
  &provider_id=uk-cs-mock   # 跳过银行选择页

Step 2: Mock Bank登录
用户名: john | 密码: doe

Step 3: 获取authorization_code（从redirect URL提取）

Step 4: 换取token
POST https://auth.truelayer-sandbox.com/connect/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&client_id={client_id}
&client_secret={client_secret}
&redirect_uri=https://localhost:3000/callback
&code={authorization_code}
```

**预期响应：**
```json
{
  "access_token": "eyJ...",
  "expires_in": 3600,
  "token_type": "Bearer",
  "refresh_token": "eyJ..."
}
```

**Pass标准：** HTTP 200，`access_token`和`refresh_token`均返回，`expires_in`= 3600

---

### 2.2 核心接口连通性

用获取的`access_token`依次调用：

```bash
# 账户列表
GET https://api.truelayer-sandbox.com/data/v1/accounts
Authorization: Bearer {access_token}

# 账户交易（关键：D+3拉取的核心接口）
GET https://api.truelayer-sandbox.com/data/v1/accounts/{account_id}/transactions
  ?from=2024-01-01T00:00:00
  &to=2024-01-31T23:59:59

# 余额
GET https://api.truelayer-sandbox.com/data/v1/accounts/{account_id}/balance

# 身份信息（AV用）
GET https://api.truelayer-sandbox.com/data/v1/info
```

**预期账户响应结构：**
```json
{
  "results": [{
    "account_id": "f1234560abf9f57287637624def390871",
    "account_type": "TRANSACTION",
    "display_name": "Club Lloyds",
    "currency": "GBP",
    "account_number": {
      "iban": "GB35LOYD12345678901234",
      "number": "12345678",
      "sort_code": "12-34-56"
    },
    "provider": { "provider_id": "uk-cs-mock" }
  }]
}
```

**Pass标准：** 4个接口全部返回HTTP 200，`account_id`可提取用于后续调用

---

### 2.3 Token刷新验证

```bash
POST https://auth.truelayer-sandbox.com/connect/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&client_id={client_id}
&client_secret={client_secret}
&refresh_token={refresh_token}
```

**Pass标准：** 返回新`access_token`，旧token无需用户重新登录

---

## 3. 第二层：D+3还款监控机制验证（Day 3-6）

> **核心问题：** 在BNPL还款日T+3，系统能否无需用户介入，后台静默拉取outflow交易？

### 3.1 UK：无感连续访问验证

**测试设计：**

用`john/eternal`登录（Connection extend返回`no_action_needed`），模拟UK FCA新规下的长期访问场景。

```python
# 模拟D+3连续访问脚本（连续3天，每天1次）
import requests, time

headers = {"Authorization": f"Bearer {access_token}"}
base_url = "https://api.truelayer-sandbox.com/data/v1"

for day in [30, 60, 90]:  # 模拟第1/2/3期还款日+3
    # 拉取还款日前后窗口的交易
    params = {
        "from": f"2024-{day-2:02d}T00:00:00",  # T-2
        "to":   f"2024-{day+3:02d}T23:59:59"   # T+3
    }
    r = requests.get(f"{base_url}/accounts/{account_id}/transactions",
                     headers=headers, params=params)
    print(f"Day {day}+3: HTTP {r.status_code}, txn count: {len(r.json()['results'])}")
    time.sleep(86400)  # 实际等待，POC中可压缩时间
```

**Pass标准：** 3次调用全部HTTP 200，无需用户重新认证

---

### 3.2 DE：SCA到期行为验证

用`john/doe`登录（Connection extend返回`authentication_needed`），模拟DE银行SCA到期后的断链场景。

```bash
# Step 1: 检查Connection状态
POST https://auth.truelayer-sandbox.com/connect/token
grant_type=refresh_token&...

# 预期响应（SCA到期模拟）：
# HTTP 400: { "error": "invalid_grant" }
# 或HTTP 200但connection_expired=true

# Step 2: 发起Reauth Flow
GET https://auth.truelayer-sandbox.com/reauthuri
  ?token={refresh_token}
  &redirect_uri=https://localhost:3000/callback
```

**记录：**
- SCA到期后API返回的错误码（`invalid_grant` / `access_denied`）
- Reauth Flow的步骤数（量化用户摩擦）
- 用户完成Reauth后数据访问是否恢复

**Pass标准：** 错误码清晰可程序化处理，Reauth后访问恢复；**结论是DE第3期（D90）存在必须处理的SCA断链**

---

### 3.3 还款转账识别逻辑验证

Mock Bank的预置交易含固定数据集。通过`/transactions`拉取后，验证以下识别逻辑：

```python
def is_repayment(txn, klarna_sort_code="12-34-56", klarna_account="12345678"):
    """
    识别策略（按优先级）：
    1. 对手方账号精确匹配（最可靠，需从Klarna合同获取真实账号）
    2. 描述字符串关键词匹配（次选）
    """
    # 策略1：对手方账号匹配（若银行返回此字段）
    meta = txn.get("meta", {})
    if (meta.get("counterpart_sort_code") == klarna_sort_code and
        meta.get("counterpart_account_number") == klarna_account):
        return True, "account_match"

    # 策略2：描述关键词
    desc = txn.get("description", "").upper()
    keywords = ["KLARNA", "CLEARPAY", "REPAYMENT", "INSTALMENT", "PAY IN 3"]
    if any(k in desc for k in keywords):
        return True, "keyword_match"

    return False, None

# 对outflow交易（amount < 0）逐一检查
transactions = response["results"]
outflows = [t for t in transactions if t["amount"] < 0]
repayments = [t for t in outflows if is_repayment(t)[0]]
```

**关键验证：** Mock Bank的`meta`字段是否返回`counterpart_sort_code`和`counterpart_account_number`。

> ⚠️ **已知限制：** TrueLayer文档显示`meta`字段内容因银行而异，Mock Bank可能不返回对手方账号。若不返回，记录为"需真实银行数据验证"，关键词匹配作为降级方案。

---

## 4. 第三层：数据结构验证（Day 7-9）

### 4.1 Transaction字段完整性审计

TrueLayer `/transactions`接口返回以下字段，subject to availability：

```json
{
  "transaction_id": "03c333979b729315545816aaa365c33f",
  "timestamp": "2018-03-06T00:00:00",
  "description": "GOOGLE PLAY STORE",
  "amount": -2.99,
  "currency": "GBP",
  "transaction_type": "DEBIT",
  "transaction_category": "PURCHASE",
  "transaction_classification": ["Entertainment", "Games"],
  "merchant_name": "Google play",
  "running_balance": { "amount": 1238.60, "currency": "GBP" },
  "meta": {
    "bank_transaction_id": "9882ks-00js",
    "provider_transaction_category": "DEB"
  }
}
```

**字段审计脚本：**

```python
import pandas as pd

def audit_fields(transactions):
    required_fields = [
        "transaction_id", "timestamp", "description",
        "amount", "currency", "transaction_type",
        "transaction_category", "transaction_classification",
        "merchant_name", "running_balance"
    ]
    df = pd.json_normalize(transactions)
    report = {}
    for f in required_fields:
        if f in df.columns:
            non_null = df[f].notna().sum()
            report[f] = f"{non_null}/{len(df)} ({non_null/len(df)*100:.0f}%)"
        else:
            report[f] = "❌ 字段不存在"
    return report
```

**Pass标准：**

| 字段 | 要求 | BNPL用途 |
|---|---|---|
| `amount` | 100%非空 | 收支判断 |
| `timestamp` | 100%非空 | D+3时间窗口过滤 |
| `transaction_type` | 100%非空 | DEBIT=outflow筛选 |
| `transaction_classification` | ≥70%非空 | IBS分类特征 |
| `merchant_name` | ≥60%非空 | 还款识别辅助 |
| `running_balance` | ≥80%非空 | 余额趋势T维度 |

---

### 4.2 Classification Taxonomy验证

`transaction_classification`字段目前仅支持UK、爱尔兰和法国的银行；DE银行会尝试用UK分类体系但准确率较低。

验证以下BNPL关键类别是否存在：

```python
# 从Mock Bank交易中提取所有出现的classification值
all_classifications = set()
for txn in transactions:
    for cls in txn.get("transaction_classification", []):
        all_classifications.add(cls)

# 检查关键类别
critical_categories = {
    "Gambling": "赌博识别（BNPL风险核心信号）",
    "Entertainment": "娱乐支出",
    "Bills and Utilities": "水电类固定支出",
    "Housing": "住房支出（偿付能力）",
    "Transfer": "转账（可能包含还款）",
    "Income": "收入识别",
}

for cat, purpose in critical_categories.items():
    status = "✅ 存在" if cat in all_classifications else "❌ 未找到"
    print(f"{status} | {cat} | {purpose}")
```

> **DE市场注意：** `transaction_classification`在DE银行支持度低，需向TrueLayer确认DE具体bank的分类覆盖情况。

---

### 4.3 IBS六维特征可提取性验证

```python
def extract_bnpl_features(transactions, balance_history):
    """验证RFMQTD六维是否可从TrueLayer数据计算"""
    import numpy as np
    from scipy import stats

    credits = [t for t in transactions if t["amount"] > 0]
    debits  = [t for t in transactions if t["amount"] < 0]

    results = {}

    # R - 近度：最近一笔收入距今天数
    if credits:
        latest_income = max(credits, key=lambda x: x["timestamp"])
        results["R_recency"] = "✅ 可计算"
    else:
        results["R_recency"] = "❌ 无收入记录"

    # F - 频度：月均交易笔数
    results["F_frequency"] = f"✅ 月均{len(transactions)/3:.0f}笔"

    # M - 金额：月均净现金流
    net = sum(t["amount"] for t in transactions) / 3
    results["M_monetary"] = f"✅ 月均净现金流: {net:.2f} GBP"

    # Q - 质量：收入变异系数
    monthly_incomes = [sum(t["amount"] for t in credits)]  # 简化
    if len(monthly_incomes) > 1:
        cv = np.std(monthly_incomes) / np.mean(monthly_incomes)
        results["Q_quality"] = f"✅ 收入CV={cv:.2f}"
    else:
        results["Q_quality"] = "⚠️ 需≥3个月数据"

    # T - 趋势：余额斜率（依赖running_balance）
    balances = [t.get("running_balance", {}).get("amount") for t in transactions]
    balances = [b for b in balances if b is not None]
    if len(balances) > 5:
        slope, _, _, _, _ = stats.linregress(range(len(balances)), balances)
        results["T_trend"] = f"✅ 余额斜率={slope:.2f}/期"
    else:
        results["T_trend"] = "❌ running_balance字段缺失或不足"

    # D - 多样性：活跃类别数
    categories = set(
        txn.get("transaction_classification", [None])[0]
        for txn in transactions
        if txn.get("transaction_classification")
    )
    results["D_diversity"] = f"✅ {len(categories)}个活跃类别"

    return results
```

**Pass标准：** ≥5/6维度可从Mock Bank数据计算出数值

---

## 5. DE市场补充测试（Day 8-10）

### 5.1 DE银行连接（需真实测试账户）

由于Sandbox只有Mock Bank，DE银行测试需要：

**方案A（推荐）：** 向TrueLayer商务申请开通DE Public Beta银行的测试账户访问权限，在sandbox-like环境测试Sparkasse/Deutsche Bank的OAuth flow

**方案B：** 在TrueLayer Console的Supported Providers页面，查询DE各银行的实际scope支持情况，与文件数据交叉验证

```bash
# 查询DE providers支持情况（需有效API token）
GET https://api.truelayer.com/api/providers?country=DE
Authorization: Bearer {access_token}

# 关注response中每个provider的scopes字段
# 预期：Sparkasse等返回 ["accounts", "transactions", "balance"]
# 注意：DE银行不返回 "transaction_classification"（文档已确认）
```

### 5.2 DE vs UK数据差异矩阵（结论汇总）

| 能力 | UK (Mock Bank测试) | DE (文档/需真实账户) |
|---|---|---|
| Transaction history | 可获取历史数据 | Volksbanken仅90天；Sparkasse 6年（首次） |
| `transaction_classification` | 支持，UK+IE+FR | **不支持**，TrueLayer文档明确 |
| `merchant_name` enrichment | 支持 | 不支持 |
| `running_balance` | 支持 | 依银行而定 |
| `meta.counterpart_*` | 部分银行支持 | 未知，需实测 |
| AV（Identity scope） | 部分银行支持 | **不在文件scope中** |

---

## 6. Pass/Fail判断标准汇总

| 测试项 | Pass标准 | Fail后果 |
|---|---|---|
| **C1** OAuth2 Flow | HTTP 200，token双返回 | 集成层问题，需修复后继续 |
| **C2** Token刷新 | 无用户介入完成刷新 | D+3机制不可行 |
| **C3** UK连续访问（90天内） | 3次D+3拉取全部200 | Y标签机制不可行 |
| **C4** DE SCA断链 | 错误码清晰，Reauth可用 | DE需运营补偿（90天前提醒用户） |
| **D1** 字段完整率 | amount/timestamp 100%；classification ≥70% | IBS特征工程受限 |
| **D2** 关键分类存在 | Gambling/Housing类别存在 | 赌博信号不可用，需自建 |
| **D3** RFMQTD | ≥5/6维度可计算 | IBS评分卡需重新设计 |
| **D4** DE classification | 确认不支持，有替代方案 | 已知缺口，非Fail |

---

## 7. 已知局限性与补偿建议

| 局限 | 原因 | 建议 |
|---|---|---|
| Mock Bank只有1家，无法测DE覆盖差异 | TrueLayer Sandbox只支持uk-cs-mock | 向TrueLayer申请DE真实测试账户 |
| `transaction_classification`在DE不支持 | 文档已明确UK/IE/FR only | DE市场自建分类规则（基于`description`关键词） |
| 还款对手方账号需从Klarna合同获取 | Mock Bank meta字段无真实counterpart数据 | 与Klarna BD团队明确收款账户IBAN/sort code |
| 分类准确率无法在Sandbox验证 | Mock数据干净，无真实噪音 | 要求TrueLayer提供匿名真实数据样本 |

---

## 8. 2周交付物清单

- [ ] **连通性报告：** 4个接口测试结果截图 + Pass/Fail
- [ ] **Token生命周期日志：** UK连续访问记录；DE SCA断链错误码记录
- [ ] **字段完整率报告：** `audit_fields()`输出表格
- [ ] **Classification Taxonomy清单：** Mock Bank返回的所有分类值
- [ ] **RFMQTD可提取性矩阵：** 6维逐一计算结果
- [ ] **DE vs UK差异矩阵：** 基于文档+实测的综合对比
- [ ] **选型初步结论：** UK/DE各市场的可行性判断 + 待解决事项清单
