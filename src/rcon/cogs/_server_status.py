import discord, logging, psutil
from discord.ext import commands, tasks
from rcon.battleye import Client

logger = logging.getLogger(__name__)

# Configuration
TIMEOUT = 10  # Connection timeout in seconds


def check_server_via_rcon(ip, port, password):
    """
    Check server status using RCON with the proper BattlEye client library.
    Simply connecting successfully means the server is up - we don't need to run commands.
    Returns True if we can connect and authenticate.
    """
    logging.info("-" * 40)
    logging.info(f"Checking DayZ server at {ip}:{port}")
    
    try:
        # Simply try to connect - if this succeeds, the server is up!
        with Client(ip, int(port), passwd=password, timeout=TIMEOUT) as client:
            # Connection successful - server is up and RCON is working
            logging.info("Server is UP - RCON login successful")
            return True
            
    except TimeoutError:
        logging.error("Server connection timed out")
        return False
    except ConnectionRefusedError:
        logging.error("Connection refused - server may be down or RCON not enabled")
        return False
    except OSError as e:
        logging.error(f"Socket error: {e}")
        return False
    except Exception as e:
        logging.error(f"Server check failed: {type(e).__name__}: {e}")
        return False


def check_players(ip, port, password):
    try:
        # # Simply try to connect - if this succeeds, the server is up!
        # with Client(ip, int(port), passwd=password, timeout=TIMEOUT) as client:
        #     # Connection successful - server is up and RCON is working
        #     logging.info("Server is UP - RCON login successful")
        #     return True
        with Client(ip, int(port), passwd=password) as client:
            player_list = client.run('players')
        
        return player_list
            
    except TimeoutError:
        logging.error("Server connection timed out")
        return False
    except ConnectionRefusedError:
        logging.error("Connection refused - server may be down or RCON not enabled")
        return False
    except OSError as e:
        logging.error(f"Socket error: {e}")
        return False
    except Exception as e:
        logging.error(f"Server check failed: {type(e).__name__}: {e}")
        return False


class server_status(commands.Cog):
    def __init__(self, bot, ip, port, password):
        self.bot = bot
        self.ip = ip
        self.port = port
        self.password = password
        # self.channel = bot.get_channel(1247743821236928637)  # prod
        # self.channel = bot.get_channel(1247688098016526366) # dev
        self.running = f"✅ Refined RP is up!"
        self.not_running = f"❌ Refined RP is down..."

    # async def change_name(self, channel: discord.VoiceChannel, *, new_name):
    #     await channel.edit(name=new_name)

    @tasks.loop(minutes=0.1)
    async def status_check(self):
        # bot = self.bot
        # # channel = self.channel
        # # app_name = "DayZServer_x64.exe"
        # is_running = check_server_via_rcon(self.ip, self.port, self.password)
        # # print(is_running)

        # if is_running:
        #     await bot.change_presence(
        #         status=discord.Status.online,
        #         activity=discord.Game(name=self.running)
        #     )
        # else:
        #     await bot.change_presence(
        #         status=discord.Status.dnd,
        #         activity=discord.Game(name=self.not_running)
        #     )

        player_list = check_players(self.ip, self.port, self.password)
        print(player_list)


def setup(bot):
    bot.add_cog(server_status(bot))
