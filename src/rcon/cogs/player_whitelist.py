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
POLL_INTERVAL = 5  # Check every 5 seconds
CHECK_NEW_DIR_INTERVAL = 30  # Check for new session directories every 30 seconds


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
    
    def __init__(self, bot, adm_log_directory):
        self.bot = bot
        self.adm_log_directory = adm_log_directory
        self.whitelist_file = WHITELIST_FILE
        self.whitelist = self.load_whitelist()
        self.observer = None
        self.current_session_dir = None
        self._handler = None
        
        # Pattern to match player connection logs
        self.connection_pattern = re.compile(
            r'Player "([^"]+)"\(id=([^)]+)\) is connected'
        )
    
    def get_most_recent_session_directory(self):
        """Find the most recently created session directory in the logs folder"""
        try:
            if not os.path.exists(self.adm_log_directory):
                logger.error(f"Logs base directory does not exist: {self.adm_log_directory}")
                return None
            
            # Get all subdirectories
            subdirs = [
                os.path.join(self.adm_log_directory, d)
                for d in os.listdir(self.adm_log_directory)
                if os.path.isdir(os.path.join(self.adm_log_directory, d))
            ]
            
            if not subdirs:
                logger.warning(f"No session directories found in: {self.adm_log_directory}")
                return None
            
            # Sort by creation time, get the most recent
            most_recent = max(subdirs, key=os.path.getctime)
            
            logger.info(f"Most recent session directory: {most_recent}")
            logger.info(f"Created: {datetime.fromtimestamp(os.path.getctime(most_recent))}")
            
            return most_recent
            
        except Exception as e:
            logger.error(f"Error finding most recent session directory: {e}")
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
    
    def get_most_recent_session_directory(self):
        """Find the most recently created session directory"""
        try:
            if not os.path.exists(self.adm_directory):
                logger.error(f"Base directory does not exist: {self.adm_directory}")
                return None
            
            # Get all subdirectories
            subdirs = [
                os.path.join(self.adm_directory, d)
                for d in os.listdir(self.adm_directory)
                if os.path.isdir(os.path.join(self.adm_directory, d))
            ]
            
            if not subdirs:
                logger.warning(f"No session directories found in: {self.adm_directory}")
                return None
            
            # Get the most recent by creation time
            most_recent = max(subdirs, key=os.path.getctime)
            logger.info(f"Most recent session directory: {most_recent}")
            
            return most_recent
            
        except Exception as e:
            logger.error(f"Error finding most recent session directory: {e}")
            return None
    
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
            #         await channel.send(f"New player whitelisted: **{name}**")
    
    
    @tasks.loop(seconds=30)
    async def check_for_new_session(self):
        """Check periodically for new session directories"""
        most_recent = self.get_most_recent_session_directory()
        
        if most_recent and most_recent != self.current_session_dir:
            logger.info(f"New session directory detected: {most_recent}")
            logger.info(f"Switching from {self.current_session_dir}")
            
            # Stop current observer
            if self.observer:
                self.observer.stop()
                self.observer.join()
                self.observer = None
            
            # Update current session
            self.current_session_dir = most_recent
            
            # Start monitoring the new directory
            try:
                files = os.listdir(most_recent)
                adm_files = [f for f in files if f.endswith('.ADM')]
                logger.info(f"Found {len(adm_files)} ADM files in new session")
                
                # Initialize file positions for ADM files in new session
                for file in adm_files:
                    file_path = os.path.join(most_recent, file)
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(0, 2)
                        self._handler.last_position[file_path] = f.tell()
                    logger.info(f"Initialized monitoring for: {file_path}")
                
                # Start new observer
                self.observer = PollingObserver(timeout=POLL_INTERVAL)
                self.observer.schedule(self._handler, most_recent, recursive=False)
                self.observer.start()
                
                logger.info(f"Now monitoring: {most_recent}")
            except Exception as e:
                logger.error(f"Error switching to new session: {e}")
    
    @check_for_new_session.before_loop
    async def before_check_new_session(self):
        """Wait for bot to be ready"""
        await self.bot.wait_until_ready()
    
    def stop_monitoring(self):
        """Stop the current observer"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("Stopped monitoring")
    
    async def start_monitoring_directory(self, session_dir):
        """Start monitoring a specific session directory"""
        if not os.path.exists(session_dir):
            logger.error(f"Session directory does not exist: {session_dir}")
            return False
        
        # List ADM files to verify access
        try:
            files = os.listdir(session_dir)
            adm_files = [f for f in files if f.endswith('.ADM')]
            logger.info(f"Found {len(adm_files)} ADM files in {session_dir}")
            for f in adm_files:
                logger.info(f"  - {f}")
        except Exception as e:
            logger.error(f"Error listing directory: {e}")
            return False
        
        # Initialize file positions for existing ADM files
        for file in os.listdir(session_dir):
            if file.endswith('.ADM'):
                file_path = os.path.join(session_dir, file)
                try:
                    # Start from end of existing files to only catch new entries
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(0, 2)  # Seek to end
                        if not self._handler:
                            self._handler = ADMFileHandler(self.process_log_lines)
                        self._handler.last_position[file_path] = f.tell()
                    logger.info(f"Initialized monitoring for: {file_path}")
                except Exception as e:
                    logger.error(f"Error initializing file {file_path}: {e}")
        
        # Create event handler if it doesn't exist
        if not self._handler:
            self._handler = ADMFileHandler(self.process_log_lines)
        
        # Use PollingObserver for Docker compatibility
        self.observer = PollingObserver(timeout=POLL_INTERVAL)
        self.observer.schedule(self._handler, session_dir, recursive=False)
        self.observer.start()
        
        self.current_session_dir = session_dir
        logger.info(f"Started POLLING monitoring of: {session_dir}")
        logger.info(f"Polling interval: {POLL_INTERVAL} seconds")
        
        return True
    
    @tasks.loop(seconds=CHECK_NEW_DIR_INTERVAL)
    async def check_for_new_session(self):
        """Periodically check if a new session directory has been created"""
        most_recent = self.get_most_recent_session_directory()
        
        if most_recent and most_recent != self.current_session_dir:
            logger.info(f"New session directory detected: {most_recent}")
            logger.info(f"Switching from {self.current_session_dir} to {most_recent}")
            
            # Stop current monitoring
            self.stop_monitoring()
            
            # Start monitoring new directory
            await self.start_monitoring_directory(most_recent)
    
    @check_for_new_session.before_loop
    async def before_check_new_session(self):
        """Wait for bot to be ready before starting the loop"""
        await self.bot.wait_until_ready()
    
    async def initial_setup(self):
        """Initial setup - find and start monitoring the most recent session"""
        logger.info(f"Starting initial setup for logs directory: {self.adm_log_directory}")
        
        if not os.path.exists(self.adm_log_directory):
            logger.error(f"Base logs directory does NOT exist: {self.adm_log_directory}")
            logger.error("Please verify the path and ensure it's properly mounted!")
            return
        
        logger.info(f"Base logs directory exists: {self.adm_log_directory}")
        
        # Find the most recent session directory
        most_recent = self.get_most_recent_session_directory()
        
        if not most_recent:
            logger.warning("No session directories found. Waiting for server to create one...")
            return
        
        # Start monitoring the most recent directory
        success = await self.start_monitoring_directory(most_recent)
        
        if success:
            # Start the periodic check for new sessions
            self.check_for_new_session.start()
        else:
            logger.error("Failed to start monitoring. Will retry when new session is detected.")
    
    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        self.stop_monitoring()
        if self.check_for_new_session.is_running():
            self.check_for_new_session.cancel()
        if self.check_for_new_session.is_running():
            self.check_for_new_session.cancel()


async def setup(bot):
    """Setup function called when loading the cog"""
    # Get the base logs directory from environment
    adm_log_directory = os.getenv("ADM_LOG_DIRECTORY")
    
    if not adm_log_directory:
        logger.error("ADM_LOG_DIRECTORY environment variable not set!")
        return
    
    logger.info(f"ADM_LOG_DIRECTORY set to: {adm_log_directory}")
    
    cog = PlayerWhitelist(bot, adm_log_directory)
    await bot.add_cog(cog)
    
    # Start monitoring after cog is added
    await cog.initial_setup()