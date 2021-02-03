import re

from discord import Embed, Member, Guild, Role, CategoryChannel
from discord.abc import GuildChannel
from discord.errors import Forbidden
from discord.ext import commands
from discord.ext.commands import BadArgument
from discord_slash import cog_ext, SlashContext, SlashCommandOptionType
from discord_slash.utils import manage_commands

import db
from administrator import slash
from administrator.check import is_enabled, guild_only, has_permissions
from administrator.logger import logger
from administrator.utils import event_is_enabled

extension_name = "invite"
logger = logger.getChild(extension_name)
role_mention_re = re.compile(r"<@&[0-9]+>")
channel_mention_re = re.compile(r"<#[0-9]+>")


class Invite(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invites = {}
        slash.get_cog_commands(self)
        self.bot.loop.create_task(self.update_invites())

    def description(self):
        return "Get role from a special invite link"

    @cog_ext.cog_subcommand(base="invite", name="help", description="Help about invite")
    @is_enabled()
    @guild_only()
    @has_permissions(administrator=True)
    async def invite_help(self, ctx: SlashContext):
        embed = Embed(title="Invite help")
        embed.add_field(name="invite create <#channel> <@role>", value="Create a invite link to a role", inline=False)
        embed.add_field(name="invite delete <code>", value="Remove a invite", inline=False)
        await ctx.send(embeds=[embed])

    @cog_ext.cog_subcommand(base="invite", name="create", description="Create a invite link to a role",
                            options=[
                                manage_commands.create_option("channel", "The channel to join",
                                                              SlashCommandOptionType.CHANNEL, True),
                                manage_commands.create_option("role", "The role to give",
                                                              SlashCommandOptionType.ROLE, True)
                            ])
    @is_enabled()
    @guild_only()
    @has_permissions(administrator=True)
    async def invite_add(self, ctx: SlashContext, channel: GuildChannel, role: Role):
        if isinstance(channel, CategoryChannel):
            raise BadArgument()
        inv = await channel.create_invite()
        s = db.Session()
        s.add(db.InviteRole(ctx.guild.id, inv.code, role.id))
        s.commit()
        s.close()
        await ctx.send(content=f"Invite created: `{inv.url}`")

    @cog_ext.cog_subcommand(base="invite", name="delete", description="Remove a invite", options=[
        manage_commands.create_option("code", "The invitation code", SlashCommandOptionType.STRING, True)])
    @is_enabled()
    @guild_only()
    @has_permissions(administrator=True)
    async def invite_delete(self, ctx: SlashContext, code: str):
        inv = next(filter(lambda i: i.code == code, await ctx.guild.invites()), None)
        if not inv:
            raise BadArgument()

        s = db.Session()
        invite_role = s.query(db.InviteRole).get({"guild_id": ctx.guild.id, "invite_code": code})
        if not invite_role:
            s.close()
            raise BadArgument()
        s.delete(invite_role)
        s.commit()
        s.close()
        await inv.delete()
        await ctx.send(content="\U0001f44d")

    async def update_invites(self):
        for g in self.bot.guilds:
            self.invites[g.id] = await g.invites()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.update_invites()

    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        if not event_is_enabled(self.qualified_name, member.guild.id):
            return
        user_invites = await member.guild.invites()
        for i in self.invites[member.guild.id]:
            for ui in user_invites:
                if i.code == ui.code and i.uses < ui.uses:
                    s = db.Session()
                    invite_role = s.query(db.InviteRole).get({"guild_id": member.guild.id, "invite_code": i.code})
                    s.close()
                    if invite_role:
                        try:
                            await member.add_roles(member.guild.get_role(invite_role.role_id))
                        except Forbidden:
                            pass
        self.invites[member.guild.id] = user_invites

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        if not event_is_enabled(self.qualified_name, invite.guild.id):
            return
        self.invites[invite.guild.id] = await invite.guild.invites()

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        s = db.Session()
        if not event_is_enabled(self.qualified_name, invite.guild.id, s):
            return
        invite_role = s.query(db.InviteRole).get({"guild_id": invite.guild.id, "invite_code": invite.code})
        if invite_role:
            s.delete(invite_role)
            s.commit()
        s.close()
        self.invites[invite.guild.id] = await invite.guild.invites()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild):
        self.invites[guild.id] = await guild.invites()

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild):
        s = db.Session()
        for g in s.query(db.InviteRole).filter(db.InviteRole.guild_id == guild.id).all():
            s.delete(g)
        s.commit()
        s.close()
        del self.invites[guild.id]


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(Invite(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Invite")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
