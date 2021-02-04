from discord.ext import commands
from discord.ext.commands import CommandNotFound, MissingRequiredArgument, BadArgument, MissingPermissions, \
    NoPrivateMessage, NotOwner
from discord_slash import SlashContext

from administrator.check import ExtensionDisabled
from administrator.logger import logger


extension_name = "help"
logger = logger.getChild(extension_name)


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def description(self):
        return "Give help and command list"

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        await self.error_handler(ctx, error)

    @commands.Cog.listener()
    async def on_slash_command_error(self, ctx: SlashContext, error: Exception):
        await self.error_handler(ctx, error)

    async def error_handler(self, ctx, error: Exception):
        if isinstance(error, CommandNotFound):
            await self.reaction(ctx, "\u2753")
        elif isinstance(error, MissingRequiredArgument) or isinstance(error, BadArgument):
            await self.reaction(ctx, "\u274C")
        elif isinstance(error, NotOwner) or isinstance(error, MissingPermissions) \
                or isinstance(error, NoPrivateMessage):
            await self.reaction(ctx, "\U000026D4")
        elif isinstance(error, ExtensionDisabled):
            await self.reaction(ctx, "\U0001F6AB")
        else:
            await ctx.send(content="An error occurred !")
            raise error

    @staticmethod
    async def reaction(ctx, react: str):
        m = getattr(ctx, "message", None)
        if m:
            await m.add_reaction(react)
        else:
            await ctx.send(content=react)


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.help_command = None
        bot.add_cog(Help(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Help")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
