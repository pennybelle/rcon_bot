import discord, logging
from discord.ext import commands
from discord import app_commands
from rcon.battleye import Client
from __main__ import server_ip, rcon_port, rcon_pass

logger = logging.getLogger(__name__)


class rcon_command(commands.Cog):
    def __init__(self, bot):
        # print("RCON_COMMAND INIT CALLED") # debug
        self.bot = bot
        self.ip = server_ip
        self.port = int(rcon_port)
        self.password = rcon_pass
        self.error_count = 0

    @app_commands.command(name="active_players", description="Get list of active players")
    @app_commands.default_permissions(administrator=True)
    async def active_players(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            with Client(self.ip, self.port, passwd=self.password) as client:
                response = client.run('players')
            
            await interaction.followup.send(f"```{response}```")
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")


async def setup(bot):
    await bot.add_cog(rcon_command(bot))