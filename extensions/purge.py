from asyncio import sleep

from discord.ext import commands
from discord import Embed, RawReactionActionEvent
from discord_slash import SlashContext, cog_ext

from administrator import slash
from administrator.check import is_enabled, guild_only, has_permissions
from administrator.logger import logger
from administrator.utils import event_is_enabled

extension_name = "purge"
logger = logger.getChild(extension_name)


class Purge(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.purges = {}
        slash.get_cog_commands(self)

    def description(self):
        return "Purge all messages between the command and the next add reaction"

    @cog_ext.cog_slash(name="purge", description="Purge all message delimited by the command to your next reaction")
    @is_enabled()
    @guild_only()
    @has_permissions(manage_messages=True)
    async def purge(self, ctx: SlashContext):
        message = await ctx.channel.send(content="\U0001f44d")
        self.purges[ctx.author.id] = message

        await sleep(2*60)
        if ctx.author.id in self.purges and self.purges[ctx.author.id] == message:
            await message.delete()
            del self.purges[ctx.author.id]

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        if payload.guild_id:
            if not event_is_enabled(self.qualified_name, payload.guild_id):
                return
            user = self.bot.get_user(payload.user_id)
            message = await self.bot.get_guild(payload.guild_id).get_channel(payload.channel_id)\
                .fetch_message(payload.message_id)
            if user.id in self.purges:
                if message.channel == self.purges[user.id].channel:
                    async with message.channel.typing():
                        await message.channel.purge(before=self.purges[user.id], after=message, limit=None)
                        await self.purges[user.id].delete()
                        await message.delete()
                        del self.purges[user.id]


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(Purge(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Purge")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
