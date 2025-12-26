#!/usr/bin/env python3
"""
Yahoo Financeで企業情報を補完するスクリプト

ローカル環境で実行してください:
  pip install pandas yfinance
  python scripts/enrich_with_yahoo_finance.py

入力: exports/growth_companies_master.csv
出力: exports/growth_companies_enriched.csv
"""

import pandas as pd
import time
import os
import sys

# yfinanceが使えない場合はrequestsで代替
try:
    import yfinance as yf
    USE_YFINANCE = True
except ImportError:
    import requests
    USE_YFINANCE = False
    print("yfinanceがインストールされていません。requestsで代替します。")
    print("より良い結果のためには: pip install yfinance")


def get_company_info_yfinance(ticker_code: str) -> dict:
    """yfinanceを使用して企業情報を取得"""
    yahoo_ticker = f"{ticker_code}.T"
    try:
        ticker = yf.Ticker(yahoo_ticker)
        info = ticker.info
        return {
            'sector': info.get('sector'),
            'industry': info.get('industry'),
            'fullTimeEmployees': info.get('fullTimeEmployees'),
            'longBusinessSummary': info.get('longBusinessSummary'),
            'website': info.get('website'),
            'marketCap': info.get('marketCap'),
        }
    except Exception as e:
        print(f"  Error: {e}")
        return {}


def get_company_info_requests(ticker_code: str) -> dict:
    """requestsを使用してYahoo Finance APIから企業情報を取得"""
    yahoo_ticker = f"{ticker_code}.T"
    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{yahoo_ticker}"
    params = {'modules': 'assetProfile,summaryDetail'}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            result = data.get('quoteSummary', {}).get('result', [])
            if result:
                profile = result[0].get('assetProfile', {})
                summary = result[0].get('summaryDetail', {})
                return {
                    'sector': profile.get('sector'),
                    'industry': profile.get('industry'),
                    'fullTimeEmployees': profile.get('fullTimeEmployees'),
                    'longBusinessSummary': profile.get('longBusinessSummary'),
                    'website': profile.get('website'),
                    'marketCap': summary.get('marketCap', {}).get('raw'),
                }
    except Exception as e:
        print(f"  Error: {e}")
    return {}


def get_company_info(ticker_code: str) -> dict:
    """企業情報を取得（yfinance優先）"""
    if USE_YFINANCE:
        return get_company_info_yfinance(ticker_code)
    else:
        return get_company_info_requests(ticker_code)


def main():
    # パス設定
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    input_file = os.path.join(project_dir, 'exports', 'growth_companies_master.csv')
    output_file = os.path.join(project_dir, 'exports', 'growth_companies_enriched.csv')

    # ファイル読み込み
    if not os.path.exists(input_file):
        print(f"Error: {input_file} が見つかりません")
        sys.exit(1)

    df = pd.read_csv(input_file)
    print(f"読み込み完了: {len(df)}社")

    # ICP候補のみ処理（情報・通信業＋サービス業）
    # 全件処理したい場合はこの行をコメントアウト
    df = df[df['is_icp_candidate'] == True].copy()
    print(f"ICP候補: {len(df)}社")

    # 新しいカラムを追加
    df['yf_sector'] = ''
    df['yf_industry'] = ''
    df['yf_employees'] = ''
    df['yf_summary'] = ''
    df['yf_website'] = ''
    df['yf_market_cap'] = ''

    # 進捗保存用（中断時に途中から再開できるように）
    checkpoint_file = os.path.join(project_dir, 'exports', '.enrich_checkpoint.csv')
    start_idx = 0

    if os.path.exists(checkpoint_file):
        checkpoint_df = pd.read_csv(checkpoint_file)
        start_idx = len(checkpoint_df)
        print(f"チェックポイントから再開: {start_idx}社目から")
        # チェックポイントのデータをマージ
        for idx, row in checkpoint_df.iterrows():
            mask = df['company_id'] == row['company_id']
            if mask.any():
                df.loc[mask, 'yf_sector'] = row.get('yf_sector', '')
                df.loc[mask, 'yf_industry'] = row.get('yf_industry', '')
                df.loc[mask, 'yf_employees'] = row.get('yf_employees', '')
                df.loc[mask, 'yf_summary'] = row.get('yf_summary', '')
                df.loc[mask, 'yf_website'] = row.get('yf_website', '')
                df.loc[mask, 'yf_market_cap'] = row.get('yf_market_cap', '')

    # Yahoo Financeから情報取得
    print("\n--- Yahoo Finance APIから情報取得中 ---")

    processed = []
    for i, (idx, row) in enumerate(df.iterrows()):
        if i < start_idx:
            processed.append(row.to_dict())
            continue

        code = str(row['stock_code'])
        name = row['company_name']

        print(f"[{i+1}/{len(df)}] {code} {name}...", end=' ', flush=True)

        info = get_company_info(code)

        if info:
            df.at[idx, 'yf_sector'] = info.get('sector', '')
            df.at[idx, 'yf_industry'] = info.get('industry', '')
            df.at[idx, 'yf_employees'] = info.get('fullTimeEmployees', '')
            df.at[idx, 'yf_summary'] = (info.get('longBusinessSummary', '') or '')[:500]
            df.at[idx, 'yf_website'] = info.get('website', '')
            df.at[idx, 'yf_market_cap'] = info.get('marketCap', '')
            print(f"OK (従業員: {info.get('fullTimeEmployees', 'N/A')})")
        else:
            print("No data")

        processed.append(df.loc[idx].to_dict())

        # 10社ごとにチェックポイント保存
        if (i + 1) % 10 == 0:
            pd.DataFrame(processed).to_csv(checkpoint_file, index=False)
            print(f"  [Checkpoint saved: {i+1}社]")

        # Rate limiting
        time.sleep(0.3)

    # 最終出力
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n出力完了: {output_file}")

    # チェックポイントファイル削除
    if os.path.exists(checkpoint_file):
        os.remove(checkpoint_file)

    # サマリ
    enriched_count = df['yf_employees'].notna().sum()
    print(f"\n--- サマリ ---")
    print(f"処理完了: {len(df)}社")
    print(f"情報取得成功: {enriched_count}社")

    # ICP候補（従業員20-100人）
    df['yf_employees'] = pd.to_numeric(df['yf_employees'], errors='coerce')
    icp_match = df[(df['yf_employees'] >= 20) & (df['yf_employees'] <= 100)]
    print(f"ICP条件（従業員20-100人）合致: {len(icp_match)}社")


if __name__ == '__main__':
    main()
