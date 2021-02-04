import re

from discord import Member, Role
from discord.ext import commands
from discord.ext.commands import BadArgument
from discord_slash import cog_ext, SlashCommandOptionType, SlashContext
from discord_slash.utils import manage_commands

import db
from administrator import slash
from administrator.check import guild_only, has_permissions
from administrator.logger import logger
from administrator.utils import get_message_by_url

extension_name = "PCP"
logger = logger.getChild(extension_name)


class PCP(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        slash.get_cog_commands(self)

    def description(self):
        return "PCP Univ Lyon 1"

    @cog_ext.cog_subcommand(base="pcp", name="join", description="Join your group", options=[
        manage_commands.create_option("group", "The target group to join", SlashCommandOptionType.ROLE, True)])
    @guild_only()
    async def pcp(self, ctx: SlashContext, role: Role):
        s = db.Session()
        p = s.query(db.PCP).get(ctx.guild.id)
        s.close()
        if p and re.fullmatch(p.roles_re, role.name.upper()):
            await ctx.send(content="\U000023f3")

            async def roles() -> list:
                return list(filter(
                    lambda r: re.fullmatch(p.roles_re, r.name.upper()) or
                    (p.start_role_re and re.fullmatch(p.start_role_re, r.name.upper())),
                    (await ctx.guild.fetch_member(ctx.author.id)).roles
                ))

            if not role or role.name in map(lambda r: r.name, await roles()):
                await ctx.delete()
                raise BadArgument()

            while await roles():
                await ctx.author.remove_roles(*(await roles()))

            while role not in (await ctx.guild.fetch_member(ctx.author.id)).roles:
                await ctx.author.add_roles(role)
            await ctx.edit(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="pcp", name="pin", description="Pin a message with the url", options=[
        manage_commands.create_option("url", "message URL", SlashCommandOptionType.STRING, True)
    ])
    @guild_only()
    async def pcp_pin(self, ctx: SlashContext, url: str):
        await self.pin(ctx, url, True)

    @cog_ext.cog_subcommand(base="pcp", name="unpin", description="Unpin a message with the url", options=[
        manage_commands.create_option("url", "message URL", SlashCommandOptionType.STRING, True)
    ])
    @guild_only()
    async def pcp_unpin(self, ctx: SlashContext, url: str):
        await self.pin(ctx, url, False)

    @staticmethod
    async def pin(ctx: SlashContext, url: str, action: bool):
        m = await get_message_by_url(ctx, url)
        if action:
            await m.pin()
            msg = "pinned a message"
        else:
            await m.unpin()
            msg = "unpinned a message"

        await ctx.send(content=f"{ctx.author.mention} {msg}")

    @cog_ext.cog_subcommand(base="pcp", subcommand_group="group", name="fix_vocal",
                            description="Check all text channel permissions to reapply vocal permissions")
    @has_permissions(administrator=True)
    async def pcp_group_fix_vocal(self, ctx: SlashContext):
        s = db.Session()
        p = s.query(db.PCP).get(ctx.guild.id)
        s.close()
        if not p:
            raise BadArgument()

        message = "\U000023f3"
        await ctx.send(content=message)
        for cat in filter(lambda c: re.fullmatch(p.roles_re, c.name.upper()), ctx.guild.categories):
            message += f"\n{cat.name}..."
            await ctx.edit(content=message)
            teachers = []
            for t in cat.text_channels:
                for p in t.overwrites:
                    if isinstance(p, Member):
                        teachers.append(p)
            voc = next(filter(lambda c: c.name == "vocal-1", cat.voice_channels), None)
            for t in teachers:
                await voc.set_permissions(t, view_channel=True)
            message += f"\n{cat.name} done"
            await ctx.edit(content=message)
        message += "\n\U0001f44d"
        await ctx.edit(content=message)

    @cog_ext.cog_subcommand(base="pcp", subcommand_group="group", name="set", description="Set regex for group role",
                            options=[
                                manage_commands.create_option("role", "Roles regex",
                                                              SlashCommandOptionType.STRING, True),
                                manage_commands.create_option("role2", "Start roles regex",
                                                              SlashCommandOptionType.STRING, False)
                            ])
    @has_permissions(administrator=True)
    async def pcp_group_set(self, ctx: SlashContext, roles_re: str, start_role_re: str = None):
        s = db.Session()
        p = s.query(db.PCP).get(ctx.guild.id)
        if p:
            p.roles_re = roles_re.upper()
            p.start_role_re = start_role_re.upper() if start_role_re else None
        else:
            p = db.PCP(ctx.guild.id, roles_re.upper(), start_role_re.upper() if start_role_re else None)
        s.add(p)
        s.commit()
        s.close()
        await ctx.send(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="pcp", subcommand_group="group", name="unset",
                            description="Unset regex for group role")
    @has_permissions(administrator=True)
    async def pcp_group_unset(self, ctx: commands.Context):
        s = db.Session()
        p = s.query(db.PCP).get(ctx.guild.id)
        if not p:
            s.close()
            raise BadArgument()
        s.delete(p)
        s.commit()
        s.close()
        await ctx.message.add_reaction("\U0001f44d")

    @cog_ext.cog_subcommand(base="pcp", subcommand_group="subject", name="add", description="Add a subject to a group",
                            options=[
                                manage_commands.create_option("name", "The subject name",
                                                              SlashCommandOptionType.STRING, True),
                                manage_commands.create_option("group", "The group",
                                                              SlashCommandOptionType.ROLE, True),
                                manage_commands.create_option("teacher", "The teacher",
                                                              SlashCommandOptionType.USER, False)
                            ])
    @has_permissions(administrator=True)
    async def pcp_group_subject_add(self, ctx: SlashContext, name: str, group: Role, teacher: Member = None):
        if teacher and not next(filter(lambda r: r.name == "professeurs", teacher.roles), None):
            raise BadArgument()

        cat = next(filter(lambda c: c.name.upper() == group.name.upper(),
                          ctx.guild.categories), None)
        if not cat:
            raise BadArgument()

        chan = next(filter(lambda c: c.name.upper() == name.upper(), cat.text_channels), None)
        if not chan:
            chan = await cat.create_text_channel(name)
        voc = next(filter(lambda c: c.name == "vocal-1", cat.voice_channels), None)
        if not voc:
            voc = await cat.create_voice_channel("vocal-1")
        if teacher:
            await chan.set_permissions(teacher, read_messages=True)
            await voc.set_permissions(teacher, view_channel=True)

        await ctx.send(content="\U0001f44d")

    @cog_ext.cog_subcommand(base="pcp", subcommand_group="subject", name="bulk",
                            description="Remove a subject to a group", options=[
            manage_commands.create_option("group", "The group", SlashCommandOptionType.ROLE, True),
            manage_commands.create_option("names", "Subjects names", SlashCommandOptionType.STRING, True)
        ])
    @has_permissions(administrator=True)
    async def pcp_group_subject_bulk(self, ctx: SlashContext, group: Role, names: str):
        for n in names.split(" "):
            await self.pcp_group_subject_add.invoke(ctx, n, group)

    @cog_ext.cog_subcommand(base="pcp", subcommand_group="subject", name="remove",description="Bulk subject add",
                            options=[
                                manage_commands.create_option("name", "The subject name",
                                                              SlashCommandOptionType.STRING, True),
                                manage_commands.create_option("group", "The group",
                                                              SlashCommandOptionType.ROLE, True)
                            ])
    @has_permissions(administrator=True)
    async def pcp_group_subject_remove(self, ctx: SlashContext, name: str, group: Role):
        cat = next(filter(lambda c: c.name.upper() == group.name.upper(), ctx.guild.categories), None)
        if not cat:
            raise BadArgument()

        chan = next(filter(lambda c: c.name.upper() == name.upper(), cat.text_channels), None)
        if not chan:
            raise BadArgument()

        await chan.delete()

        await ctx.send(content="\U0001f44d")


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(PCP(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("PCP")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
