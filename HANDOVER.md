# 引き継ぎドキュメント

## 現在のブランチ
```
claude/kumono-sales-intelligence-db-HfuVI
```

## プロジェクト概要
Kumono営業インテリジェンスDB - ICP条件に合う企業をストックし、シグナル検知で最適タイミングでアプローチ

---

## 完了済みタスク（PJ1: 初期リスト構築）

| # | タスク | 状態 |
|---|--------|------|
| 1-3 | グロース市場リスト取得（JPX） | ✅ 完了 |
| 1-4 | 企業マスタDB形式で出力 | ✅ 完了 |
| - | Yahoo Finance補完スクリプト作成 | ✅ 完了 |

---

## 作成済みファイル

```
exports/
├── growth_companies_raw.csv      # グロース市場610社（JPX生データ）
└── growth_companies_master.csv   # 企業マスタDB形式

scripts/
├── fetch_growth_companies.py     # JPX Excel読み込みスクリプト
└── enrich_with_yahoo_finance.py  # Yahoo Finance補完スクリプト（ローカル実行用）
```

---

## 現在の進捗

```
グロース市場: 610社
├── 情報・通信業: 250社 ← ICP候補
├── サービス業:   196社 ← ICP候補
└── その他:       164社

ICP候補合計: 446社
```

---

## 次のステップ

### Step 1: Yahoo Finance補完（ローカル実行）

```bash
cd ~/sales_list
git pull origin claude/kumono-sales-intelligence-db-HfuVI
pip install yfinance pandas
python scripts/enrich_with_yahoo_finance.py
```

出力: `exports/growth_companies_enriched.csv`
- 従業員数
- 事業概要
- 時価総額
- WebサイトURL

### Step 2: ICP条件フィルタリング

補完後、以下の条件でフィルタ：
- 従業員数: 20〜100人
- 事業モデル: サブスク/SaaS（LLMで判定）
- ターゲット: toC寄り

### Step 3: VCポートフォリオ追加（未着手）

主要VC20-30社のポートフォリオから企業を追加

---

## ICP条件（参考）

| 項目 | 条件 |
|------|------|
| 事業モデル | サブスク/SaaS（toC寄り） |
| ステージ | シリーズA〜C、上場前後（グロース市場含む） |
| 従業員規模 | 20〜100人 |
| 領域 | ヘルスケア/フィットネス/ライフスタイル等に強み |

---

## 企業マスタDB スキーマ

| カラム | 説明 |
|--------|------|
| company_id | 一意ID（証券コード） |
| company_name | 企業名 |
| url | 企業サイトURL |
| description | 事業概要 |
| business_model | サブスク/SaaS/その他 |
| target | toC/toB/両方 |
| stage | 上場（グロース） |
| employee_count | 従業員数 |
| domain | 領域（業種） |
| icp_score | ICP合致スコア（1-5） |
| source | 情報ソース |
| is_icp_candidate | ICP候補フラグ |

---

## 環境の注意点

- この環境（Claude Code）では外部API（Yahoo Finance等）へのアクセスがブロックされる
- Yahoo Finance補完はローカルMac環境で実行する必要あり

---

## 再開時のコマンド

```bash
# リポジトリをクローン or プル
git clone https://github.com/kozango/sales_list.git
cd sales_list
git checkout claude/kumono-sales-intelligence-db-HfuVI

# Yahoo Finance補完を実行
pip install yfinance pandas
python scripts/enrich_with_yahoo_finance.py
```

---

最終更新: 2025-12-26
