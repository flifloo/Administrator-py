from datetime import datetime

from discord.ext import commands
from discord import Embed
from discord.ext.commands import BadArgument
from discord.ext import tasks
from discord_slash import SlashContext, cog_ext, SlashCommandOptionType
from discord_slash.utils import manage_commands

from administrator.check import is_enabled
from administrator.logger import logger
from administrator import db, slash
from administrator.utils import time_pars, seconds_to_time_string

extension_name = "reminders"
logger = logger.getChild(extension_name)


class Reminders(commands.Cog, name="Reminder"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        slash.get_cog_commands(self)

    def description(self):
        return "Create and manage reminders"

    @cog_ext.cog_subcommand(base="reminder", name="add", description="Add a reminder to your reminders list", options=[
        manage_commands.create_option("message", "The message", SlashCommandOptionType.STRING, True),
        manage_commands.create_option("time", "When, ?D?H?M?S", SlashCommandOptionType.STRING, True)
    ])
    @is_enabled()
    async def reminder_add(self, ctx: SlashContext, message: str, time: str):
        time = time_pars(time)
        now = datetime.now()
        s = db.Session()
        s.add(db.Task(message, ctx.author.id, ctx.channel.id, now + time, datetime.now()))
        s.commit()
        s.close()

        await ctx.send(content=f"""Remind you in {seconds_to_time_string(time.total_seconds())} !""")

    @cog_ext.cog_subcommand(base="reminder", name="list", description="Show your tasks list")
    @is_enabled()
    async def reminder_list(self, ctx: SlashContext):
        embed = Embed(title="Tasks list")
        s = db.Session()
        for t in s.query(db.Task).filter(db.Task.user == ctx.author.id).all():
            embed.add_field(name=f"N°{t.id} | {t.date.strftime('%d/%m/%Y %H:%M')}", value=f"{t.message}", inline=False)
        s.close()
        await ctx.send(embeds=[embed])

    @cog_ext.cog_subcommand(base="reminder", name="remove", description="Remove the task withe the matching id",
                            options=[
                                manage_commands.create_option("id", "The reminder id",
                                                              SlashCommandOptionType.INTEGER, True)])
    @is_enabled()
    async def reminder_remove(self, ctx: SlashContext, n: int):
        s = db.Session()
        t = s.query(db.Task).filter(db.Task.id == n).first()
        if t and t.user == ctx.author.id:
            s.delete(t)
            s.commit()
            s.close()
            await ctx.send(content="\U0001f44d")
        else:
            s.close()
            raise BadArgument()

    @tasks.loop(minutes=1)
    async def reminders_loop(self):
        s = db.Session()
        for t in s.query(db.Task).filter(db.Task.date <= datetime.now()).all():
            self.bot.loop.create_task(self.reminder_exec(t))
            s.delete(t)

        s.commit()
        s.close()

    async def reminder_exec(self, task: db.Task):
        embed = Embed(title="You have a reminder !")
        user = self.bot.get_user(task.user)
        embed.set_author(name=f"{user.name}#{user.discriminator}", icon_url=user.avatar_url)
        embed.add_field(name=str(task.creation_date.strftime('%d/%m/%Y %H:%M')), value=task.message)
        await (await self.bot.get_channel(task.channel).send(f"{user.mention}", embed=embed)).edit(content="")

    def cog_unload(self):
        self.reminders_loop.stop()


def setup(bot):
    logger.info(f"Loading...")
    try:
        reminders = Reminders(bot)
        bot.add_cog(reminders)
        reminders.reminders_loop.start()
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Reminders")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
