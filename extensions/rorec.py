from discord.abc import GuildChannel
from discord.ext import commands
from discord import Embed, RawReactionActionEvent, RawBulkMessageDeleteEvent, RawMessageDeleteEvent, NotFound, \
    InvalidArgument, HTTPException, TextChannel, Forbidden, Role, Message
from discord.ext.commands import BadArgument
from discord_slash import cog_ext, SlashContext, SlashCommandOptionType
from discord_slash.utils import manage_commands

from administrator import db, slash
from administrator.check import is_enabled, guild_only, has_permissions
from administrator.logger import logger
from administrator.utils import event_is_enabled, get_message_by_url

extension_name = "rorec"
logger = logger.getChild(extension_name)


class RoRec(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        slash.get_cog_commands(self)

    def description(self):
        return "Create role-reaction message to give role from a reaction add"

    @staticmethod
    async def get_message(session: db.Session, ctx: SlashContext, url: str) -> db.RoRec:
        m = session.query(db.RoRec).filter(db.RoRec.message == (await get_message_by_url(ctx, url)).id and
                                           db.RoRec.guild == ctx.guild.id).first()
        if not m:
            raise BadArgument()
        else:
            return m

    async def try_emoji(self, msg: Message, emoji: str):
        try:
            await msg.add_reaction(emoji)
        except (HTTPException, NotFound, InvalidArgument):
            raise BadArgument()
        else:
            await (await msg.channel.fetch_message(msg.id)).remove_reaction(emoji, self.bot.user)

    @cog_ext.cog_subcommand(base="rorec", name="new",
                            description="Create a new role-reaction message on the mentioned channel",
                            options=[
                                manage_commands.create_option("title", "The title",
                                                              SlashCommandOptionType.STRING, True),
                                manage_commands.create_option("channel", "The target channel",
                                                              SlashCommandOptionType.CHANNEL, True),
                                manage_commands.create_option("description", "The description",
                                                              SlashCommandOptionType.STRING, False),
                                manage_commands.create_option("one", "If only one role is packable",
                                                              SlashCommandOptionType.BOOLEAN, False)
                            ])
    @is_enabled()
    @guild_only()
    @has_permissions(manage_roles=True)
    async def rorec_new(self, ctx: SlashContext, title: str, channel: GuildChannel, description: str = "",
                        one: bool = False):
        if not isinstance(channel, TextChannel):
            raise BadArgument()

        embed = Embed(title=title, description=description)
        embed.add_field(name="Roles", value="No role yet...")
        message = await channel.send(embed=embed)
        r = db.RoRec(message.id, channel.id, ctx.guild.id, one)
        s = db.Session()
        s.add(r)
        s.commit()
        s.close()
        await ctx.send(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="rorec", name="edit",
                            description="Edit a role-reaction message title and description",
                            options=[
                                manage_commands.create_option("url", "The message url",
                                                              SlashCommandOptionType.STRING, True),
                                manage_commands.create_option("title", "The new title",
                                                              SlashCommandOptionType.STRING, True),
                                manage_commands.create_option("description", "The new description",
                                                              SlashCommandOptionType.STRING, False)
                            ])
    @is_enabled()
    @guild_only()
    @has_permissions(manage_roles=True)
    async def rorec_edit(self, ctx: SlashContext, url: str, title: str, description: str = ""):
        s = db.Session()
        m = await self.get_message(s, ctx, url)
        s.close()

        message = await ctx.guild.get_channel(m.channel).fetch_message(m.message)
        embed: Embed = message.embeds[0]
        embed.title = title
        embed.description = description
        await message.edit(embed=embed)
        await ctx.send(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="rorec", name="set",
                            description="Add/edit a emoji with linked roles",
                            options=[
                                manage_commands.create_option("url", "The message url",
                                                              SlashCommandOptionType.STRING, True),
                                manage_commands.create_option("emoji", "The emoji",
                                                              SlashCommandOptionType.STRING, True),
                                manage_commands.create_option("role", "The role",
                                                              SlashCommandOptionType.ROLE, True)
                            ])
    @is_enabled()
    @guild_only()
    @has_permissions(manage_roles=True)
    async def rorec_set(self, ctx: SlashContext, url: str, emoji: str, role: Role):
        await ctx.send(content="\U000023f3")
        s = db.Session()
        m = await self.get_message(s, ctx, url)

        await ctx.delete()
        msg = await ctx.channel.send("\U000023f3")
        await self.try_emoji(msg, emoji)

        data = m.get_data()
        data[emoji] = list(map(lambda x: x.id, [role]))
        m.set_data(data)
        await self.rorec_update(m)
        s.commit()
        s.close()
        await msg.edit(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="rorec", name="remove",
                            description="Remove a emoji of a role-reaction message",
                            options=[
                                manage_commands.create_option("url", "The message url",
                                                              SlashCommandOptionType.STRING, True),
                                manage_commands.create_option("emoji", "The emoji",
                                                              SlashCommandOptionType.STRING, True)
                            ])
    @is_enabled()
    @guild_only()
    @has_permissions(manage_roles=True)
    async def rorec_remove(self, ctx: SlashContext, url: str, emoji: str):
        await ctx.send(content="\U000023f3")
        s = db.Session()
        m = await self.get_message(s, ctx, url)

        await ctx.delete()
        msg = await ctx.channel.send("\U000023f3")
        await self.try_emoji(msg, emoji)

        data = m.get_data()
        if emoji not in data:
            raise BadArgument()
        del data[emoji]
        m.set_data(data)

        await self.rorec_update(m)
        s.commit()
        s.close()
        await msg.edit("\U0001f44d")

    @cog_ext.cog_subcommand(base="rorec", name="reload",
                            description="Reload the message and the reactions",
                            options=[manage_commands.create_option("url", "The message url",
                                                                   SlashCommandOptionType.STRING, True)])
    @is_enabled()
    @guild_only()
    @has_permissions(manage_roles=True)
    async def rorec_reload(self, ctx: SlashContext, url: str):
        s = db.Session()
        m = await self.get_message(s, ctx, url)

        await self.rorec_update(m)
        s.close()
        await ctx.send(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="rorec", name="delete",
                            description="Remove a role-reaction message",
                            options=[manage_commands.create_option("url", "The message link",
                                                                   SlashCommandOptionType.STRING, True)])
    @is_enabled()
    @guild_only()
    @has_permissions(manage_roles=True)
    async def rorec_delete(self, ctx: SlashContext, url: str):
        msg = await get_message_by_url(ctx, url)
        s = db.Session()
        await self.get_message(s, ctx, url)
        s.close()
        await msg.delete()
        await ctx.send(content="\U0001f44d")

    async def rorec_update(self, m: db.RoRec):
        channel = self.bot.get_channel(m.channel)
        if not channel:
            pass
        message = await channel.fetch_message(m.message)
        if not message:
            pass
        embed: Embed = message.embeds[0]
        name = embed.fields[0].name
        embed.remove_field(0)
        value = ""
        data = m.get_data()
        await message.clear_reactions()
        for d in data:
            value += f"{d}: "
            value += ", ".join(map(lambda x: self.bot.get_guild(m.guild).get_role(x).mention, data[d]))
            value += "\n"
            await message.add_reaction(d)
        if not value:
            value = "No role yet..."
        embed.add_field(name=name, value=value)
        await message.edit(embed=embed)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, message: RawMessageDeleteEvent):
        s = db.Session()
        r = s.query(db.RoRec).filter(db.RoRec.message == message.message_id).first()
        if r:
            s.delete(r)
            s.commit()
        s.close()

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, messages: RawBulkMessageDeleteEvent):
        s = db.Session()
        for id in messages.message_ids:
            r = s.query(db.RoRec).filter(db.RoRec.message == id).first()
            if r:
                s.delete(r)
        s.commit()
        s.close()

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: GuildChannel):
        if isinstance(channel, TextChannel):
            s = db.Session()
            for r in s.query(db.RoRec).filter(db.RoRec.channel == channel.id).all():
                s.delete(r)
            s.commit()
            s.close()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        s = db.Session()
        if payload.guild_id and not event_is_enabled(self.qualified_name, payload.guild_id, s):
            return
        m = s.query(db.RoRec).filter(db.RoRec.message == payload.message_id).first()
        s.close()
        if m and payload.member.id != self.bot.user.id:
            data = m.get_data()
            emoji = str(payload.emoji)
            if emoji in data:
                guild = self.bot.get_guild(payload.guild_id)
                roles = [guild.get_role(r) for r in data[emoji]]
                add = False

                if m.one:
                    del data[emoji]
                    remove_roles = []
                    [remove_roles.extend(map(lambda x: guild.get_role(x), data[e])) for e in data]
                    await payload.member.remove_roles(*remove_roles, reason="Only one role-reaction message")

                for r in filter(lambda x: x not in payload.member.roles, roles):
                    try:
                        await payload.member.add_roles(r, reason="Role-reaction message")
                        add = True
                    except Forbidden:
                        await payload.member.send("I don't have the permission to add a role to you !")

                if not add:
                    try:
                        await payload.member.remove_roles(*roles, reason="Role-reaction message")
                    except Forbidden:
                        await payload.member.send("I don't have the permission to remove one of your roles !")

            await (await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id))\
                .remove_reaction(payload.emoji, payload.member)


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(RoRec(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("RoRec")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
