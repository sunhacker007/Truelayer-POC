"""
Layer 3: 数据结构验证

D1 — 字段完整率审计
D2 — Classification Taxonomy验证
D3 — RFMQTD六维特征可提取性
D4 — DE classification确认不支持（文档已知，记录即可）
"""

from datetime import datetime


# ── D1 字段完整率 ──────────────────────────────────────────────────────────

FIELD_THRESHOLDS = {
    "transaction_id":             100,
    "timestamp":                  100,
    "description":                100,
    "amount":                     100,
    "currency":                   100,
    "transaction_type":           100,
    "transaction_category":        80,
    "transaction_classification":  70,
    "merchant_name":               60,
    "running_balance":             80,
}


def audit_fields(transactions: list) -> dict:
    print("\n[D1] 字段完整率审计")
    if not transactions:
        print("[D1] ⚠️  无交易数据可审计")
        return {}

    total = len(transactions)
    report = {}
    all_pass = True

    for field, threshold in FIELD_THRESHOLDS.items():
        # running_balance is nested
        if field == "running_balance":
            non_null = sum(1 for t in transactions if t.get("running_balance", {}).get("amount") is not None)
        else:
            non_null = sum(1 for t in transactions if t.get(field) is not None and t.get(field) != "")

        pct = round(non_null / total * 100)
        passed = pct >= threshold
        if not passed:
            all_pass = False
        status = "✅" if passed else "❌"
        report[field] = {"non_null": non_null, "total": total, "pct": pct, "threshold": threshold, "pass": passed}
        print(f"  {status} {field}: {pct}% ({non_null}/{total}) [要求≥{threshold}%]")

    print(f"[D1] 总结: {'✅ PASS' if all_pass else '❌ FAIL — 部分字段低于阈值'}")
    return report


# ── D2 Classification Taxonomy ─────────────────────────────────────────────

CRITICAL_CATEGORIES = {
    "Gambling":            "赌博识别（BNPL风险核心信号）",
    "Entertainment":       "娱乐支出",
    "Bills and Utilities": "水电类固定支出",
    "Housing":             "住房支出（偿付能力）",
    "Transfer":            "转账（可能包含还款）",
    "Income":              "收入识别",
}


def check_classifications(transactions: list) -> dict:
    print("\n[D2] Classification Taxonomy验证")
    all_cats = set()
    for txn in transactions:
        for c in txn.get("transaction_classification", []):
            all_cats.add(c)

    print(f"  Mock Bank返回的所有分类 ({len(all_cats)}个): {sorted(all_cats) or '(无)'}")
    results = {}
    for cat, purpose in CRITICAL_CATEGORIES.items():
        found = cat in all_cats
        results[cat] = found
        print(f"  {'✅' if found else '❌'} {cat} — {purpose}")

    found_count = sum(results.values())
    print(f"[D2] 总结: {found_count}/{len(CRITICAL_CATEGORIES)} 关键类别存在 {'✅ PASS' if found_count >= 4 else '❌ FAIL'}")
    print("[D2] DE市场注意: transaction_classification 在DE银行不支持（文档已确认），DE需自建关键词分类规则")
    return {"categories_found": results, "all_categories": sorted(all_cats)}


# ── D3 RFMQTD六维特征 ──────────────────────────────────────────────────────

def extract_rfmqtd(transactions: list) -> dict:
    print("\n[D3] RFMQTD六维特征可提取性验证")
    results = {}

    credits = [t for t in transactions if t.get("amount", 0) > 0]
    debits  = [t for t in transactions if t.get("amount", 0) < 0]

    # R — 近度: 最近一笔收入距今天数
    if credits:
        try:
            latest = max(credits, key=lambda x: x.get("timestamp", ""))
            ts = latest["timestamp"][:10]
            delta = (datetime.now() - datetime.strptime(ts, "%Y-%m-%d")).days
            results["R_recency"] = {"value": f"{delta}天前", "pass": True}
            print(f"  ✅ R(近度): 最近收入 {ts}，距今 {delta} 天")
        except Exception as e:
            results["R_recency"] = {"value": None, "pass": False, "error": str(e)}
            print(f"  ❌ R(近度): 计算失败 — {e}")
    else:
        results["R_recency"] = {"value": None, "pass": False, "error": "无收入记录"}
        print("  ❌ R(近度): 无收入记录")

    # F — 频度: 月均交易笔数
    if transactions:
        months = max(1, len(set(t["timestamp"][:7] for t in transactions if t.get("timestamp"))))
        freq = round(len(transactions) / months, 1)
        results["F_frequency"] = {"value": f"{freq}笔/月", "pass": True}
        print(f"  ✅ F(频度): 月均 {freq} 笔（{len(transactions)}笔/{months}个月）")
    else:
        results["F_frequency"] = {"value": None, "pass": False}
        print("  ❌ F(频度): 无数据")

    # M — 金额: 月均净现金流
    if transactions:
        months = max(1, len(set(t["timestamp"][:7] for t in transactions if t.get("timestamp"))))
        net = sum(t.get("amount", 0) for t in transactions) / months
        currency = transactions[0].get("currency", "GBP")
        results["M_monetary"] = {"value": f"{net:.2f} {currency}/月", "pass": True}
        print(f"  ✅ M(金额): 月均净现金流 {net:.2f} {currency}")
    else:
        results["M_monetary"] = {"value": None, "pass": False}
        print("  ❌ M(金额): 无数据")

    # Q — 质量: 月收入变异系数
    if credits:
        months_map = {}
        for t in credits:
            m = t.get("timestamp", "")[:7]
            months_map.setdefault(m, 0)
            months_map[m] += t.get("amount", 0)
        monthly = list(months_map.values())
        if len(monthly) >= 2:
            mean = sum(monthly) / len(monthly)
            std = (sum((x - mean) ** 2 for x in monthly) / len(monthly)) ** 0.5
            cv = round(std / mean, 3) if mean else None
            results["Q_quality"] = {"value": f"CV={cv}", "pass": True}
            print(f"  ✅ Q(质量): 月收入变异系数 CV={cv}（<0.3为稳定收入）")
        else:
            results["Q_quality"] = {"value": "仅1个月数据", "pass": False, "note": "需≥2个月收入数据"}
            print("  ⚠️  Q(质量): 需≥2个月收入数据")
    else:
        results["Q_quality"] = {"value": None, "pass": False}
        print("  ❌ Q(质量): 无收入记录")

    # T — 趋势: 余额斜率
    balances = [t.get("running_balance", {}).get("amount") for t in transactions]
    balances = [b for b in balances if b is not None]
    if len(balances) >= 5:
        n = len(balances)
        x_mean = (n - 1) / 2
        y_mean = sum(balances) / n
        num = sum((i - x_mean) * (balances[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = round(num / den, 4) if den else 0
        direction = "上升" if slope > 0 else "下降"
        results["T_trend"] = {"value": f"斜率={slope} ({direction})", "pass": True}
        print(f"  ✅ T(趋势): 余额斜率={slope}/期 ({direction}趋势，{len(balances)}个数据点)")
    else:
        results["T_trend"] = {"value": None, "pass": False, "note": f"running_balance有效点={len(balances)}，需≥5"}
        print(f"  ❌ T(趋势): running_balance有效数据不足（{len(balances)}点，需≥5）")

    # D — 多样性: 活跃消费类别数
    categories = set()
    for t in transactions:
        cats = t.get("transaction_classification", [])
        if cats:
            categories.add(cats[0])
    results["D_diversity"] = {"value": f"{len(categories)}个类别", "pass": len(categories) >= 3}
    print(f"  {'✅' if len(categories) >= 3 else '⚠️ '} D(多样性): {len(categories)} 个活跃消费类别")

    passed_count = sum(1 for v in results.values() if v.get("pass"))
    print(f"\n[D3] 总结: {passed_count}/6 维度可计算 {'✅ PASS' if passed_count >= 5 else '❌ FAIL — 特征工程受限'}")
    return {"dimensions": results, "passed": passed_count}
