#!/usr/bin/env python3
"""
グロース市場上場企業の情報取得スクリプト

Step 1: JPXの上場銘柄一覧Excelを読み込み、グロース市場でフィルタ
Step 2: Yahoo Finance APIで企業情報を補完
Step 3: 企業マスタDB形式でCSV出力
"""

import pandas as pd
import requests
import json
import time
import os
from datetime import datetime

# 設定
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'exports')

def load_jpx_excel(filepath: str) -> pd.DataFrame:
    """JPXの上場銘柄一覧Excelを読み込む"""
    print(f"Loading JPX data from: {filepath}")

    # xlsファイルを読み込み（xlrdが必要）
    try:
        df = pd.read_excel(filepath, engine='xlrd')
    except Exception:
        # xlsxの場合
        df = pd.read_excel(filepath, engine='openpyxl')

    print(f"Total companies loaded: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    return df


def filter_growth_market(df: pd.DataFrame) -> pd.DataFrame:
    """グロース市場の企業のみにフィルタ"""
    # カラム名の候補（JPXのExcel形式による）
    market_col_candidates = ['市場・商品区分', '市場区分', 'Market/Product', '市場']

    market_col = None
    for col in market_col_candidates:
        if col in df.columns:
            market_col = col
            break

    if market_col is None:
        print(f"Warning: Market column not found. Available columns: {list(df.columns)}")
        # 全カラムを表示してデバッグ
        print(df.head())
        return df

    # グロース市場でフィルタ
    growth_keywords = ['グロース', 'Growth', 'growth']
    mask = df[market_col].astype(str).str.contains('|'.join(growth_keywords), case=False, na=False)
    growth_df = df[mask].copy()

    print(f"Growth market companies: {len(growth_df)}")
    return growth_df


def get_yahoo_finance_info(ticker_code: str) -> dict:
    """
    Yahoo Finance APIから企業情報を取得
    ticker_code: 証券コード（例: "4477"）
    """
    yahoo_ticker = f"{ticker_code}.T"

    # Yahoo Finance v8 API (非公式)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            result = data.get('chart', {}).get('result', [])
            if result:
                meta = result[0].get('meta', {})
                return {
                    'symbol': meta.get('symbol'),
                    'currency': meta.get('currency'),
                    'regularMarketPrice': meta.get('regularMarketPrice'),
                    'previousClose': meta.get('previousClose'),
                }
    except Exception as e:
        print(f"  Error fetching {yahoo_ticker}: {e}")

    return {}


def get_company_profile(ticker_code: str) -> dict:
    """
    Yahoo Finance quoteSummary APIから企業プロファイルを取得
    """
    yahoo_ticker = f"{ticker_code}.T"

    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{yahoo_ticker}"
    params = {
        'modules': 'assetProfile,summaryProfile,summaryDetail'
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

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
        print(f"  Error fetching profile for {yahoo_ticker}: {e}")

    return {}


def enrich_with_yahoo_finance(df: pd.DataFrame, limit: int = None) -> pd.DataFrame:
    """Yahoo Financeから企業情報を補完"""

    # 証券コードのカラムを探す
    code_col_candidates = ['コード', '銘柄コード', 'Code', 'code', 'Ticker']
    code_col = None
    for col in code_col_candidates:
        if col in df.columns:
            code_col = col
            break

    if code_col is None:
        print(f"Warning: Code column not found. Available: {list(df.columns)}")
        return df

    # 新しいカラムを追加
    df['yf_sector'] = None
    df['yf_industry'] = None
    df['yf_employees'] = None
    df['yf_summary'] = None
    df['yf_website'] = None
    df['yf_market_cap'] = None

    codes = df[code_col].tolist()
    if limit:
        codes = codes[:limit]

    print(f"\nFetching Yahoo Finance data for {len(codes)} companies...")

    for i, code in enumerate(codes):
        code_str = str(code).zfill(4)  # 4桁にゼロ埋め
        print(f"  [{i+1}/{len(codes)}] Fetching {code_str}...", end=' ')

        profile = get_company_profile(code_str)

        if profile:
            idx = df[df[code_col] == code].index[0]
            df.at[idx, 'yf_sector'] = profile.get('sector')
            df.at[idx, 'yf_industry'] = profile.get('industry')
            df.at[idx, 'yf_employees'] = profile.get('fullTimeEmployees')
            df.at[idx, 'yf_summary'] = profile.get('longBusinessSummary')
            df.at[idx, 'yf_website'] = profile.get('website')
            df.at[idx, 'yf_market_cap'] = profile.get('marketCap')
            print("OK")
        else:
            print("No data")

        # Rate limiting
        time.sleep(0.5)

    return df


def convert_to_master_db_format(df: pd.DataFrame) -> pd.DataFrame:
    """企業マスタDB形式に変換"""

    # カラムマッピング（JPXのExcel形式に依存）
    column_mapping = {
        'コード': 'stock_code',
        '銘柄名': 'company_name',
        '市場・商品区分': 'market',
        '33業種区分': 'industry_category',
        '17業種区分': 'industry_category_17',
        '規模区分': 'size_category',
    }

    # 存在するカラムのみマッピング
    rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df.rename(columns=rename_dict)

    # 企業マスタDBスキーマに合わせた出力
    master_columns = [
        'company_id',
        'company_name',
        'url',
        'description',
        'business_model',
        'target',
        'stage',
        'employee_count',
        'domain',
        'icp_score',
        'source',
        'created_at',
        'updated_at',
        'notes',
        # 追加情報
        'stock_code',
        'market',
        'market_cap',
    ]

    result = pd.DataFrame()

    # 既存データをマッピング
    result['company_id'] = df.get('stock_code', df.index).astype(str)
    result['company_name'] = df.get('company_name', df.get('銘柄名', ''))
    result['url'] = df.get('yf_website', '')
    result['description'] = df.get('yf_summary', '')
    result['business_model'] = ''  # 後でLLMで判定
    result['target'] = ''  # 後でLLMで判定
    result['stage'] = '上場'  # グロース市場上場企業
    result['employee_count'] = df.get('yf_employees', '')
    result['domain'] = df.get('yf_industry', df.get('33業種区分', ''))
    result['icp_score'] = ''  # 後でLLMで判定
    result['source'] = 'JPX Growth Market'
    result['created_at'] = datetime.now().strftime('%Y-%m-%d')
    result['updated_at'] = datetime.now().strftime('%Y-%m-%d')
    result['notes'] = ''
    result['stock_code'] = df.get('stock_code', '')
    result['market'] = df.get('market', 'グロース')
    result['market_cap'] = df.get('yf_market_cap', '')

    return result


def main():
    """メイン処理"""
    print("=" * 60)
    print("グロース市場企業情報取得スクリプト")
    print("=" * 60)

    # Step 1: JPX Excelファイルを探す
    jpx_files = [
        os.path.join(DATA_DIR, 'data_j.xls'),
        os.path.join(DATA_DIR, 'data_j.xlsx'),
        os.path.join(DATA_DIR, 'jpx_listed_companies.xls'),
        os.path.join(DATA_DIR, 'jpx_listed_companies.xlsx'),
    ]

    jpx_file = None
    for f in jpx_files:
        if os.path.exists(f):
            jpx_file = f
            break

    if jpx_file is None:
        print("\n[ERROR] JPX上場銘柄一覧ファイルが見つかりません。")
        print("以下のいずれかをdata/フォルダに配置してください:")
        print("  - data_j.xls")
        print("  - data_j.xlsx")
        print("\nダウンロード先:")
        print("  https://www.jpx.co.jp/markets/statistics-equities/misc/01.html")
        return

    # Step 2: Excel読み込み
    df = load_jpx_excel(jpx_file)

    # Step 3: グロース市場フィルタ
    growth_df = filter_growth_market(df)

    if len(growth_df) == 0:
        print("\n[ERROR] グロース市場の企業が見つかりませんでした。")
        print("Excelファイルの形式を確認してください。")
        return

    # Step 4: Yahoo Financeで情報補完（テスト時は件数制限）
    # 本番は limit=None で全件取得
    enriched_df = enrich_with_yahoo_finance(growth_df, limit=10)  # テスト用に10件

    # Step 5: 企業マスタDB形式に変換
    master_df = convert_to_master_db_format(enriched_df)

    # Step 6: CSV出力
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_file = os.path.join(OUTPUT_DIR, 'growth_companies_master.csv')
    master_df.to_csv(output_file, index=False, encoding='utf-8-sig')

    print(f"\n[SUCCESS] Output saved to: {output_file}")
    print(f"Total companies: {len(master_df)}")

    # サマリ表示
    print("\n--- Sample Data ---")
    print(master_df[['company_id', 'company_name', 'employee_count', 'domain']].head(10))


if __name__ == '__main__':
    main()
