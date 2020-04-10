from discord.ext import commands
from discord import Member, VoiceState, Embed, Reaction, Guild
from discord.ext.commands import CommandNotFound

from bot_bde.logger import logger


extension_name = "speak"
logger = logger.getChild(extension_name)


class Speak(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.strict = False
        self.voice_chan = None
        self.waiting = []
        self.lastSpeaker = None
        self.reaction = []
        self.lastReaction = None
        self.voice_message = None
        self.last_message = None

    @commands.group("speak", pass_context=True)
    @commands.guild_only()
    async def speak(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            raise CommandNotFound

    @speak.group("help", pass_context=True)
    @commands.guild_only()
    async def speak_help(self, ctx: commands.Context):
        embed = Embed(title="Speak help")
        embed.add_field(name="speak setup [strict]",
                        value="Set your current voice channel as the speak channel", inline=False)
        embed.add_field(name="speak mute", value="Mute everyone on the speak channel except you", inline=False)
        embed.add_field(name="speak unmute", value="Unmute everyone on the speak channel except you", inline=False)
        await ctx.send(embed=embed)

    @speak.group("setup", pass_context=True)
    @commands.guild_only()
    async def speak_setup(self, ctx: commands.Context, *args):
        if not ctx.author.voice.channel.permissions_for(ctx.author).mute_members:
            await ctx.message.add_reaction("\u274C")
        else:
            self.voice_chan = ctx.author.voice.channel.id
            embed = Embed(title="Speak \U0001f508")
            embed.add_field(name="Waiting list \u23f3", value="Nobody", inline=False)
            embed.add_field(name="Reactions",
                            value="\U0001f5e3 speak !\n"
                                  "\u2757 react to speaker\n"
                                  "\u27A1 Next\n"
                                  "\U0001F512 Strict\n"
                                  "\u274C clear the speak\n"
                                  "Remove your reaction to remove from list",
                            inline=False)
            self.voice_message = await ctx.send(embed=embed)
            for reaction in ["\U0001f5e3", "\u2757", "\u27A1", "\U0001F512", "\u274C"]:
                await self.voice_message.add_reaction(reaction)
            self.voice_message = await self.voice_message.channel.fetch_message(self.voice_message.id)

    @speak.group("mute", pass_context=True)
    @commands.guild_only()
    async def speak_mute(self, ctx: commands.Context):
        if ctx.author.voice is None or ctx.author.voice.channel is None or \
                not ctx.author.voice.channel.permissions_for(ctx.author).mute_members:
            await ctx.message.add_reaction("\u274C")
        else:
            for client in ctx.author.voice.channel.members:
                if client != ctx.author and not client.bot:
                    await client.edit(mute=True)
            await ctx.message.add_reaction("\U0001f44d")

    @speak.group("unmute", pass_context=True)
    @commands.guild_only()
    async def speak_unmute(self, ctx: commands.Context):
        if ctx.author.voice is None or ctx.author.voice.channel is None or \
                not ctx.author.voice.channel.permissions_for(ctx.author).mute_members:
            await ctx.message.add_reaction("\u274C")
        else:
            for client in ctx.author.voice.channel.members:
                if not client.bot:
                    await client.edit(mute=False)
            await ctx.message.add_reaction("\U0001f44d")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState):
        if self.voice_chan and self.strict and \
                (before is None or before.channel is None or before.channel.id != self.voice_chan) and\
                (after is not None and after.channel is not None and after.channel.id == self.voice_chan) and \
                not (self.lastSpeaker and member.id == self.lastSpeaker) and \
                not (self.reaction and member.id == self.lastReaction):
            await member.edit(mute=True)
        elif self.voice_chan and \
                (before is not None and before.channel is not None and before.channel.id == self.voice_chan) and\
                (after is not None and after.channel is not None and after.channel.id != self.voice_chan):
            await member.edit(mute=False)

    async def cog_after_invoke(self, ctx: commands.Context):
        await ctx.message.delete(delay=30)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Member):
        if not user.bot:
            if reaction.message.id == self.voice_message.id:
                if str(reaction.emoji) == "\U0001f5e3":
                    await self.speak_action(reaction, user)
                elif str(reaction.emoji) == "\u2757":
                    await self.speak_react_action(reaction, user)
                elif str(reaction.emoji) == "\u27A1":
                    await self.speak_next_action(reaction, user)
                elif str(reaction.emoji) in ["\U0001F512", "\U0001F513"]:
                    await self.speak_strict_action(reaction, user)
                elif str(reaction.emoji) == "\u274C":
                    await self.speak_clear_action(reaction, user)
                else:
                    await reaction.remove(user)
                await self.update_list(reaction.message.channel.guild)

    async def speak_action(self, reaction: Reaction, user: Member):
        if user.voice is None or user.voice.channel is None or \
                self.voice_chan is None or \
                user.voice.channel.id != self.voice_chan or \
                user.id in self.waiting:
            await reaction.remove(user)
        else:
            self.waiting.append(user.id)

    async def speak_react_action(self, reaction: Reaction, user: Member):
        if user.voice is None or user.voice.channel is None or self.voice_chan is None or \
                user.voice.channel.id != self.voice_chan or user.id in self.reaction or \
                self.lastSpeaker is None or self.lastSpeaker == user.id:
            await reaction.remove(user)
        else:
            self.reaction.append(user.id)

    async def speak_next_action(self, reaction: Reaction, user: Member):
        await reaction.remove(user)
        if self.voice_chan and \
                reaction.message.guild.get_channel(self.voice_chan).permissions_for(user).mute_members:
            if self.last_message:
                await self.last_message.delete()
            if self.lastReaction:
                user: Member = reaction.message.guild.get_member(self.lastReaction)
                self.reaction.remove(self.lastReaction)
                if self.strict:
                    await user.edit(mute=True)
                await self.voice_message.reactions[1].remove(user)
            if self.lastSpeaker and len(self.reaction) == 0:
                user: Member = reaction.message.guild.get_member(self.lastSpeaker)
                self.waiting.remove(self.lastSpeaker)
                if self.strict:
                    await user.edit(mute=True)
                await self.voice_message.reactions[0].remove(user)
            if len(self.reaction) != 0 and self.lastSpeaker is not None:
                user: Member = reaction.message.guild.get_member(self.reaction[0])
                self.lastReaction = self.reaction[0]
                self.last_message = await reaction.message.channel.send(
                    f"{user.mention} react on {reaction.message.guild.get_member(self.lastSpeaker).mention} speak !")
                if self.strict:
                    await user.edit(mute=False)
            elif len(self.waiting) != 0:
                user: Member = reaction.message.guild.get_member(self.waiting[0])
                self.lastSpeaker = self.waiting[0]
                self.lastReaction = None
                self.last_message = await reaction.message.channel.send(f"It's {user.mention} turn")
                if self.strict:
                    await user.edit(mute=False)
            else:
                self.lastSpeaker = None
                self.lastReaction = None
                self.last_message = await reaction.message.channel.send("Nobody left !")

    async def speak_strict_action(self, reaction: Reaction, user: Member):
        if not self.voice_chan or \
                not reaction.message.guild.get_channel(self.voice_chan).permissions_for(user).mute_members:
            await reaction.remove(user)
        else:
            replace = ["\U0001F512", "\U0001F513"] if not self.strict else ["\U0001F513", "\U0001F512"]
            self.strict = not self.strict
            if self.strict:
                for client in user.voice.channel.members:
                    if client != user and not client.bot and \
                            not (self.lastSpeaker and client.id == self.lastSpeaker) and \
                            not (self.reaction and client.id == self.lastReaction):
                        await client.edit(mute=True)
            embed = self.voice_message.embeds[0]
            field = embed.fields[1]
            embed.remove_field(1)
            embed.add_field(name=field.name, value=field.value.replace(replace[0], replace[1]), inline=False)
            await self.voice_message.edit(embed=embed)
            self.voice_message = await self.voice_message.channel.fetch_message(self.voice_message.id)
            await reaction.remove(user)

    async def speak_clear_action(self, reaction: Reaction, user: Member):
        speak_channel = reaction.message.guild.get_channel(self.voice_chan)
        if not self.voice_chan or not speak_channel.permissions_for(user).mute_members:
            await reaction.remove(user)
        else:
            self.waiting = []
            self.lastSpeaker = None
            self.reaction = []
            self.lastReaction = None
            for client in speak_channel.members:
                if not client.bot:
                    await client.edit(mute=False)
            self.strict = False
            self.voice_chan = None
            if self.last_message:
                await self.last_message.delete()
                self.last_message = None
            await self.voice_message.delete()
            self.voice_message = None

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: Reaction, user: Member):
        if not user.bot:
            if reaction.message.id == self.voice_message.id:
                if str(reaction.emoji) == "\U0001f5e3" and user.id in self.waiting and user.id != self.lastSpeaker:
                    self.waiting.remove(user.id)
                elif str(reaction.emoji) == "\u2757" and user.id in self.reaction and user.id != self.lastReaction:
                    self.reaction.remove(user.id)
                await self.update_list(reaction.message.channel.guild)

    async def update_list(self, guild: Guild):
        if self.voice_message:
            persons = []
            if len(self.reaction) != 0:
                for i, reaction in enumerate(self.reaction):
                    persons.append(f"Reaction N°{i+1}: {guild.get_member(reaction).display_name}")
            for i, speaker in enumerate(self.waiting):
                persons.append(f"N°{i+1}: {guild.get_member(speaker).display_name}")
            if len(persons) == 0:
                persons = "Nobody"
            else:
                persons = "\n".join(persons)
            embed = self.voice_message.embeds[0]
            field = embed.fields[0]
            embed.remove_field(0)
            embed.insert_field_at(0, name=field.name, value=persons, inline=True)
            await self.voice_message.edit(embed=embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if ctx.invoked_with == extension_name or \
                (ctx.command.root_parent is not None and ctx.command.root_parent.name == extension_name):
            if isinstance(error, CommandNotFound):
                await ctx.message.add_reaction("\u2753")
                await ctx.message.delete(delay=30)
            else:
                await ctx.send("An error occurred !")
                raise error


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(Speak(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Speak")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
