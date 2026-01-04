import os
import sys
import asyncio
import discord
import logging
import dotenv
from discord.ext import commands
from utilities.logging_utils import setup_logger
# from cogs._server_status import server_status
# from cogs._player_check import player_check
from cogs.player_whitelist import PlayerWhitelist

# from cogs.core.server_settings import Settings

COGS_ROOT_PATH = os.path.join(os.path.dirname(__file__), "cogs")

logger = logging.getLogger(__name__)
prefix = "~"
intents = discord.Intents.all()

# This sets the prefix to use for commands.
bot = commands.Bot(command_prefix=commands.when_mentioned_or(prefix), intents=intents)

dotenv.load_dotenv("C:/Users/michelle/Documents/GitHub/RRstatus/.env")

server_ip = os.getenv("SERVER_IP")
# print(server_ip)
rcon_port = os.getenv("RCON_PORT")
# print(rcon_port)
rcon_pass = os.getenv("RCON_PASSWORD")
# print(rcon_pass)

# In this function, we load all the files from the Cogs folder.
# Cogs are just files that hold our commands.
async def load_cogs():
    """
    Loads the directories under the /cogs/ folder,
    then digs through those directories and loads the cogs.
    """
    print("Loading Cogs...")
    failed_to_load = []

    for file in os.listdir(COGS_ROOT_PATH):
        if file.endswith(".py") and not file.startswith("_"):
            cog_path = os.path.join(COGS_ROOT_PATH, file)
            logger.debug(f"Loading Cog: {cog_path}")
            try:
                await bot.load_extension(f"cogs.{file[:-3]}")
                print(f"Loaded Cog: {cog_path}")
            except Exception as e:
                logger.warning(
                    "Failed to load: {%s}.{%s}, {%s}", COGS_ROOT_PATH, file, e
                )
                print(f"Exception loading {file}: {e}")  # Add this for debugging
                failed_to_load.append(f"{file[:-3]}")
    if failed_to_load:
        logger.warning(
            f"Cog loading finished. Failed to load the following cogs: {', '.join(failed_to_load)}"
        )
    else:
        print("Loaded all cogs successfully.")


# In this function, we use an argument or env file to load the Bot-Token.
def load_token_and_run():
    # server_settings_path = "resources"
    # if server_settings_path:
    #     bot.server_settings = Settings(server_settings_path)  # type: ignore
    if len(sys.argv) > 1:
        TOKEN = sys.argv[1]
        bot.run(TOKEN)
    else:
        # print(os.getenv("DISCORD_TOKEN"))
        print("Using token from .env")
        bot.run(os.getenv("DISCORD_TOKEN"))


@bot.event
async def on_ready():
    print(f"{bot.user} [{bot.user.id}] is connected to the following guilds:")
    for guild in bot.guilds:
        print(f"\t- {guild.name}(id: {guild.id})")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

    # print("starting events...")
    player_whitelist_object = PlayerWhitelist(bot)
    player_whitelist_object.check_for_new_session.start()
    # player_check_object = player_check(bot, server_ip, rcon_port, rcon_pass)
    # player_check_object.check.start()
    # player_check_object = server_status(bot, server_ip, rcon_port, rcon_pass)
    # player_check_object.status_check.start()


def main():
    setup_logger(
        level=int(os.getenv("LOGGING_LEVEL", 20)),
        stream_logs=bool(os.getenv("STREAM_LOGS", False)),
    )
    
    # Load cogs before running
    async def startup():
        async with bot:
            await load_cogs()
            await bot.start(os.getenv("DISCORD_TOKEN"))

    asyncio.run(startup())
    load_token_and_run()


if __name__ == "__main__":
    main()
