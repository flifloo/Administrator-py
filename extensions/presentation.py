from discord.abc import GuildChannel
from discord.ext import commands
from discord import Message, Role, TextChannel
from discord.ext.commands import BadArgument
from discord_slash import cog_ext, SlashCommandOptionType, SlashContext
from discord_slash.utils import manage_commands

from administrator.check import is_enabled, guild_only, has_permissions
from administrator.logger import logger
from administrator import db, slash
from administrator.utils import event_is_enabled

extension_name = "presentation"
logger = logger.getChild(extension_name)


class Presentation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        slash.get_cog_commands(self)

    def description(self):
        return "Give role to user who make a presentation in a dedicated channel"

    @cog_ext.cog_subcommand(base="presentation", name="set",
                            description="Set the presentation channel and the role to give",
                            options=[
                                manage_commands.create_option("channel", "The presentation channel",
                                                              SlashCommandOptionType.CHANNEL, True),
                                manage_commands.create_option("role", "The role to give",
                                                              SlashCommandOptionType.ROLE, True)
                            ])
    @is_enabled()
    @guild_only()
    @has_permissions(manage_guild=True)
    async def presentation_set(self, ctx: SlashContext, channel: GuildChannel, role: Role):
        if not isinstance(channel, TextChannel):
            raise BadArgument()
        s = db.Session()
        p = s.query(db.Presentation).filter(db.Presentation.guild == ctx.guild.id).first()
        if not p:
            p = db.Presentation(ctx.guild.id, channel.id, role.id)
            s.add(p)
        else:
            p.channel = channel.id
            p.role = role.id
        s.commit()
        await ctx.send(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="presentation", name="disable", description="Disable the auto role give")
    @is_enabled()
    @guild_only()
    @has_permissions(manage_guild=True)
    async def presentation_disable(self, ctx: SlashContext):
        s = db.Session()
        p = s.query(db.Presentation).filter(db.Presentation.guild == ctx.guild.id).first()
        if not p:
            await ctx.send(content="Nothing to disable !")
        else:
            s.delete(p)
            s.commit()
            await ctx.send(content="\U0001f44d")
        s.close()

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.guild is not None:
            s = db.Session()
            if not event_is_enabled(self.qualified_name, message.guild.id, s):
                return
            p = s.query(db.Presentation).filter(db.Presentation.guild == message.guild.id).first()
            s.close()
            if p and p.channel == message.channel.id and p.role not in map(lambda x: x.id, message.author.roles):
                await message.author.add_roles(message.guild.get_role(p.role), reason="Presentation done")


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(Presentation(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Presentation")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
