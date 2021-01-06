from discord import Intents
from discord_slash import SlashCommand

from administrator.config import config
import db
from discord.ext import commands

bot = commands.Bot(command_prefix=config.get("prefix"), intents=Intents.all())
slash = SlashCommand(bot, auto_register=True, auto_delete=True)

import extensions

bot.run(config.get("token"))
