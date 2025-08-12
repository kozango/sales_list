import os
import time
import logging
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
MAX_RETRIES = 5
INITIAL_BACKOFF = 10  # Seconds, to respect rate limits
OUTPUT_DIR = Path("archives")

# --- Main Logic ---

def get_channel_info(client, channel_id):
    """Fetch a channel's info (name, is_private) from its ID."""
    try:
        result = client.conversations_info(channel=channel_id)
        channel_info = result.get("channel", {})
        return {
            "name": channel_info.get("name", channel_id),
            "is_private": channel_info.get("is_private", False)
        }
    except SlackApiError as e:
        logging.error(f"Error fetching channel info for {channel_id}: {e.response['error']}")
        return None

def get_user_name(client, user_id):
    """Fetch a user's real name from their user ID."""
    try:
        result = client.users_info(user=user_id)
        return result.get("user", {}).get("real_name", user_id)
    except SlackApiError as e:
        logging.error(f"Error fetching user info for {user_id}: {e.response['error']}")
        return user_id

def fetch_messages(client, channel_id, start_time, end_time):
    """Fetch all messages, including thread replies, from a channel within a given time range."""
    all_messages = {}
    next_cursor = None
    retries = 0

    # 1. Fetch all top-level messages
    logging.info("--- Starting to fetch top-level messages ---")
    while retries < MAX_RETRIES:
        try:
            while True:
                logging.info(f"Fetching conversations history... (Cursor: {next_cursor})")
                result = client.conversations_history(
                    channel=channel_id,
                    oldest=start_time.timestamp(),
                    latest=end_time.timestamp(),
                    limit=200,
                    cursor=next_cursor
                )
                for msg in result.get("messages", []):
                    if msg.get('ts') not in all_messages:
                        all_messages[msg['ts']] = msg

                if result.get("has_more"):
                    next_cursor = result.get("response_metadata", {}).get("next_cursor")
                    time.sleep(60)  # Tier 1 rate limit: 1 req/min
                else:
                    break
            break  # Exit retry loop on success
        except SlackApiError as e:
            if e.response["error"] == "ratelimited":
                retry_after = int(e.response.headers.get("Retry-After", INITIAL_BACKOFF))
                logging.warning(f"Rate limited. Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                retries += 1
            else:
                logging.error(f"Error fetching messages: {e.response['error']}")
                return None
    if retries == MAX_RETRIES:
        logging.error("Max retries reached for conversations.history.")
        return None

    logging.info(f"Fetched {len(all_messages)} top-level messages.")

    # 2. Fetch replies for each thread
    logging.info("--- Starting to fetch thread replies ---")
    thread_parents = [msg for msg in all_messages.values() if msg.get("reply_count")]
    logging.info(f"Found {len(thread_parents)} threads to fetch.")

    for i, parent in enumerate(thread_parents):
        thread_ts = parent.get('ts')
        logging.info(f"Fetching replies for thread {i+1}/{len(thread_parents)} (ts: {thread_ts})")
        try:
            # conversations.replies is Tier 1 for unapproved apps. Wait 60s.
            time.sleep(60)
            for reply_page in client.conversations_replies(channel=channel_id, ts=thread_ts, limit=200):
                for reply in reply_page.get("messages", []):
                    if reply.get('ts') not in all_messages:
                        all_messages[reply['ts']] = reply
        except SlackApiError as e:
            logging.error(f"Error fetching replies for thread {thread_ts}: {e.response['error']}")
            # Continue to the next thread even if one fails
            continue

    logging.info(f"Total messages including replies: {len(all_messages)}")
    return list(all_messages.values())

def save_to_tsv(messages, client, channel_id, channel_name, target_date):
    """Save messages to a TSV file in the specified directory structure."""
    """Save messages to a TSV file in the specified directory structure."""
    if not messages:
        logging.info("No messages to save.")
        return

    # Sort messages by timestamp (oldest first)
    messages.sort(key=lambda m: float(m.get('ts', 0)))

    # Create directory path
    year = target_date.strftime("%Y")
    month = target_date.strftime("%m")
    file_dir = OUTPUT_DIR / channel_id / year / month
    file_dir.mkdir(parents=True, exist_ok=True)

    # Define file path
    file_name = f"{channel_id}_{target_date.strftime('%Y-%m-%d')}.tsv"
    file_path = file_dir / file_name

    # Cache user names to reduce API calls
    user_cache = {}

    logging.info(f"Saving messages to {file_path}")
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(["timestamp_utc", "channel_name", "user_id", "user_name", "text", "thread_ts"])

        for msg in messages:
            # Skip non-message types (e.g., channel join events)
            if msg.get("type") != "message" or msg.get("subtype") is not None:
                continue

            user_id = msg.get("user", "N/A")
            if user_id != "N/A" and user_id not in user_cache:
                user_cache[user_id] = get_user_name(client, user_id)
            
            user_name = user_cache[user_id]
            text = msg.get("text", "").replace('\n', ' ').replace('\r', ' ')
            ts_utc = datetime.fromtimestamp(float(msg.get("ts", 0)), tz=timezone.utc).isoformat()

            thread_ts = msg.get("thread_ts", "")
            writer.writerow([ts_utc, channel_name, user_id, user_name, text, thread_ts])
    
    logging.info("Successfully saved messages.")

def read_backup_channels(config_file):
    """Read the channel configuration file and return a list of channels to back up."""
    backup_list = []
    try:
        with open(config_file, 'r', newline='', encoding='utf-8') as f:
            # Skip header
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('backup_enabled', '').lower() == 'true':
                    backup_list.append(row)
        logging.info(f"Found {len(backup_list)} channels enabled for backup in {config_file}.")
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_file}")
    except Exception as e:
        logging.error(f"Error reading {config_file}: {e}")
    return backup_list

def get_target_channels():
    """Read the channel configuration file and return a list of channel IDs to back up."""
    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / 'channels.csv'
    backup_list = read_backup_channels(config_path)
    return [channel['channel_id'] for channel in backup_list]

def get_channel_name(client, channel_id):
    """Fetch a channel's name from its ID."""
    try:
        result = client.conversations_info(channel=channel_id)
        channel_info = result.get("channel", {})
        return channel_info.get("name", channel_id)
    except SlackApiError as e:
        logging.error(f"Error fetching channel info for {channel_id}: {e.response['error']}")
        return channel_id

def main():
    """Main function to run the backup process based on a config file."""
    parser = argparse.ArgumentParser(description="Backup Slack messages for a specified date.")
    parser.add_argument(
        "--date",
        type=str,
        help="Target date in YYYY-MM-DD format. Defaults to yesterday (JST)."
    )
    args = parser.parse_args()

    load_dotenv()

    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    if not SLACK_BOT_TOKEN:
        logging.error("SLACK_BOT_TOKEN must be set.")
        return

    client = WebClient(token=SLACK_BOT_TOKEN)
    channel_ids = get_target_channels()

    if not channel_ids:
        logging.info("No channels are enabled for backup in channels.csv. Exiting.")
        return

    # Determine target date
    jst = timezone(timedelta(hours=9))
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
            logging.info(f"Manual backup triggered for date: {target_date}")
        except ValueError:
            logging.error("Invalid date format. Please use YYYY-MM-DD.")
            return
    else:
        target_date = (datetime.now(jst) - timedelta(days=1)).date()
        logging.info(f"Scheduled backup running for date: {target_date}")

    start_of_day = datetime.combine(target_date, datetime.min.time(), tzinfo=jst)
    end_of_day = datetime.combine(target_date, datetime.max.time(), tzinfo=jst)

    logging.info(f"--- Starting backup for {len(channel_ids)} channel(s) for date {target_date} ---")

    for channel_id in channel_ids:
        logging.info(f"\nProcessing channel: {channel_id}")
        try:
            # Wait for a moment to avoid rate limiting
            time.sleep(1)

            channel_name = get_channel_name(client, channel_id)
            logging.info(f"Target channel name: {channel_name}")

            messages = fetch_messages(client, channel_id, start_of_day, end_of_day)

            if messages:
                save_to_tsv(messages, client, channel_id, channel_name, target_date)
            else:
                logging.info(f"No messages found for channel {channel_id} on {target_date}. Skipping.")
        
        except SlackApiError as e:
            if e.response["error"] == "not_in_channel":
                logging.warning(f"Bot is not in channel {channel_id}. Skipping. Please invite the bot to this channel.")
            else:
                logging.error(f"An error occurred for channel {channel_id}: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred for channel {channel_id}: {e}")
            continue # Move to the next channel
    
    logging.info("--- Backup process finished ---")

if __name__ == "__main__":
    main()
