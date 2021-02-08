import re
from datetime import datetime, timedelta, time
from operator import xor

import ics
import requests
from discord import Embed, DMChannel, TextChannel
from discord.abc import GuildChannel
from discord.ext import commands
from discord.ext import tasks
from discord.ext.commands import BadArgument, MissingPermissions
from discord_slash import cog_ext, SlashCommandOptionType, SlashContext
from discord_slash.utils import manage_commands

from administrator import db, slash
from administrator.check import guild_only, has_permissions, is_enabled
from administrator.logger import logger


extension_name = "calendar"
logger = logger.getChild(extension_name)
url_re = re.compile(r"http:\/\/adelb\.univ-lyon1\.fr\/jsp\/custom\/modules\/plannings\/anonymous_cal\.jsp\?resources="
                    r"([0-9]+)&projectId=([0-9]+)")


def query_calendar(name: str, guild: int) -> db.Calendar:
    s = db.Session()
    c: db.Calendar = s.query(db.Calendar).filter(db.Calendar.server == guild).filter(db.Calendar.name == name).first()
    s.close()
    if not c:
        raise BadArgument()
    return c


class Calendar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        slash.get_cog_commands(self)

    @cog_ext.cog_subcommand(base="calendar", name="define", description="Define a calendar", options=[
        manage_commands.create_option("name", "The name of the calendar", SlashCommandOptionType.STRING, True),
        manage_commands.create_option("url", "The url of the calendar", SlashCommandOptionType.STRING, True)
    ])
    @is_enabled()
    @guild_only()
    @has_permissions(manage_channels=True)
    async def calendar_define(self, ctx: SlashContext, name: str, url: str):
        try:
            ics.Calendar(requests.get(url).text)
        except Exception:
            raise BadArgument()
        m = url_re.findall(url)
        if not m:
            raise BadArgument()

        s = db.Session()
        if s.query(db.Calendar).filter(db.Calendar.server == ctx.guild.id).filter(db.Calendar.name == name).first():
            s.close()
            raise BadArgument()
        s.add(db.Calendar(name, int(m[0][0]), int(m[0][1]), ctx.guild.id))
        s.commit()
        s.close()
        await ctx.send(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="calendar", name="list", description="List all server calendar")
    @is_enabled()
    @guild_only()
    async def calendar_list(self, ctx: SlashContext):
        embed = Embed(title="Calendar list")
        s = db.Session()
        for c in s.query(db.Calendar).filter(db.Calendar.server == ctx.guild.id).all():
            embed.add_field(name=c.name, value=f"resources: {c.resources} | project id: {c.project_id}", inline=False)
        s.close()
        await ctx.send(embeds=[embed])

    @cog_ext.cog_subcommand(base="calendar", name="remove", description="Remove a server calendar", options=[
        manage_commands.create_option("name", "The name of the calendar", SlashCommandOptionType.STRING, True)
    ])
    @guild_only()
    @has_permissions(manage_channels=True)
    async def calendar_remove(self, ctx: SlashContext, name: str):
        s = db.Session()
        c = s.query(db.Calendar).filter(db.Calendar.server == ctx.guild.id).filter(db.Calendar.name == name).first()
        if c:
            s.delete(c)
            s.commit()
            s.close()
            await ctx.send(content="\U0001f44d")
        else:
            s.close()
            raise BadArgument()

    @cog_ext.cog_subcommand(base="calendar", name="day", description="Show the current day or the given day", options=[
        manage_commands.create_option("name", "The name of the calendar", SlashCommandOptionType.STRING, True),
        manage_commands.create_option("date", "A target date", SlashCommandOptionType.STRING, False)
    ])
    @is_enabled()
    @guild_only()
    async def calendar_day(self, ctx: SlashContext, name: str, day: str = None):
        c = query_calendar(name, ctx.guild.id)
        if day is None:
            date = datetime.now().date()
        else:
            try:
                date = datetime.strptime(day, "%d/%m/%Y").date()
            except ValueError:
                raise BadArgument()

        embed = c.day_embed(date)

        s = db.Session()
        if s.is_modified(c):
            s.add(c)
            s.commit()
        s.close()
        await ctx.send(embeds=[embed])

    @cog_ext.cog_subcommand(base="calendar", name="week", description="Show the week or the given week", options=[
        manage_commands.create_option("name", "The name of the calendar", SlashCommandOptionType.STRING, True),
        manage_commands.create_option("date", "A target date", SlashCommandOptionType.STRING, False)
    ])
    @is_enabled()
    @guild_only()
    async def calendar_week(self, ctx: SlashContext, name: str, day: str = None):
        c = query_calendar(name, ctx.guild.id)
        if day is None:
            date = datetime.now().date()
        else:
            try:
                date = datetime.strptime(day, "%d/%m/%Y").date()
            except ValueError:
                raise BadArgument()

        embed = c.week_embed(date)

        s = db.Session()
        if s.is_modified(c):
            s.add(c)
            s.commit()
        s.close()
        await ctx.send(embeds=[embed])

    @cog_ext.cog_subcommand(base="calendar", subcommand_group="notify", name="add",
                            description="Notify you or the giver channel of calendar events",
                            options=[
                                manage_commands.create_option("name", "The name of the calendar",
                                                              SlashCommandOptionType.STRING, True),
                                manage_commands.create_option("channel", "A target channel",
                                                              SlashCommandOptionType.CHANNEL, False)
                            ])
    @is_enabled()
    @guild_only()
    async def calendar_notify_set(self, ctx: SlashContext, name: str, channel: GuildChannel = None):
        await self.add_remove_calendar(ctx, name, channel, True)

    @cog_ext.cog_subcommand(base="calendar", subcommand_group="notify", name="remove",
                            description="Remove the calendar notify of the current user or the given channel",
                            options=[
                                manage_commands.create_option("name", "The name of the calendar",
                                                              SlashCommandOptionType.STRING, True),
                                manage_commands.create_option("channel", "A target channel",
                                                              SlashCommandOptionType.CHANNEL, False)
                            ])
    @is_enabled()
    @guild_only()
    async def calendar_notify_remove(self, ctx: SlashContext, name: str, channel: GuildChannel = None):
        await self.add_remove_calendar(ctx, name, channel, False)

    @staticmethod
    async def add_remove_calendar(ctx: SlashContext, name: str, channel: GuildChannel, action: bool):
        if channel:
            if not isinstance(channel, TextChannel):
                raise BadArgument()
            if not channel.permissions_for(ctx.author).manage_channels:
                raise MissingPermissions(["manage_channels"])
            else:
                m = channel.id
        else:
            if not ctx.author.dm_channel:
                await ctx.author.create_dm()
            m = ctx.author.dm_channel.id

        s = db.Session()
        c = query_calendar(name, ctx.guild.id)
        n = s.query(db.CalendarNotify).filter(db.CalendarNotify.channel == m) \
            .filter(db.CalendarNotify.calendar_id == c.id) \
            .first()

        if action and not n:
            s.add(db.CalendarNotify(m, c.id))
        elif not action and n:
            s.delete(n)
        else:
            s.close()
            raise BadArgument()
        s.commit()
        s.close()

        await ctx.send(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="calendar", subcommand_group="notify", name="list",
                            description="List all notify of all calendar or the given one",
                            options=[
                                manage_commands.create_option("name", "The name of the calendar",
                                                              SlashCommandOptionType.STRING, True)
                            ])
    @is_enabled()
    @guild_only()
    @has_permissions(manage_channels=True)
    async def calendar_notify_list(self, ctx: SlashContext, name: str = None):
        s = db.Session()
        embed = Embed(title="Notify list")
        if name is None:
            calendars = s.query(db.Calendar).filter(db.Calendar.server == ctx.guild.id).all()
        else:
            calendars = [query_calendar(name, ctx.guild.id)]
        for c in calendars:
            notify = []
            for n in c.calendars_notify:
                ch = self.bot.get_channel(n.channel)
                if type(ch) == TextChannel:
                    notify.append(ch.mention)
                elif type(ch) == DMChannel:
                    notify.append(ch.recipient.mention)
            embed.add_field(name=c.name, value="\n".join(notify) or "Nothing here", inline=False)
        await ctx.send(embeds=[embed])

    @tasks.loop(minutes=1)
    async def calendar_notify_loop(self):
        s = db.Session()
        now = datetime.now().astimezone(tz=None)

        for c in s.query(db.Calendar).all():
            if now.time() >= time(hour=20) and c.last_notify.astimezone(tz=None) < now.replace(hour=20, minute=00) and\
                    now.isoweekday() not in [5, 6]:
                c.last_notify = now
                s.add(c)
                s.commit()

                for n in c.calendars_notify:
                    if now.isoweekday() == 7:
                        await n.next_week_resume(self.bot)
                    else:
                        await n.next_day_resume(self.bot)

            for e in c.events(now.date(), now.date()):
                if xor(c.last_notify.astimezone(tz=None) < e.begin - timedelta(minutes=30) <= now,
                       c.last_notify.astimezone(tz=None) < e.begin - timedelta(minutes=10) <= now):
                    c.last_notify = now
                    s.add(c)
                    s.commit()

                    for n in c.calendars_notify:
                        await n.notify(self.bot, e)

                    break
        s.close()

    def cog_unload(self):
        self.calendar_notify_loop.stop()


def setup(bot):
    logger.info(f"Loading...")
    try:
        calendar = Calendar(bot)
        bot.add_cog(calendar)
        calendar.calendar_notify_loop.start()
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Calendar")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
