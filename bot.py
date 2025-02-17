import os
import logging
import asyncio
from telethon import TelegramClient, events, Button
from yt_dlp import YoutubeDL
from redis import Redis  # For caching and task queuing

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram API credentials
API_ID = 'YOUR_API_ID'
API_HASH = 'YOUR_API_HASH'
BOT_TOKEN = 'YOUR_BOT_TOKEN'

# Redis Labs connection details
REDIS_URI = "redis-12345.c1.us-east1-2.gce.cloud.redislabs.com:12345"  # Replace with your Redis URI
REDIS_PASSWORD = "your-redis-password"  # Replace with your Redis password

# Initialize Redis client
redis = Redis(
    host=REDIS_URI.split(':')[0],  # Extract host from URI
    port=int(REDIS_URI.split(':')[1]),  # Extract port from URI
    password=REDIS_PASSWORD,  # Use the Redis password
    decode_responses=True  # Ensure responses are decoded to strings
)

# Initialize Telethon client
client = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# yt-dlp options
ydl_opts = {
    'format': 'best',
    'quiet': True,
    'no_warnings': True,
}

# Constants for Redis keys
USER_STATE_KEY = "user_state:{user_id}"
DOWNLOAD_QUEUE = "download_queue"

async def download_and_send(user_id, url, format_id):
    """Download and send the file to the user."""
    ydl_opts['format'] = format_id
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        # Send the file to the user
        await client.send_file(user_id, file_path)

        # Delete the file from the server
        os.remove(file_path)
        logger.info(f"File sent and deleted for user {user_id}.")
    except Exception as e:
        logger.error(f"Error for user {user_id}: {e}")
        await client.send_message(user_id, "An error occurred. Please try again.")

async def process_download_queue():
    """Process the download queue asynchronously."""
    while True:
        task = redis.rpop(DOWNLOAD_QUEUE)
        if task:
            user_id, url, format_id = task.decode('utf-8').split('|')
            await download_and_send(int(user_id), url, format_id)
        await asyncio.sleep(1)  # Prevent busy-waiting

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    """Send a welcome message."""
    await event.reply("Welcome! Send me a link to download audio or video.")

@client.on(events.NewMessage)
async def handle_link(event):
    """Handle the link sent by the user."""
    url = event.text
    if not url.startswith(('http://', 'https://')):
        await event.reply("Please send a valid URL.")
        return

    # Store the URL in Redis
    user_id = event.sender_id
    redis.set(USER_STATE_KEY.format(user_id=user_id), url)

    # Ask the user to choose between audio or video
    buttons = [
        [Button.inline("Audio", b"audio")],
        [Button.inline("Video", b"video")]
    ]
    await event.reply("Do you want to download audio or video?", buttons=buttons)

@client.on(events.CallbackQuery)
async def handle_callback(event):
    """Handle callback queries."""
    user_id = event.sender_id
    data = event.data.decode('utf-8')

    if data in ('audio', 'video'):
        # List available formats
        url = redis.get(USER_STATE_KEY.format(user_id=user_id)).decode('utf-8')
        ydl = YoutubeDL(ydl_opts)
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])

        buttons = []
        for f in formats:
            if (data == 'audio' and f.get('acodec') != 'none' and f.get('vcodec') == 'none') or \
               (data == 'video' and f.get('vcodec') != 'none'):
                buttons.append([Button.inline(f"{f['ext']} ({f['format']})", f"{data}_{f['format_id']}")])

        await event.edit(f"Select {data} quality:", buttons=buttons)

    elif data.startswith(('audio_', 'video_')):
        # Add the task to the download queue
        format_id = data.split('_')[1]
        url = redis.get(USER_STATE_KEY.format(user_id=user_id)).decode('utf-8')
        redis.lpush(DOWNLOAD_QUEUE, f"{user_id}|{url}|{format_id}")

        await event.edit("Your request has been added to the queue. Please wait.")

# Start the bot and download queue processor
async def main():
    await asyncio.gather(
        client.run_until_disconnected(),
        process_download_queue()
    )

if __name__ == '__main__':
    logger.info("Bot started...")
    asyncio.run(main())


# dont worry, this shit gonna need fucking hardcore debugging 
