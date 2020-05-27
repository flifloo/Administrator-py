import re
from datetime import datetime, timedelta

from discord.ext import commands
from discord import Embed
from discord.ext.commands import CommandNotFound, BadArgument, MissingRequiredArgument
from discord.ext import tasks

from bot_bde.logger import logger


extension_name = "reminders"
logger = logger.getChild(extension_name)


def time_pars(s: str) -> timedelta:
    match = re.fullmatch(r"(?:([0-9]+)W)*(?:([0-9]+)D)*(?:([0-9]+)H)*(?:([0-9]+)M)*(?:([0-9]+)S)*", s.upper().replace(" ", "").strip())
    if match:
        w, d, h, m, s = match.groups()
        if any([w, d, h, m, s]):
            w, d, h, m, s = [i if i else 0 for i in [w, d, h, m, s]]
            return timedelta(weeks=int(w), days=int(d), hours=int(h), minutes=int(m), seconds=int(s))
    raise BadArgument()


class Reminders(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tasks = []

    @commands.group("reminder", pass_context=True)
    async def reminder(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            raise CommandNotFound()

    @reminder.group("help", pass_context=True)
    async def reminder_help(self, ctx: commands.Context):
        embed = Embed(title="Reminder help")
        embed.add_field(name="speak add <message> <time>", value="Add a reminder to your reminders list\n"
                                                                 "Time: ?D?H?M?S", inline=False)
        embed.add_field(name="speak list", value="Show your tasks list", inline=False)
        embed.add_field(name="speak remove [N°]", value="Show your tasks list with if no id given\n"
                                                        "Remove the task withe the matching id", inline=False)
        await ctx.send(embed=embed)

    @reminder.group("add", pass_context=True)
    async def reminder_add(self, ctx: commands.Context, message: str, time: str):
        time = time_pars(time)
        now = datetime.now()
        self.tasks.append({
            "date": now + time,
            "create": now,
            "user": ctx.author.id,
            "message": message,
            "channel": ctx.channel.id,
        })

        hours, seconds = divmod(time.seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        await ctx.send(f"""Remind you in {f"{time.days}d {hours}h {minutes}m {seconds}s"
            if time.days > 0 else f"{hours}h {minutes}m {seconds}s"
            if hours > 0 else f"{minutes}m {seconds}s"
            if minutes > 0 else f"{seconds}s"} !""")

    @reminder.group("list", pass_context=True)
    async def reminder_list(self, ctx: commands.Context):
        embed = Embed(title="Tasks list")
        for i, t in enumerate(self.tasks):
            if t["user"] == ctx.author.id:
                embed.add_field(name=t["date"], value=f"N°{i} | {t['message']}", inline=False)
        await ctx.send(embed=embed)

    @reminder.group("remove", pass_context=True)
    async def reminder_remove(self, ctx: commands.Context, n: int = None):
        tasks =list(filter(lambda t: t["user"] == ctx.author.id, self.tasks))
        if n is None:
            await ctx.invoke(self.reminder_list)
        elif n >= len(tasks):
            raise BadArgument()
        else:
            del self.tasks[n]
            await ctx.message.add_reaction("\U0001f44d")

    @tasks.loop(minutes=1)
    async def reminders_loop(self):
        trash = []
        for t in self.tasks:
            if t["date"] <= datetime.now():
                self.bot.loop.create_task(self.reminder_exec(t))
                trash.append(t)

        for t in trash:
            del self.tasks[self.tasks.index(t)]

    async def reminder_exec(self, task: dict):
        embed = Embed(title="You have a reminder !")
        embed.add_field(name=task["date"], value=task["message"])
        await self.bot.get_channel(task["channel"]).send(f"<@{task['user']}>", embed=embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if ctx.invoked_with == "reminder" or \
                (ctx.command.root_parent and ctx.command.root_parent.name == "reminder"):
            if isinstance(error, CommandNotFound)\
                    or isinstance(error, BadArgument)\
                    or isinstance(error, MissingRequiredArgument):
                await ctx.message.add_reaction("\u2753")
                await ctx.message.delete(delay=30)
            else:
                await ctx.send("An error occurred !")
                raise error


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