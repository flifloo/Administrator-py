from traceback import format_exc

from discord.ext import commands
from discord import Embed
from administrator.logger import logger


extension_name = "extension"
logger = logger.getChild(extension_name)


class Extension(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def description(self):
        return "Manage bot's extensions"

    @commands.group("extension", pass_context=True)
    @commands.is_owner()
    async def extension(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.extension_help)

    @extension.group("help", pass_context=True)
    async def extension_help(self, ctx: commands.Context):
        embed = Embed(title="Extension help")
        embed.add_field(name="extension list", value="List all loaded extensions", inline=False)
        embed.add_field(name="extension load <name>", value="Load an extension", inline=False)
        embed.add_field(name="extension unload <name>", value="Unload an extension", inline=False)
        embed.add_field(name="extension reload <name>", value="Reload an extension", inline=False)
        await ctx.send(embed=embed)

    @extension.group("list", pass_context=True)
    async def extension_list(self, ctx: commands.Context):
        embed = Embed(title="Extensions list")
        for extension in self.bot.extensions:
            embed.add_field(name=extension, value="Loaded", inline=False)
        await ctx.send(embed=embed)

    @extension.group("load", pass_context=True)
    async def extension_load(self, ctx: commands.Context, name: str):
        try:
            self.bot.load_extension(name)
        except Exception as e:
            await ctx.message.add_reaction("\u26a0")
            await ctx.send(f"{e.__class__.__name__}: {e}\n```{format_exc()}```")
        else:
            await ctx.message.add_reaction("\U0001f44d")

    @extension.group("unload", pass_context=True)
    async def extension_unload(self, ctx: commands.Context, name: str):
        try:
            self.bot.unload_extension(name)
        except Exception as e:
            await ctx.message.add_reaction("\u26a0")
            await ctx.send(f"{e.__class__.__name__}: {e}\n```{format_exc()}```")
        else:
            await ctx.message.add_reaction("\U0001f44d")

    @extension.group("reload", pass_context=True)
    async def extension_reload(self, ctx: commands.Context, name: str):
        try:
            self.bot.unload_extension(name)
            self.bot.load_extension(name)
        except Exception as e:
            await ctx.message.add_reaction("\u26a0")
            await ctx.send(f"{e.__class__.__name__}: {e}\n```{format_exc()}```")
        else:
            await ctx.message.add_reaction("\U0001f44d")


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(Extension(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Extension")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
