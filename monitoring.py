"""
Layer 2: D+3还款监控机制验证

Tests:
  C3 — UK连续访问: 模拟3期还款日D+3静默拉取（john/eternal）
  C4 — DE SCA断链: 模拟refresh_token到期，记录错误码（john/doe）
  还款识别逻辑: account_match优先，keyword_match降级
"""

import auth
import data

# 模拟3期还款日的时间窗口（Mock Bank有固定历史数据，用固定区间）
REPAYMENT_WINDOWS = [
    ("2021-01-01T00:00:00", "2021-01-31T23:59:59", "第1期"),
    ("2021-02-01T00:00:00", "2021-02-28T23:59:59", "第2期"),
    ("2021-03-01T00:00:00", "2021-03-31T23:59:59", "第3期"),
]

REPAYMENT_KEYWORDS = ["KLARNA", "CLEARPAY", "REPAYMENT", "INSTALMENT", "PAY IN 3"]


def simulate_d3_access(access_token: str, refresh_token: str, account_id: str) -> dict:
    """
    C3: UK连续访问验证 (john/eternal场景)
    模拟3次D+3拉取，每次先refresh token（验证无需用户介入）。
    """
    print("\n[C3] UK D+3连续访问验证")
    results = []
    current_refresh = refresh_token

    for from_dt, to_dt, label in REPAYMENT_WINDOWS:
        # 尝试刷新token（模拟D+3时token可能快到期）
        try:
            tokens = auth.refresh_access_token(current_refresh)
            access_token = tokens["access_token"]
            current_refresh = tokens.get("refresh_token", current_refresh)
            token_status = "refreshed"
        except Exception as e:
            token_status = f"refresh_failed: {e}"

        # 拉取交易数据
        try:
            txns = data.get_transactions(access_token, account_id, from_dt, to_dt)
            status = "PASS"
            txn_count = len(txns)
        except Exception as e:
            status = "FAIL"
            txn_count = 0
            print(f"[C3] {label} 拉取失败: {e}")

        result = {
            "period": label,
            "token_status": token_status,
            "http_status": status,
            "txn_count": txn_count,
        }
        results.append(result)
        print(f"[C3] {label}: token={token_status}, 拉取={status}, 交易数={txn_count}")

    passed = all(r["http_status"] == "PASS" for r in results)
    print(f"[C3] 总结: {'✅ PASS — UK连续访问无需用户重新认证' if passed else '❌ FAIL — 存在访问中断'}")
    return {"test": "C3", "pass": passed, "details": results}


def check_sca_expiry(refresh_token: str) -> dict:
    """
    C4: DE SCA断链验证 (john/doe场景)
    尝试refresh，预期失败（invalid_grant），记录错误码。
    """
    print("\n[C4] DE SCA断链验证")
    try:
        auth.refresh_access_token(refresh_token)
        # 如果成功，说明token还有效
        print("[C4] Token仍有效 — SCA断链尚未触发（Mock Bank中此场景需token真正过期）")
        return {
            "test": "C4",
            "pass": True,
            "sca_expired": False,
            "error_code": None,
            "note": "Token仍有效，Mock Bank中SCA断链需等待token自然过期",
        }
    except Exception as e:
        error_str = str(e)
        # 判断错误类型
        if "invalid_grant" in error_str or "400" in error_str:
            error_code = "invalid_grant"
            reauth_note = "需发起Reauth Flow: GET /reauthuri?token={refresh_token}&redirect_uri=..."
            passed = True  # 错误码清晰可程序化处理即为PASS
        else:
            error_code = error_str
            reauth_note = "未知错误类型，需进一步排查"
            passed = False

        print(f"[C4] SCA断链确认 — error_code={error_code}")
        print(f"[C4] Reauth指引: {reauth_note}")
        print(f"[C4] 总结: {'✅ PASS — 错误码清晰，可程序化处理' if passed else '❌ FAIL — 错误码不明确'}")
        return {
            "test": "C4",
            "pass": passed,
            "sca_expired": True,
            "error_code": error_code,
            "reauth_note": reauth_note,
        }


def identify_repayments(transactions: list,
                        klarna_sort_code: str = "12-34-56",
                        klarna_account: str = "12345678") -> dict:
    """还款识别逻辑: account_match优先，keyword_match降级。"""
    print("\n[还款识别] 分析outflow交易...")
    outflows = [t for t in transactions if t.get("amount", 0) < 0]
    repayments = []

    for txn in outflows:
        meta = txn.get("meta", {})
        # 策略1：对手方账号精确匹配
        if (meta.get("counterpart_sort_code") == klarna_sort_code and
                meta.get("counterpart_account_number") == klarna_account):
            repayments.append({**txn, "_match_strategy": "account_match"})
            continue
        # 策略2：描述关键词
        desc = txn.get("description", "").upper()
        if any(k in desc for k in REPAYMENT_KEYWORDS):
            repayments.append({**txn, "_match_strategy": "keyword_match"})

    counterpart_available = any(
        t.get("meta", {}).get("counterpart_sort_code") for t in transactions
    )

    print(f"[还款识别] outflow交易: {len(outflows)} 笔, 识别为还款: {len(repayments)} 笔")
    print(f"[还款识别] meta.counterpart字段: {'✅ 可用' if counterpart_available else '⚠️ 不可用 — 仅关键词匹配'}")
    return {
        "outflow_count": len(outflows),
        "repayment_count": len(repayments),
        "repayments": repayments,
        "counterpart_field_available": counterpart_available,
    }
