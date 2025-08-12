import os
import csv
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

# --- ロギング設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG_FILE = 'channels.csv'

def get_all_public_channels(client):
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
            if e.response.get("needed") == "conversations:list":
                 logging.error("PERMISSION ERROR: Please add the 'conversations:list' scope to your Slack Bot and reinstall the app.")
            return None
    logging.info(f"Successfully fetched {len(channels)} public channels.")
    return channels

def write_channels_to_csv(all_channels):
    """channels.csvを公開チャンネルの全リストで上書きする"""
    if not all_channels:
        logging.warning("No channels found to write.")
        return 0

    try:
        with open(CONFIG_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['channel_id', 'channel_name_note', 'backup_enabled'])
            
            for channel in all_channels:
                channel_name = channel.get('name', 'unknown_channel')
                # デフォルトではすべてのチャンネルを backup_enabled=false で追加
                writer.writerow([channel['id'], channel_name, 'false'])
        
        logging.info(f"Successfully populated {CONFIG_FILE} with {len(all_channels)} channels.")
        return len(all_channels)
    except IOError as e:
        logging.error(f"Error writing to {CONFIG_FILE}: {e}")
        return 0

def main():
    """メイン処理"""
    load_dotenv()
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    if not SLACK_BOT_TOKEN:
        logging.error("SLACK_BOT_TOKEN must be set in your .env file.")
        return

    client = WebClient(token=SLACK_BOT_TOKEN)
    
    all_channels = get_all_public_channels(client)
    if all_channels is not None:
        write_channels_to_csv(all_channels)
    else:
        logging.error("Could not populate channel list due to an error.")

if __name__ == "__main__":
    main()
