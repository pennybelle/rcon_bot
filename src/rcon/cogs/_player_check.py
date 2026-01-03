import discord, logging, psutil
from discord.ext import commands, tasks
from rcon.battleye import Client
# from __main__ import server_ip, rcon_port, rcon_pass

logger = logging.getLogger(__name__)

# Configuration
TIMEOUT = 10  # Connection timeout in seconds


def check_players(ip, port, password):

    try:
        with Client(ip, port, passwd=password) as client:
            player_list = client.run('players')
        
        return str(player_list).splitlines()
            
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
        logging.error(f"Player check failed: {type(e).__name__}: {e}")
        return False


class player_check(commands.Cog):
    def __init__(self, bot, ip, port, password):
        self.bot = bot
        self.ip = ip
        self.port = port
        self.password = password

    @tasks.loop(seconds=10)
    async def check(self):
        # bot = self.bot
        # channel = self.channel
        # app_name = "DayZServer_x64.exe"
        player_list = check_players(self.ip, self.port, self.password)
        await print(player_list)
        # await print(player_list.splitlines())

        # if player_list:
        #     await bot.change_presence(
        #         status=discord.Status.online,
        #         activity=discord.Game(name=self.running)
        #     )
        # else:
        #     await bot.change_presence(
        #         status=discord.Status.dnd,
        #         activity=discord.Game(name=self.not_running)
        #     )


async def setup(bot):
    await bot.add_cog(player_check(bot))
