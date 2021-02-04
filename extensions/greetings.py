from discord.ext import commands
from discord import Member, Embed, Forbidden
from discord_slash import cog_ext, SlashContext, SlashCommandOptionType
from discord_slash.utils import manage_commands

from administrator.check import is_enabled, guild_only, has_permissions
from administrator.logger import logger
from administrator import db, slash
from administrator.utils import event_is_enabled


extension_name = "greetings"
logger = logger.getChild(extension_name)


class Greetings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        slash.get_cog_commands(self)

    def description(self):
        return "Setup join and leave message"

    @cog_ext.cog_subcommand(base="greetings", name="set",
                            description="Set the greetings message\n`{}` will be replace by the username",
                            options=[
                                manage_commands.create_option("type", "The join or leave message",
                                                              SlashCommandOptionType.STRING, True,
                                                              [manage_commands.create_choice("join", "join"),
                                                               manage_commands.create_choice("leave", "leave")]),
                                manage_commands.create_option("message", "The message", SlashCommandOptionType.STRING,
                                                              True)
                            ])
    @is_enabled()
    @guild_only()
    @has_permissions(manage_guild=True)
    async def greetings_set(self, ctx: SlashContext, message_type: str, message: str):
        s = db.Session()
        m = s.query(db.Greetings).filter(db.Greetings.guild == ctx.guild.id).first()
        if not m:
            m = db.Greetings(ctx.guild.id)
            s.add(m)
        setattr(m, message_type+"_enable", True)
        setattr(m, message_type+"_message", message.replace("\\n", '\n'))
        s.commit()
        await ctx.send(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="greetings", name="show",
                            description="Show the greetings message",
                            options=[manage_commands.create_option("type", "The join or leave message",
                                                                   SlashCommandOptionType.STRING, True,
                                                                   [manage_commands.create_choice("join", "join"),
                                                                    manage_commands.create_choice("leave", "leave")])])
    @is_enabled()
    @guild_only()
    @has_permissions(manage_guild=True)
    async def greetings_show(self, ctx: SlashContext, message_type: str):
        s = db.Session()
        m = s.query(db.Greetings).filter(db.Greetings.guild == ctx.guild.id).first()
        s.close()
        if not m:
            await ctx.send(content=f"No {message_type} message set !")
        else:
            if message_type == "join":
                await ctx.send(embeds=[m.join_embed(ctx.guild.name, str(ctx.author))])
            else:
                await ctx.send(content=m.leave_msg(str(ctx.author)))

    @cog_ext.cog_subcommand(base="greetings", name="toggle",
                            description="Enable or disable the greetings message",
                            options=[manage_commands.create_option("type", "The join or leave message",
                                                                   SlashCommandOptionType.STRING, True,
                                                                   [manage_commands.create_choice("join", "join"),
                                                                    manage_commands.create_choice("leave", "leave")])])
    @is_enabled()
    @guild_only()
    @has_permissions(manage_guild=True)
    async def greetings_toggle(self, ctx: SlashContext, message_type: str):
        s = db.Session()
        m = s.query(db.Greetings).filter(db.Greetings.guild == ctx.guild.id).first()
        if not m:
            await ctx.send(content=f"No {message_type} message set !")
        else:
            setattr(m, message_type+"_enable", not getattr(m, message_type+"_enable"))
            s.commit()
            await ctx.send(content=f"{message_type.title()} message is " +
                                   ("enable" if getattr(m, message_type+"_enable") else "disable"))
        s.close()

    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        s = db.Session()
        if not event_is_enabled(self.qualified_name, member.guild.id, s):
            return
        m = s.query(db.Greetings).filter(db.Greetings.guild == member.guild.id).first()
        s.close()
        if m and m.join_enable:
            embed = m.join_embed(member.guild.name, str(member))
            try:
                await member.send(embed=embed)
            except Forbidden:
                await member.guild.system_channel.send(member.mention, embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: Member):
        s = db.Session()
        if not event_is_enabled(self.qualified_name, member.guild.id, s):
            return
        m = s.query(db.Greetings).filter(db.Greetings.guild == member.guild.id).first()
        s.close()
        if m and m.leave_enable:
            await member.guild.system_channel.send(m.leave_msg(str(member)))

    def cog_unload(self):
        slash.remove_cog_commands(self)


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(Greetings(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Greetings")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
