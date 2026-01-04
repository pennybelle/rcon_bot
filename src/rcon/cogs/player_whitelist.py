import os
import re
import json
import logging
import asyncio
from datetime import datetime
from discord.ext import commands, tasks
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

# Configuration
WHITELIST_FILE = "player_whitelist.json"
POLL_INTERVAL = 5  # Check every 5 seconds (adjust as needed)


class ADMFileHandler(FileSystemEventHandler):
    """Handles file system events for ADM log files"""
    
    def __init__(self, callback):
        self.callback = callback
        self.last_position = {}
        super().__init__()
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # Only process ADM files
        if not event.src_path.endswith('.ADM'):
            return
        
        logger.info(f"ADM file modified: {event.src_path}")
        
        # Read only new lines since last position
        try:
            file_path = event.src_path
            
            # Initialize position for this file if not tracked
            if file_path not in self.last_position:
                self.last_position[file_path] = 0
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Seek to last read position
                f.seek(self.last_position[file_path])
                
                # Read new lines
                new_lines = f.readlines()
                
                # Update position
                self.last_position[file_path] = f.tell()
            
            # Process new lines
            if new_lines:
                asyncio.create_task(self.callback(new_lines, file_path))
                
        except Exception as e:
            logger.error(f"Error reading ADM file: {e}")


class PlayerWhitelist(commands.Cog):
    """Monitors DayZ server logs and maintains a player whitelist"""
    
    def __init__(self, bot, adm_directory):
        self.bot = bot
        self.adm_directory = adm_directory
        self.whitelist_file = WHITELIST_FILE
        self.whitelist = self.load_whitelist()
        self.observer = None
        self.current_session_dir = None
        
        # Pattern to match player connection logs
        self.connection_pattern = re.compile(
            r'Player "([^"]+)"\(id=([^)]+)\) is connected'
        )
    
    def get_most_recent_session_directory(self):
        """Find the most recently created session directory"""
        try:
            if not os.path.exists(self.adm_directory):
                return None
            
            subdirs = [
                os.path.join(self.adm_directory, d)
                for d in os.listdir(self.adm_directory)
                if os.path.isdir(os.path.join(self.adm_directory, d))
            ]
            
            if not subdirs:
                return None
            
            most_recent = max(subdirs, key=os.path.getctime)
            logger.info(f"Most recent session directory: {most_recent}")
            return most_recent
            
        except Exception as e:
            logger.error(f"Error finding session directory: {e}")
            return None
    
    def load_whitelist(self):
        """Load existing whitelist from file"""
        if os.path.exists(self.whitelist_file):
            try:
                with open(self.whitelist_file, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} players from whitelist")
                    return data
            except Exception as e:
                logger.error(f"Error loading whitelist: {e}")
                return {}
        return {}
    
    def save_whitelist(self):
        """Save whitelist to file"""
        try:
            with open(self.whitelist_file, 'w') as f:
                json.dump(self.whitelist, f, indent=2)
            logger.info(f"Saved whitelist with {len(self.whitelist)} players")
        except Exception as e:
            logger.error(f"Error saving whitelist: {e}")
    
    def add_to_whitelist(self, player_name, player_id):
        """Add a player to the whitelist"""
        if player_id not in self.whitelist:
            self.whitelist[player_id] = {
                'name': player_name,
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat()
            }
            logger.info(f"Added new player to whitelist: {player_name} ({player_id})")
            return True
        else:
            # Update last seen time
            self.whitelist[player_id]['last_seen'] = datetime.now().isoformat()
            # Update name in case it changed
            self.whitelist[player_id]['name'] = player_name
            return False
    
    async def process_log_lines(self, lines, file_path):
        """Process new log lines for player connections"""
        new_players = []
        
        for line in lines:
            match = self.connection_pattern.search(line)
            if match:
                player_name = match.group(1)
                player_id = match.group(2)
                
                logger.info(f"Detected player connection: {player_name} ({player_id})")
                
                is_new = self.add_to_whitelist(player_name, player_id)
                if is_new:
                    new_players.append((player_name, player_id))
        
        # Save if we found any players
        if new_players:
            self.save_whitelist()
            
            # Optional: Send notification to Discord channel
            # channel_id = 1247743821236928637  # Replace with your channel ID
            # channel = self.bot.get_channel(channel_id)
            # if channel:
            #     for name, pid in new_players:
            #         await channel.send(f"🆕 New player whitelisted: **{name}**")
    
    async def start_monitoring(self):
        """Start monitoring the ADM directory"""
        logger.info(f"Attempting to access ADM directory: {self.adm_directory}")
        
        if not os.path.exists(self.adm_directory):
            logger.error(f"ADM directory does not exist: {self.adm_directory}")
            logger.error("Please ensure the directory is mounted correctly in Docker")
            return
        
        # Find the most recent session directory
        session_dir = self.get_most_recent_session_directory()
        if not session_dir:
            logger.error("No session directory found!")
            return
        
        self.current_session_dir = session_dir
        logger.info(f"Monitoring session directory: {session_dir}")
        
        # List files to verify access
        try:
            files = os.listdir(session_dir)
            adm_files = [f for f in files if f.endswith('.ADM')]
            logger.info(f"Found {len(adm_files)} ADM files in directory")
            for f in adm_files:
                logger.info(f"  - {f}")
        except Exception as e:
            logger.error(f"Error listing directory: {e}")
            return
        
        # Initialize file positions for existing ADM files
        for file in os.listdir(session_dir):
            if file.endswith('.ADM'):
                file_path = os.path.join(session_dir, file)
                try:
                    # Start from end of existing files to only catch new entries
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(0, 2)  # Seek to end
                        if not hasattr(self, '_handler'):
                            self._handler = ADMFileHandler(self.process_log_lines)
                        self._handler.last_position[file_path] = f.tell()
                    logger.info(f"Initialized monitoring for: {file_path}")
                except Exception as e:
                    logger.error(f"Error initializing file {file_path}: {e}")
        
        # IMPORTANT: Use PollingObserver instead of Observer for Docker compatibility
        event_handler = ADMFileHandler(self.process_log_lines)
        self._handler = event_handler
        
        # PollingObserver works across Docker mounts by checking file stats periodically
        self.observer = PollingObserver(timeout=POLL_INTERVAL)
        self.observer.schedule(event_handler, session_dir, recursive=False)
        self.observer.start()
        
        logger.info(f"Started POLLING monitoring of ADM files in: {session_dir}")
        logger.info(f"Polling interval: {POLL_INTERVAL} seconds")
        
        # Start checking for new sessions
        if not self.check_for_new_session.is_running():
            self.check_for_new_session.start()
    
    @tasks.loop(seconds=30)
    async def check_for_new_session(self):
        """Check periodically for new session directories"""
        most_recent = self.get_most_recent_session_directory()
        
        if most_recent and most_recent != self.current_session_dir:
            logger.info(f"New session directory detected: {most_recent}")
            
            # Stop current observer
            if self.observer:
                self.observer.stop()
                self.observer.join()
            
            # Update session
            self.current_session_dir = most_recent
            
            # Start monitoring new directory
            try:
                files = os.listdir(most_recent)
                adm_files = [f for f in files if f.endswith('.ADM')]
                
                for file in adm_files:
                    file_path = os.path.join(most_recent, file)
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(0, 2)
                        self._handler.last_position[file_path] = f.tell()
                
                self.observer = PollingObserver(timeout=POLL_INTERVAL)
                self.observer.schedule(self._handler, most_recent, recursive=False)
                self.observer.start()
                
                logger.info(f"Now monitoring: {most_recent}")
            except Exception as e:
                logger.error(f"Error switching to new session: {e}")
    
    @check_for_new_session.before_loop
    async def before_check_new_session(self):
        await self.bot.wait_until_ready()
    
    def stop_monitoring(self):
        """Stop monitoring"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("Stopped monitoring ADM files")
    
    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        self.stop_monitoring()
        if self.check_for_new_session.is_running():
            self.check_for_new_session.cancel()


async def setup(bot):
    """Setup function called when loading the cog"""
    # Get ADM directory from environment
    adm_directory = os.getenv("ADM_LOG_DIRECTORY")
    
    if not adm_directory:
        logger.error("ADM_LOG_DIRECTORY environment variable not set!")
        logger.error("Add ADM_LOG_DIRECTORY=/path/to/logs to your .env file")
        return
    
    logger.info(f"ADM_LOG_DIRECTORY set to: {adm_directory}")
    
    cog = PlayerWhitelist(bot, adm_directory)
    await bot.add_cog(cog)
    
    # Start monitoring after cog is added
    await cog.start_monitoring()