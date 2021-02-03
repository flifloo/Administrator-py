from traceback import format_exc

from discord.ext import commands
from discord import Embed, Guild
from discord.ext.commands import BadArgument
from discord_slash import cog_ext, SlashContext, SlashCommandOptionType
from discord_slash.utils import manage_commands

import db
from administrator import slash
from administrator.check import has_permissions
from administrator.logger import logger


extension_name = "extension"
logger = logger.getChild(extension_name)


class Extension(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        slash.get_cog_commands(self)

    def description(self):
        return "Manage bot's extensions"

    @cog_ext.cog_subcommand(base="extension", name="list", description="List all enabled extensions")
    @has_permissions(administrator=True)
    async def extension_list(self, ctx: SlashContext):
        s = db.Session()
        embed = Embed(title="Extensions list")
        for es in s.query(db.ExtensionState).filter(db.ExtensionState.guild_id == ctx.guild.id):
            embed.add_field(name=es.extension_name, value="Enable" if es.state else "Disable")
        s.close()
        await ctx.send(embeds=[embed])

    @cog_ext.cog_subcommand(base="extension",
                            name="enable",
                            description="Enable an extensions",
                            options=[manage_commands.create_option("extension", "The extension to enable",
                                                                   SlashCommandOptionType.STRING, True)])
    @has_permissions(administrator=True)
    async def extension_enable(self, ctx: SlashContext, name: str):
        s = db.Session()
        es = s.query(db.ExtensionState).get((name, ctx.guild.id))
        if not es:
            raise BadArgument()
        elif es.state:
            message = "Extension already enabled"
        else:
            es.state = True
            s.add(es)
            s.commit()
            s.close()
            message = "\U0001f44d"
        await ctx.send(content=message)

    @cog_ext.cog_subcommand(base="extension",
                            name="disable",
                            description="Disable an extensions",
                            options=[manage_commands.create_option("extension", "The extension to disable",
                                                                   SlashCommandOptionType.STRING, True)])
    @has_permissions(administrator=True)
    async def extension_disable(self, ctx: SlashContext, name: str):
        s = db.Session()
        es = s.query(db.ExtensionState).get((name, ctx.guild.id))
        if not es:
            raise BadArgument()
        elif not es.state:
            message = "Extension already disabled"
        else:
            es.state = False
            s.add(es)
            s.commit()
            s.close()
            message = "\U0001f44d"
        await ctx.send(content=message)

    @commands.group("extension", pass_context=True)
    async def extension(self, ctx: commands.Context):
        pass

    @extension.group("loaded", pass_context=True)
    @commands.is_owner()
    async def extension_loaded(self, ctx: commands.Context):
        embed = Embed(title="Extensions loaded")
        for extension in self.bot.extensions:
            embed.add_field(name=extension, value="Loaded", inline=False)
        await ctx.send(embed=embed)

    @extension.group("load", pass_context=True)
    @commands.is_owner()
    async def extension_load(self, ctx: commands.Context, name: str):
        try:
            self.bot.load_extension(name)
        except Exception as e:
            await ctx.message.add_reaction("\u26a0")
            await ctx.send(f"{e.__class__.__name__}: {e}\n```{format_exc()}```")
        else:
            await ctx.message.add_reaction("\U0001f44d")

    @extension.group("unload", pass_context=True)
    @commands.is_owner()
    async def extension_unload(self, ctx: commands.Context, name: str):
        try:
            self.bot.unload_extension(name)
        except Exception as e:
            await ctx.message.add_reaction("\u26a0")
            await ctx.send(f"{e.__class__.__name__}: {e}\n```{format_exc()}```")
        else:
            await ctx.message.add_reaction("\U0001f44d")

    @extension.group("reload", pass_context=True)
    @commands.is_owner()
    async def extension_reload(self, ctx: commands.Context, name: str):
        try:
            self.bot.unload_extension(name)
            self.bot.load_extension(name)
        except Exception as e:
            await ctx.message.add_reaction("\u26a0")
            await ctx.send(f"{e.__class__.__name__}: {e}\n```{format_exc()}```")
        else:
            await ctx.message.add_reaction("\U0001f44d")

    @commands.Cog.listener()
    async def on_ready(self):
        s = db.Session()
        for guild in self.bot.guilds:
            for extension in filter(lambda x: x not in ["Extension", "Help"], self.bot.cogs):
                e = s.query(db.Extension).get(extension)
                if not e:
                    s.add(db.Extension(extension))
                    s.commit()
                es = s.query(db.ExtensionState).get((extension, guild.id))
                if not es:
                    s.add(db.ExtensionState(extension, guild.id))
                    s.commit()
        s.close()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild):
        s = db.Session()
        for extension in s.query(db.Extension).all():
            s.add(db.ExtensionState(extension.name, guild.id))
        s.commit()
        s.close()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild):
        s = db.Session()
        for es in s.query(db.ExtensionState).filter(db.ExtensionState.guild_id == guild.id):
            s.delete(es)
        s.commit()
        s.close()

    def cog_unload(self):
        slash.remove_cog_commands(self)


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
