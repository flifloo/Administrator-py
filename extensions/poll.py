from discord.ext import commands
from discord import Member, Embed, Reaction
from discord.ext.commands import CommandNotFound, MissingRequiredArgument

from bot_bde.logger import logger


extension_name = "poll"
logger = logger.getChild(extension_name)
REACTIONS = []
for i in range(10):
    REACTIONS.append(str(i)+"\ufe0f\u20E3")
REACTIONS.append("\U0001F51F")


class Poll(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.polls = {}

    @commands.group("poll", pass_context=True)
    @commands.guild_only()
    async def poll(self, ctx: commands.Context, name: str, *choices):
        if ctx.invoked_subcommand is None:
            multi = False
            if choices and choices[0] in ["multi", "m"]:
                multi = True
                choices = choices[1:]
            if len(choices) == 0 or len(choices) > 11:
                await ctx.message.add_reaction("\u274C")
            else:
                embed = Embed(title=name)
                for i, choice in enumerate(choices):
                    embed.add_field(name=REACTIONS[i], value=choice, inline=False)
                message = await ctx.send(embed=embed)
                reactions = REACTIONS[0:len(choices)] + ["\U0001F5D1"]
                for reaction in reactions:
                    await message.add_reaction(reaction)
                message = await message.channel.fetch_message(message.id)
                self.polls[message.id] = {"multi": multi, "message": message, "author": ctx.message.author.id}
                await ctx.message.delete()

    @poll.group("help", pass_context=True)
    @commands.guild_only()
    async def speak_help(self, ctx: commands.Context):
        embed = Embed(title="poll help")
        embed.add_field(name="poll ",
                        value="...", inline=False)
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Member):
        if not user.bot and reaction.message.id in self.polls:
            if reaction not in self.polls[reaction.message.id]["message"].reactions:
                await reaction.remove(user)
            elif str(reaction.emoji) == "\U0001F5D1":
                if user.id != self.polls[reaction.message.id]["author"]:
                    await reaction.remove(user)
                else:
                    await self.close_poll(reaction.message.id)
            elif not self.polls[reaction.message.id]["multi"]:
                f = False
                for r in reaction.message.reactions:
                    if str(r.emoji) != str(reaction.emoji):
                        async for u in r.users():
                            if u == user:
                                await r.remove(user)
                                f = True
                                break
                        if f:
                            break

    async def close_poll(self, id: int):
        message = await self.polls[id]["message"].channel.fetch_message(id)
        reactions = message.reactions
        await message.clear_reactions()
        embed = message.embeds[0]
        for i, f in enumerate(embed.fields):
            embed.set_field_at(i, name=f"{f.name} - {reactions[i].count-1}", value=f.value, inline=False)
        await message.edit(embed=embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if ctx.invoked_with == extension_name or \
                (ctx.command.root_parent is not None and ctx.command.root_parent.name == extension_name):
            if isinstance(error, CommandNotFound):
                await ctx.message.add_reaction("\u2753")
                await ctx.message.delete(delay=30)
            if isinstance(error, MissingRequiredArgument):
                await ctx.message.add_reaction("\u274C")
                await ctx.message.delete(delay=30)
            else:
                await ctx.send("An error occurred !")
                raise error


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(Poll(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Poll")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")