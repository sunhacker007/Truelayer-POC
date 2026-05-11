"""
TrueLayer BNPL POC — 三层验证入口

Layer 1: 连通性验证（C1-C3 token + 4个接口）
Layer 2: D+3还款监控机制验证（C3 UK / C4 DE SCA）
Layer 3: 数据结构验证（D1字段完整率 / D2分类 / D3 RFMQTD）

运行前置条件：
  1. .env 已配置 CLIENT_ID / CLIENT_SECRET / REDIRECT_URI
  2. 在 TrueLayer Console 中已注册 REDIRECT_URI
  3. 浏览器可访问（用于完成Mock Bank授权）
"""

import json
import sys

import auth
import data
import monitoring
import audit
import export

BANNER = """
╔══════════════════════════════════════════════════════╗
║         TrueLayer BNPL POC — Sandbox验证             ║
║         UK + DE市场  |  2周POC  |  三层验证           ║
╚══════════════════════════════════════════════════════╝
"""

# 交易查询时间窗口（Mock Bank有固定历史数据）
TXN_FROM = "2021-01-01T00:00:00"
TXN_TO   = "2021-12-31T23:59:59"


def run_layer1(tokens: dict, account_id: str) -> dict:
    """C1-C3: 连通性 + Token刷新"""
    print("\n" + "="*54)
    print("LAYER 1: 连通性验证")
    print("="*54)
    results = {}
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")

    # C1 — 4个核心接口
    print("\n[C1] 核心接口连通性（4个接口）")
    endpoints = {}
    try:
        accounts = data.get_accounts(access_token)
        endpoints["accounts"] = "PASS"
    except Exception as e:
        endpoints["accounts"] = f"FAIL: {e}"

    try:
        txns = data.get_transactions(access_token, account_id, TXN_FROM, TXN_TO)
        endpoints["transactions"] = "PASS"
    except Exception as e:
        endpoints["transactions"] = f"FAIL: {e}"
        txns = []

    try:
        balance = data.get_balance(access_token, account_id)
        endpoints["balance"] = "PASS"
    except Exception as e:
        endpoints["balance"] = f"FAIL: {e}"

    try:
        info = data.get_info(access_token)
        endpoints["info"] = "PASS"
    except Exception as e:
        endpoints["info"] = f"FAIL: {e}"

    c1_pass = all(v == "PASS" for v in endpoints.values())
    print(f"[C1] 总结: {'✅ PASS (4/4)' if c1_pass else '❌ FAIL — 部分接口不通'}")
    results["C1"] = {"pass": c1_pass, "endpoints": endpoints}

    # C2 — Token刷新
    print("\n[C2] Token刷新验证")
    if refresh_token:
        try:
            new_tokens = auth.refresh_access_token(refresh_token)
            access_token = new_tokens["access_token"]
            refresh_token = new_tokens.get("refresh_token", refresh_token)
            results["C2"] = {"pass": True}
            print("[C2] ✅ PASS — Token刷新成功，无需用户介入")
        except Exception as e:
            results["C2"] = {"pass": False, "error": str(e)}
            print(f"[C2] ❌ FAIL — Token刷新失败: {e}")
    else:
        results["C2"] = {"pass": False, "error": "无refresh_token"}
        print("[C2] ❌ FAIL — 未获取到refresh_token（请确认scope含offline_access）")

    return results, access_token, refresh_token, txns


def run_layer2_uk(access_token: str, refresh_token: str, account_id: str) -> dict:
    """C3: UK D+3连续访问（需用john/eternal重新授权）"""
    print("\n" + "="*54)
    print("LAYER 2a: UK D+3连续访问验证 (john/eternal)")
    print("="*54)
    print("\n此场景需用 john/eternal 重新授权（模拟UK永久Token）")
    answer = input("是否重新授权？(y/n，默认n跳过): ").strip().lower()
    if answer == "y":
        tokens = auth.prompt_for_code("uk_permanent")
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token", refresh_token)
    return monitoring.simulate_d3_access(access_token, refresh_token, account_id)


def run_layer2_de(refresh_token: str) -> dict:
    """C4: DE SCA断链验证"""
    print("\n" + "="*54)
    print("LAYER 2b: DE SCA断链验证")
    print("="*54)
    print("\n⚠️  注意: Mock Bank中SCA断链需等待access_token自然过期（约1小时）")
    print("    当前直接尝试refresh，记录实际错误码")
    return monitoring.check_sca_expiry(refresh_token)


def run_layer3(transactions: list) -> dict:
    """D1-D4: 数据结构审计"""
    print("\n" + "="*54)
    print("LAYER 3: 数据结构验证")
    print("="*54)
    results = {}
    results["D1"] = audit.audit_fields(transactions)
    results["D2"] = audit.check_classifications(transactions)
    results["D3"] = audit.extract_rfmqtd(transactions)
    print("\n[D4] DE Classification确认")
    print("  ⚠️  transaction_classification 在DE银行不支持（TrueLayer文档已确认：仅UK/IE/FR）")
    print("  建议: DE市场自建基于description关键词的分类规则")
    results["D4"] = {"note": "DE不支持classification，已知缺口，非Fail"}
    return results


def print_summary(l1: dict, l2_uk: dict, l2_de: dict, l3: dict):
    print("\n" + "="*54)
    print("POC结果汇总")
    print("="*54)
    rows = [
        ("C1", "4个核心接口连通性",        l1.get("C1", {}).get("pass")),
        ("C2", "Token刷新（无用户介入）",   l1.get("C2", {}).get("pass")),
        ("C3", "UK D+3连续访问",            l2_uk.get("pass")),
        ("C4", "DE SCA断链错误码清晰",      l2_de.get("pass")),
        ("D1", "字段完整率达标",            all(v.get("pass") for v in l3.get("D1", {}).values()) if l3.get("D1") else None),
        ("D2", "关键分类≥4/6存在",          sum(l3.get("D2", {}).get("categories_found", {}).values()) >= 4 if l3.get("D2") else None),
        ("D3", "RFMQTD≥5/6可计算",         (l3.get("D3", {}).get("passed", 0) >= 5) if l3.get("D3") else None),
    ]
    for code, desc, passed in rows:
        if passed is None:
            icon = "⏭️ "
            label = "SKIP"
        elif passed:
            icon = "✅"
            label = "PASS"
        else:
            icon = "❌"
            label = "FAIL"
        print(f"  {icon} [{code}] {desc}: {label}")
    print()


def main():
    print(BANNER)

    # ── Step 1: UK标准授权 ──────────────────────────────
    print("STEP 1: UK标准OAuth授权 (john/doe)")
    tokens = auth.prompt_for_code("uk_standard")
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")

    # ── Step 2: 获取account_id ──────────────────────────
    print("\n[setup] 获取账户列表...")
    accounts = data.get_accounts(access_token)
    if not accounts:
        print("[error] 未返回账户，请检查授权scope")
        sys.exit(1)

    # 列出账户供用户选择
    print("\n可用账户:")
    for i, acc in enumerate(accounts):
        print(f"  [{i}] {acc.get('display_name')} ({acc.get('account_type')}) — {acc.get('account_id','')[:12]}...")
    idx = 0
    if len(accounts) > 1:
        try:
            idx = int(input(f"选择账户 [0-{len(accounts)-1}]: ").strip())
        except ValueError:
            idx = 0
    account_id = accounts[idx]["account_id"]
    print(f"[setup] 使用账户: {accounts[idx].get('display_name')} (id={account_id[:12]}...)")

    # ── Layer 1 ─────────────────────────────────────────
    l1_results, access_token, refresh_token, txns = run_layer1(tokens, account_id)

    # ── Layer 2 ─────────────────────────────────────────
    l2_uk = run_layer2_uk(access_token, refresh_token, account_id)
    l2_de = run_layer2_de(refresh_token)

    # ── 还款识别（用Layer 1拉到的交易数据）──────────────
    if txns:
        monitoring.identify_repayments(txns)

    # ── Layer 3 ─────────────────────────────────────────
    l3_results = run_layer3(txns)

    # ── 汇总 ────────────────────────────────────────────
    print_summary(l1_results, l2_uk, l2_de, l3_results)

    # ── 导出 ────────────────────────────────────────────
    print("\n" + "="*54)
    print("导出文件")
    print("="*54)
    export.save_transactions_csv(txns, "transactions.csv")
    export.save_poc_report_md(
        accounts=accounts,
        transactions=txns,
        l1=l1_results,
        l2_uk=l2_uk,
        l2_de=l2_de,
        l3=l3_results,
        path="POC_Results.md",
    )
    print("\n交付物:")
    print("  📄 transactions.csv — 1788笔交易原始数据")
    print("  📋 POC_Results.md   — POC结果报告")


if __name__ == "__main__":
    main()
