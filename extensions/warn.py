from discord import Embed, Forbidden, Member, Guild
from discord.ext import commands
from discord.ext.commands import BadArgument
from discord_slash import cog_ext, SlashCommandOptionType, SlashContext
from discord_slash.utils import manage_commands

from administrator import db, slash
from administrator.check import is_enabled, guild_only, has_permissions
from administrator.logger import logger
from administrator.utils import time_pars, seconds_to_time_string

extension_name = "warn"
logger = logger.getChild(extension_name)


class Warn(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        slash.get_cog_commands(self)

    def description(self):
        return "Send warning to user and make custom action after a number of warn"

    @staticmethod
    async def check_warn(ctx: SlashContext, target: Member):
        s = db.Session()
        c = s.query(db.Warn).filter(db.Warn.guild == ctx.guild.id, db.Warn.user == target.id).count()
        a = s.query(db.WarnAction).filter(db.WarnAction.guild == ctx.guild.id, db.WarnAction.count == c).first()
        if a:
            reason = f"Action after {c} warns"
            if a.action == "kick":
                await target.kick(reason=reason)
            elif a.action == "ban":
                await target.ban(reason=reason)
            elif a.action == "mute":
                pass  # Integration with upcoming ban & mute extension

    @cog_ext.cog_subcommand(base="warn", name="add", description="Send a warn to a user", options=[
        manage_commands.create_option("user", "The user", SlashCommandOptionType.USER, True),
        manage_commands.create_option("description", "The description", SlashCommandOptionType.STRING, True)
    ])
    @is_enabled()
    @guild_only()
    @has_permissions(kick_members=True, ban_members=True, mute_members=True)
    async def warn_add(self, ctx: SlashContext, user: Member, description: str):
        s = db.Session()
        s.add(db.Warn(user.id, ctx.author.id, ctx.guild.id, description))
        s.commit()
        s.close()

        try:
            embed = Embed(title="You get warned !", description="A moderator send you a warn", color=0xff0000)
            embed.add_field(name="Description:", value=description)
            await user.send(embed=embed)
        except Forbidden:
            await ctx.send(content="Fail to send warn notification to the user, DM close :warning:")
        else:
            await ctx.send(content="\U0001f44d")
        await self.check_warn(ctx, user)

    @cog_ext.cog_subcommand(base="warn", name="remove", description="Remove a number of warn to a user", options=[
        manage_commands.create_option("user", "The user", SlashCommandOptionType.USER, True),
        manage_commands.create_option("number", "The warn to remove", SlashCommandOptionType.INTEGER, True)
    ])
    @is_enabled()
    @guild_only()
    @has_permissions(kick_members=True, ban_members=True, mute_members=True)
    async def warn_remove(self, ctx: SlashContext, user: Member, number: int):
        s = db.Session()
        ws = s.query(db.Warn).filter(db.Warn.guild == ctx.guild.id, db.Warn.user == user.id).all()
        if number <= 0 or number > len(ws):
            raise BadArgument()
        s.delete(ws[number-1])
        s.commit()
        s.close()
        await ctx.send(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="warn", name="purge", description="Remove all warn of a user", options=[
        manage_commands.create_option("user", "The user", SlashCommandOptionType.USER, True)])
    @is_enabled()
    @guild_only()
    @has_permissions(kick_members=True, ban_members=True, mute_members=True)
    async def warn_purge(self, ctx: SlashContext, user: Member):
        s = db.Session()
        for w in s.query(db.Warn).filter(db.Warn.guild == ctx.guild.id, db.Warn.user == user.id).all():
            s.delete(w)
        s.commit()
        s.close()
        await ctx.send(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="warn", name="list", description="List warn of the guild or a specified user",
                            options=[
                                manage_commands.create_option("user", "The user", SlashCommandOptionType.USER, False)
                            ])
    @is_enabled()
    @guild_only()
    @has_permissions(kick_members=True, ban_members=True, mute_members=True)
    async def warn_list(self, ctx: SlashContext, user: Member = None):
        s = db.Session()
        embed = Embed(title="Warn list")
        ws = {}
        if user:
            ws[user.id] = s.query(db.Warn).filter(db.Warn.guild == ctx.guild.id, db.Warn.user == user.id).all()
        else:
            for w in s.query(db.Warn).filter(db.Warn.guild == ctx.guild.id).all():
                if w.user not in ws:
                    ws[w.user] = []
                ws[w.user].append(w)
        s.close()

        for u in ws:
            warns = [f"{self.bot.get_user(w.author).mention} - {w.date.strftime('%d/%m/%Y %H:%M')}```{w.description}```"
                     for w in ws[u]]
            embed.add_field(name=self.bot.get_user(u), value="\n".join(warns), inline=False)

        await ctx.send(embeds=[embed])

    @cog_ext.cog_subcommand(base="warn", name="actions", description="List all the actions of the guild")
    @is_enabled()
    @guild_only()
    @has_permissions(kick_members=True, ban_members=True, mute_members=True)
    async def warn_actions(self, ctx: SlashContext):
        s = db.Session()
        embed = Embed(title="Warn list")
        ws = {}
        embed.title = "Actions list"
        for a in s.query(db.WarnAction).filter(db.WarnAction.guild == ctx.guild.id).order_by(db.WarnAction.count) \
                .all():
            action = f"{a.action} for {seconds_to_time_string(a.duration)}" if a.duration else a.action
            embed.add_field(name=f"{a.count} warn(s)", value=action, inline=False)
        s.close()

        for u in ws:
            warns = [f"{self.bot.get_user(w.author).mention} - {w.date.strftime('%d/%m/%Y %H:%M')}```{w.description}```"
                     for w in ws[u]]
            embed.add_field(name=self.bot.get_user(u), value="\n".join(warns), inline=False)

        await ctx.send(embeds=[embed])

    @cog_ext.cog_subcommand(base="warn", name="action", description="Set an action for a count of warn", options=[
        manage_commands.create_option("count", "The number of warns", SlashCommandOptionType.INTEGER, True),
        manage_commands.create_option("action", "The action", SlashCommandOptionType.STRING, True, [
            manage_commands.create_choice("mute", "mute"),
            manage_commands.create_choice("kick", "kick"),
            manage_commands.create_choice("ban", "ban"),
            manage_commands.create_choice("nothing", "nothing")
        ]),
        manage_commands.create_option("time", "The duration of the action, ?D?H?M?S",
                                      SlashCommandOptionType.STRING, False)
    ])
    @is_enabled()
    @guild_only()
    @has_permissions(administrator=True)
    async def warn_action(self, ctx: SlashContext, count: int, action: str, time: str = None):
        if count <= 0 or\
                (action not in ["kick", "nothing"] and not action.startswith("mute") and not action.startswith("ban")):
            raise BadArgument()

        s = db.Session()
        a = s.query(db.WarnAction).filter(db.WarnAction.guild == ctx.guild.id, db.WarnAction.count == count).first()

        if action == "nothing":
            if a:
                s.delete(a)
            else:
                raise BadArgument()
        else:
            if time:
                time = time_pars(time).total_seconds()
            if a:
                a.action = action
                a.duration = time
            else:
                s.add(db.WarnAction(ctx.guild.id, count, action, time))

        s.commit()
        s.close()
        await ctx.send(content="\U0001f44d")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild):
        s = db.Session()
        for w in s.query(db.Warn).filter(db.Warn.guild == guild.id).all():
            s.delete(w)
        for a in s.query(db.WarnAction).filter(db.WarnAction.guild == guild.id).all():
            s.delete(a)
        s.commit()
        s.close()


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(Warn(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Warn")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
