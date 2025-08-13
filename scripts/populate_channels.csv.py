import os
import csv
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

# --- ロギング設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG_FILE = 'channels.csv'

def get_all_channels(client):
    """
    Botがアクセス可能な全てのパブリックチャンネルとプライベートチャンネルを取得する
    """
    channels = []
    cursor = None
    logging.info("Fetching all channels from Slack...")
    while True:
        try:
            response = client.conversations_list(types="public_channel,private_channel", limit=200, cursor=cursor)
            channels.extend(response['channels'])
            cursor = response.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break
        except SlackApiError as e:
            logging.error(f"Error fetching channels: {e.response['error']}")
            return None
    logging.info(f"Successfully fetched {len(channels)} channels.")
    return channels

def update_channels_csv(all_channels):
    """
    channels.csvを更新する。
    - 既存のチャンネルはそのまま維持する。
    - 新しく見つかったチャンネルのみを末尾に追記する。
    - 追記されるチャンネルのbackup_enabledは 'false' に設定される。
    """
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_file_path = os.path.join(script_dir, CONFIG_FILE)
    
    existing_channel_ids = set()
    
    # 1. 既存のチャンネルIDを読み込む
    try:
        if os.path.exists(csv_file_path) and os.path.getsize(csv_file_path) > 0:
            with open(csv_file_path, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                header = next(reader)  # ヘッダーをスキップ
                for row in reader:
                    if row: # 空行をスキップ
                        existing_channel_ids.add(row[0])
            logging.info(f"Found {len(existing_channel_ids)} existing channels in channels.csv.")
    except (FileNotFoundError, StopIteration):
        logging.info("channels.csv not found or is empty. A new file will be created.")

    # 2. 新しいチャンネルを特定する
    new_channels = [
        ch for ch in all_channels 
        if ch['id'] not in existing_channel_ids
    ]

    if not new_channels:
        logging.info("No new channels to add.")
        return

    logging.info(f"Found {len(new_channels)} new channels to add.")

    # 3. 新しいチャンネルを追記する
    is_new_file = not os.path.exists(csv_file_path) or os.path.getsize(csv_file_path) == 0
    with open(csv_file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # ファイルが新規作成された場合、ヘッダーを書き込む
        if is_new_file:
            writer.writerow(['channel_id', 'channel_name_note', 'backup_enabled'])
        
        for channel in new_channels:
            channel_id = channel['id']
            channel_name = channel.get('name', f"private-group-{channel_id}")
            writer.writerow([channel_id, channel_name, 'false'])
            logging.info(f"Added new channel: {channel_name} ({channel_id})")

def main():
    """メイン処理"""
    load_dotenv()
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    if not SLACK_BOT_TOKEN:
        logging.error("SLACK_BOT_TOKEN must be set in your .env or environment variables.")
        return

    client = WebClient(token=SLACK_BOT_TOKEN)
    
    all_channels = get_all_channels(client)
    if all_channels is not None:
        update_channels_csv(all_channels)
    else:
        logging.error("Could not update channel list due to an error.")

if __name__ == "__main__":
    main()
