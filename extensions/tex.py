from urllib.parse import urlencode

from discord import Embed
from discord.ext import commands
from discord_slash import cog_ext, SlashContext, SlashCommandOptionType
from discord_slash.utils import manage_commands

from administrator import slash
from administrator.check import is_enabled
from administrator.logger import logger


extension_name = "TeX"


class TeX(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.polls = {}
        slash.get_cog_commands(self)

    def description(self):
        return "Render TeX formula"

    @cog_ext.cog_slash(name="tex", description="Render a TeX formula", options=[
        manage_commands.create_option("formula", "The TeX formula", SlashCommandOptionType.STRING, True)])
    @is_enabled()
    async def tex(self, ctx: SlashContext, formula: str):
        await ctx.send(content=f"https://chart.apis.google.com/chart?cht=tx&chs=40&{urlencode({'chl': formula})}")


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(TeX(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("TeX")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
