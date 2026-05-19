"""
Risk Proxy 模块：在 TrueLayer Insights API 未开通时，
用现有 /transactions 数据自行计算风险代理指标。

覆盖信号：
  - 收入稳定性（Income Stability）
  - 透支风险（Overdraft Risk）
  - 赌博行为（Gambling Signal）
  - 还款能力（Repayment Capacity）
  - 账户活跃度（Account Activity）
"""

from datetime import datetime


def analyse_risk(transactions: list, balance: dict) -> dict:
    """
    输入: transactions（/transactions 返回列表）, balance（/balance 返回）
    输出: 风险代理指标字典
    """
    print("\n[Risk] 风险代理指标计算")
    results = {}

    credits = [t for t in transactions if t.get("amount", 0) > 0]
    debits  = [t for t in transactions if t.get("amount", 0) < 0]

    # ── 1. 收入稳定性 ─────────────────────────────────────
    monthly_income = {}
    for t in credits:
        m = t.get("timestamp", "")[:7]
        monthly_income[m] = monthly_income.get(m, 0) + t.get("amount", 0)

    if len(monthly_income) >= 2:
        vals = list(monthly_income.values())
        mean = sum(vals) / len(vals)
        std  = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
        cv   = round(std / mean, 3) if mean else None
        stability = "稳定" if cv is not None and cv < 0.3 else "波动"
        results["income_stability"] = {
            "monthly_avg": round(mean, 2),
            "cv": cv,
            "signal": stability,
            "pass": cv is not None and cv < 0.3,
        }
        icon = "✅" if results["income_stability"]["pass"] else "⚠️ "
        print(f"  {icon} 收入稳定性: 月均 {mean:.2f}, CV={cv} → {stability}")
    else:
        results["income_stability"] = {"signal": "数据不足", "pass": False}
        print("  ❌ 收入稳定性: 月收入数据不足（需≥2个月）")

    # ── 2. 透支风险 ───────────────────────────────────────
    balances = [t.get("running_balance", {}).get("amount")
                for t in transactions if t.get("running_balance")]
    balances = [b for b in balances if b is not None]

    if balances:
        negative_days = sum(1 for b in balances if b < 0)
        min_balance   = min(balances)
        overdraft_rate = round(negative_days / len(balances) * 100, 1)
        risk_level = "高" if overdraft_rate > 10 else ("中" if overdraft_rate > 3 else "低")
        results["overdraft_risk"] = {
            "negative_balance_pct": overdraft_rate,
            "min_balance": min_balance,
            "risk_level": risk_level,
            "pass": overdraft_rate <= 3,
        }
        icon = "✅" if results["overdraft_risk"]["pass"] else "⚠️ "
        print(f"  {icon} 透支风险: 负余额占比 {overdraft_rate}%，最低余额 {min_balance:.2f} → 风险{risk_level}")
    else:
        results["overdraft_risk"] = {"signal": "running_balance字段缺失", "pass": None}
        print("  ⚠️  透支风险: running_balance 字段不可用")

    # ── 3. 赌博行为 ───────────────────────────────────────
    gambling_txns = []
    for t in transactions:
        # 方式1: classification 字段
        if "Gambling" in (t.get("transaction_classification") or []):
            gambling_txns.append({**t, "_detected_by": "classification"})
            continue
        # 方式2: description 关键词
        desc = t.get("description", "").upper()
        if any(k in desc for k in ["BET365", "BETWAY", "PADDY POWER", "LADBROKES",
                                    "BETFAIR", "WILLIAM HILL", "CASINO", "GAMBLING",
                                    "LOTTERY", "FLUTTER"]):
            gambling_txns.append({**t, "_detected_by": "keyword"})

    gambling_amount = sum(abs(t.get("amount", 0)) for t in gambling_txns)
    total_debit = sum(abs(t.get("amount", 0)) for t in debits)
    gambling_pct = round(gambling_amount / total_debit * 100, 2) if total_debit else 0

    results["gambling_signal"] = {
        "txn_count": len(gambling_txns),
        "total_amount": round(gambling_amount, 2),
        "pct_of_total_spend": gambling_pct,
        "pass": len(gambling_txns) == 0,
    }
    icon = "✅" if results["gambling_signal"]["pass"] else "🔴"
    print(f"  {icon} 赌博信号: {len(gambling_txns)} 笔，金额 {gambling_amount:.2f}，占总支出 {gambling_pct}%")

    # ── 4. 还款能力（D+3 窗口净余量）────────────────────────
    monthly_net = {}
    for t in transactions:
        m = t.get("timestamp", "")[:7]
        monthly_net[m] = monthly_net.get(m, 0) + t.get("amount", 0)

    if monthly_net:
        avg_net = round(sum(monthly_net.values()) / len(monthly_net), 2)
        current_balance = balance.get("current", 0) or 0
        results["repayment_capacity"] = {
            "monthly_avg_net_cashflow": avg_net,
            "current_balance": current_balance,
            "signal": "充裕" if avg_net > 0 and current_balance > 0 else "紧张",
            "pass": avg_net > 0,
        }
        icon = "✅" if results["repayment_capacity"]["pass"] else "⚠️ "
        print(f"  {icon} 还款能力: 月均净现金流 {avg_net:.2f}，当前余额 {current_balance:.2f} → {results['repayment_capacity']['signal']}")

    # ── 5. 账户活跃度 ─────────────────────────────────────
    months_active = len(set(t.get("timestamp", "")[:7] for t in transactions))
    avg_monthly_txn = round(len(transactions) / months_active, 1) if months_active else 0
    results["account_activity"] = {
        "months_active": months_active,
        "avg_monthly_txn": avg_monthly_txn,
        "total_txn": len(transactions),
        "pass": avg_monthly_txn >= 10,
    }
    icon = "✅" if results["account_activity"]["pass"] else "⚠️ "
    print(f"  {icon} 账户活跃度: {months_active} 个月，月均 {avg_monthly_txn} 笔")

    # ── 汇总 ──────────────────────────────────────────────
    passed = sum(1 for v in results.values() if isinstance(v, dict) and v.get("pass") is True)
    total  = sum(1 for v in results.values() if isinstance(v, dict) and v.get("pass") is not None)
    print(f"\n[Risk] 汇总: {passed}/{total} 项风险指标通过")
    print("[Risk] ⚠️  注：以上为 transaction 数据自建代理指标，非 TrueLayer 官方 Risk Insights API")

    return results
