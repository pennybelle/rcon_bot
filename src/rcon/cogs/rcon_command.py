import discord, logging
from discord.ext import commands
from rcon.battleye import Client

logger = logging.getLogger(__name__)


class rcon_command(commands.Cog):
    def __init__(self, bot, ip, port, password):
        self.bot = bot
        self.ip = ip
        self.port = port
        self.password = password

        with Client(self.ip, self.port, passwd=self.password) as client:
            response = client.run('status')
            # response = client.run('some_command', 'with', 'some', 'arguments')

        print("status response:", response)

    @commands.slash_command(pass_context=True)
    @commands.has_permissions(administrator=True)
    async def active_players(self):
        with Client(self.ip, self.port, passwd=self.password) as client:
            response = client.run('status')
            # response = client.run('some_command', 'with', 'some', 'arguments')

        print(response)

    # if user does not have permissions, tell command user
    @active_players.error
    async def cog_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
        # print(self.error_count)

        # prevent duplicate responses
        if self.error_count % 2 != 0:
            self.error_count += 1  # prevent duplicate responses
            raise error

        # if missing permissions, respond accordingly
        if isinstance(error, discord.errors.ApplicationCommandInvokeError):
            # print("No Access")
            # self.error_count += 1 # prevent duplicate responses
            pass
        elif isinstance(error, commands.errors.MissingPermissions):
            await ctx.respond("Sorry, you cannot use this command!", ephemeral=True)
            self.error_count += 1  # prevent duplicate responses
            return
        else:
            await ctx.respond(f"Error: {error}", ephemeral=True)
            raise error  # raise other errors to ensure they aren't ignored


def setup(bot):
    bot.add_cog(rcon_command(bot))
