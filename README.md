# Slack Backup PoC

Slackの特定チャンネルの会話を毎日バックアップするためのPythonスクリプトです。

## 1. プロジェクト概要

このプロジェクトは、指定されたSlackチャンネルのメッセージ（スレッド返信を含む）を一日分取得し、TSV形式のファイルとして保存します。PoC（概念実証）フェーズとして、バックアップデータもGitリポジトリで一元管理するシンプルな構成になっています。

## 2. 現在の機能と設計

- **日次バックアップ**: スクリプト実行日の前日分のメッセージを取得します。
- **チャンネル指定**: `channels.csv` ファイルでバックアップ対象のチャンネルを指定します。
- **TSV形式で保存**: データはタブ区切りファイルとして、以下の構造で保存されます。
  - `archives/[チャンネルID]/[年]/[月]/[チャンネルID]_[日付].tsv`
- **スレッド対応**: スレッド内の返信もすべて取得し、親メッセージと同じファイルに保存します。
- **データ管理**: 生成されたバックアップデータ（`archives/` フォルダ）もGitの管理対象とし、GitHubに保存します。
- **プライベートチャンネル対応**: ボットをチャンネルに招待すれば、プライベートチャンネルのバックアップも可能です。特別なコード変更は不要です。

### 保存されるデータ項目

| 列名 | 内容 |
| :--- | :--- |
| `timestamp_utc` | メッセージの投稿日時（UTC） |
| `channel_name` | チャンネル名 |
| `user_id` | 投稿者のID |
| `user_name` | 投稿者の名前 |
| `text` | メッセージの本文 |
| `thread_ts` | スレッドの親メッセージのID（スレッドでない場合は自身のID） |

### 特殊なケースの挙動

- **他チャンネルからの引用**: メッセージ本文に他の投稿へのリンク（URL）が含まれている場合、その**URLがテキストとしてそのまま保存されます**。リンク先のメッセージ本文や添付ファイルは取得しません。

## 3. 使い方

### 3.1. セットアップ

1.  **リポジトリをクローン**

2.  **環境変数の設定**
    プロジェクトルートに `.env` ファイルを作成し、Slack Botのトークンを記述します。
    ```
    SLACK_BOT_TOKEN="xoxb-xxxxxxxxxxxxx"
    ```

3.  **依存ライブラリのインストール**
    ```bash
    pip install -r requirements.txt
    ```

4.  **バックアップ対象チャンネルの指定**
    `channels.csv` を編集し、バックアップしたいチャンネルのIDと、バックアップを有効にするか (`true`/`false`) を設定します。

### 3.2. バックアップの実行

以下のコマンドを実行すると、前日分のメッセージがバックアップされます。

```bash
python scripts/slack_backup.py
```

### 3.3. バックアップデータの同期

新しいバックアップファイルが作成されたら、以下のコマンドでGitHubに同期します。

```bash
git add archives/
git commit -m "Add backup data for YYYY-MM-DD"
git push origin master
```

## 4. 今後の展望（Future Scenarios）

現在の「全量バックアップ」方式から、より洗練された方式へ発展させるアイディアです。

### シナリオA: キュレーション・バックアップ（簡易版）

- **概要**: `#backup` のような専用チャンネルを用意し、保存したい重要なメッセージの**リンクをそこに投稿**します。スクリプトのバックアップ対象をこのチャンネルのみに絞ります。
- **メリット**: 運用が簡単。重要な情報へのインデックスが作れる。
- **デメリット**: バックアップされるのはURLのみ。リンク先の元投稿が消えると見れなくなる。

### シナリオB: キュレーション・バックアップ（発展版）

- **概要**: シナリオAをさらに発展させ、`#backup` チャンネルに投稿されたURLをスクリプトが解釈。**リンク先のメッセージ本文やスレッドを丸ごと取得して**保存するように改造します。
- **メリット**: 本当に重要な情報だけを、内容を含めて完全にバックアップできる。
- **デメリット**: スクリプトの大幅な改造が必要となり、実装難易度が高い。

### その他のアイディア

- **実行の自動化 (GitHub Actions)**: `GitHub Actions` を利用して、バックアップとGitへのプッシュを毎日自動で実行するのが最も推奨される方法です。その場合、リポジトリのSecretsに `SLACK_BOT_TOKEN` を登録し、ワークフロー内でスクリプトを実行、変更をコミット＆プッシュする設定が必要になります。
- **ストレージの変更**: データが大規模になった場合、`archives/` をGit管理から外し、Amazon S3などのクラウドストレージに保存するよう変更する。

このプロジェクトは、公開Slackチャンネル1つのテキストメッセージを、毎日GitHubリポジトリへバックアップするためのPoC（概念実証）です。

## 目的

バックアッププロセスの精度、実行時間、そして運用フローを検証することを目的としています。

## 主な機能

-   **対象データ**: 公開Slackチャンネル1つ（スレッド内の返信を含むテキストメッセージ）。
-   **実行スケジュール**: GitHub Actionsにより毎日実行。
-   **保存形式**: メッセージはTSV形式で、年・月・日ごとに整理されて保存されます。
-   **使用技術**: Python (`slack_sdk`) と GitHub Actions。

## セットアップ手順

1.  **Slackアプリの作成**: 以下のスコープを持つSlackアプリを作成します。
    -   `channels:history`
    -   `channels:read`
    -   `conversations:list` (チャンネルリスト取得用)
2.  **Botをチャンネルに招待**: 作成したBotをバックアップ対象のチャンネルに招待します。
3.  **プライベートリポジトリの作成**: GitHubにプライベートリポジトリを作成します。
4.  **バックアップ対象チャンネルの設定**: プロジェクトのルートにある `channels.csv` ファイルを編集して、バックアップしたいチャンネルを管理します。

    ```csv
    channel_id,channel_name_note,backup_enabled
    C12345678,general,true
    C98765432,random,false
    ```
    - `channel_id`: 必須。バックアップ対象のチャンネルID。
    - `channel_name_note`: 任意。管理用のメモです。
    - `backup_enabled`: 必須。`true`に設定されたチャンネルのみバックアップされます。

    **プライベートチャンネルの注意点:**
    Slack APIの仕様上、プライベートチャンネルをバックアップするには、まずBotをそのチャンネルに招待する必要があります。Botが招待されていないプライベートチャンネルは、チャンネルリスト取得スクリプト (`scripts/populate_channels.csv.py`) を実行しても一覧に表示されません。

5.  **リポジトリのSecrets設定**: 以下をリポジトリのSecretsに設定します。
    -   `SLACK_BOT_TOKEN`: あなたのSlack BotのOAuthトークン。
6.  **Python依存関係のインストール**:
    ```bash
    pip install -r requirements.txt
    ```

## ワークフロー

GitHub Actionsのワークフロー (`.github/workflows/slack-backup.yml`) は、毎日定時（UTC 15:00 / JST 00:00）に実行されるほか、手動での実行も可能です。

1.  リポジトリをチェックアウトします。
2.  **チャンネルリスト更新**: `scripts/populate_channels.csv.py` を実行し、Slackから最新のチャンネルリストを取得して `channels.csv` を更新します。新しいチャンネルは `backup_enabled=false` として追加されます。
3.  **メッセージのバックアップ**: `scripts/slack_backup.py` を実行し、`channels.csv` で `backup_enabled=true` に設定されているチャンネルのメッセージを取得します。
4.  取得したメッセージをTSVファイルに整形し、`archives/` ディレクトリ以下に保存します。
5.  **変更をコミット**: `archives/` ディレクトリや `channels.csv` に変更があった場合、変更内容をリポジトリにコミット＆プッシュします。

### 保存形式の例

`archives/C98765432/2025/07/C98765432_2025-07-26.tsv`

```tsv
timestamp_utc	channel_name	user_id	user_name	text	thread_ts
2025-07-25T23:00:00+00:00	general	U01234567	koza	こんにちは	
2025-07-25T23:05:00+00:00	general	U88888888	Bさん	おはよー	2025-07-25T23:00:00+00:00
```
- **thread_ts**: このメッセージが属するスレッドの親メッセージのタイムスタンプ。トップレベルのメッセージでは空欄になります。

---

# Slack Backup PoC

This project is a Proof of Concept (PoC) to back up text messages from a single public Slack channel to a GitHub repository on a daily basis.

## Purpose

The goal is to validate the accuracy, execution time, and operational flow of the backup process.

## Features

-   **Target Data**: One public Slack channel (text messages, including replies in threads).
-   **Schedule**: Runs daily via GitHub Actions.
-   **Storage Format**: Messages are saved in TSV format, organized by year, month, and day.
-   **Technology**: Python (`slack_sdk`) and GitHub Actions.

## Setup

1.  **Create a Slack App** with the following scopes:
    -   `channels:history`
    -   `channels:read`
    -   `conversations:list` (for fetching the channel list)
2.  **Invite the Bot** to the target channel.
3.  **Create a private GitHub repository**.
4.  **Configure Target Channels**: Edit the `channels.csv` file in the project root to manage which channels to back up.

    ```csv
    channel_id,channel_name_note,backup_enabled
    C12345678,general,true
    C98765432,random,false
    ```
    - `channel_id`: Required. The ID of the target channel.
    - `channel_name_note`: Optional. A note for management purposes.
    - `backup_enabled`: Required. Only channels with this set to `true` will be backed up.

    **Note on Private Channels:**
    Due to Slack API specifications, to back up a private channel, you must first invite the Bot to that channel. Private channels to which the Bot has not been invited will not appear in the list even after running the channel list acquisition script (`scripts/populate_channels.csv.py`).

5.  **Set Repository Secrets**:
    -   `SLACK_BOT_TOKEN`: Your Slack Bot User OAuth Token.
6.  **Install Python dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Workflow

The GitHub Actions workflow (`.github/workflows/slack-backup.yml`) runs on a schedule (`0 15 * * *` UTC, which is 00:00 JST) and can also be triggered manually.

1.  Checks out the repository.
2.  **Update Channel List**: Runs `scripts/populate_channels.csv.py` to fetch the latest channel list from Slack and update `channels.csv`. New channels are added with `backup_enabled=false`.
3.  **Backup Messages**: Runs `scripts/slack_backup.py` to fetch messages for channels where `backup_enabled=true` in `channels.csv`.
4.  Formats the messages into a TSV file and saves it under the `archives/` directory.
5.  **Commit Changes**: If there are any changes in the `archives/` directory or to `channels.csv`, it commits and pushes them to the repository.

### Example of Storage Format

File path: `archives/C98765432/2025/07/C98765432_2025-07-26.tsv`

```tsv
timestamp_utc	channel_name	user_id	user_name	text	thread_ts
2025-07-25T23:00:00+00:00	general	U01234567	koza	Hello	
2025-07-25T23:05:00+00:00	general	U88888888	UserB	Good morning	2025-07-25T23:00:00+00:00
```
- **thread_ts**: The timestamp of the parent message of the thread this message belongs to. It is empty for top-level messages.