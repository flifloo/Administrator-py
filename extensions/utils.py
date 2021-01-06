from datetime import datetime

from discord import Embed, Guild
from discord.ext import commands
from discord_slash import cog_ext, SlashContext, SlashCommandOptionType
from discord_slash.utils import manage_commands

from administrator import slash
from administrator.check import is_enabled
from administrator.logger import logger


extension_name = "utils"
logger = logger.getChild(extension_name)


class Utils(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        slash.get_cog_commands(self)

    def description(self):
        return "Some tools"

    @commands.group("eval", pass_context=True)
    @commands.is_owner()
    async def eval(self, ctx: commands.Context):
        start = ctx.message.content.find("```python")
        end = ctx.message.content.find("```", start+9)
        command = ctx.message.content[start+9:end]
        try:
            exec("async def __ex(self, ctx):\n" + command.replace("\n", "\n    "))
            out = str(await locals()["__ex"](self, ctx))
            if len(out) > 1994:
                while out:
                    await ctx.send(f"```{out[:1994]}```")
                    out = out[1994:]
            else:
                await ctx.send(f"```{out}```")
        except Exception as e:
            await ctx.send(f"```{e.__class__.__name__}: {e}```")

    @cog_ext.cog_slash(name="ping", description="Return the ping with the discord API")
    @is_enabled()
    async def ping(self, ctx: SlashContext):
        start = datetime.now()
        content = f"Discord WebSocket latency: `{round(self.bot.latency*1000)}ms`"
        await ctx.send(content=content)
        await ctx.edit(content=content+"\n"+f"Bot latency: `{round((datetime.now() - start).microseconds/1000)}ms`")

    @cog_ext.cog_slash(name="info",
                       description="Show information on guild or user specified",
                       options=[manage_commands.create_option("user", "A user", SlashCommandOptionType.USER, False)])
    @is_enabled()
    async def info(self, ctx: SlashContext, user: SlashCommandOptionType.USER = None):
        if user:
            embed = Embed(title=str(user))
            embed.set_author(name="User infos", icon_url=user.avatar_url)
            embed.add_field(name="Display name", value=user.display_name)
            embed.add_field(name="Joined at", value=user.joined_at)
            if user.premium_since:
                embed.add_field(name="Guild premium since", value=user.premium_since)
            embed.add_field(name="Top role", value=user.top_role)
            embed.add_field(name="Created at", value=user.created_at)
            embed.add_field(name="ID", value=user.id)
        else:
            guild: Guild = ctx.guild
            embed = Embed(title=str(guild))
            embed.set_author(name="Guild infos", icon_url=guild.icon_url)
            embed.add_field(name="Emojis", value=f"{str(len(guild.emojis))}/{guild.emoji_limit}")
            embed.add_field(name="Region", value=guild.region)
            embed.add_field(name="Owner", value=str(guild.owner))
            if guild.max_presences:
                embed.add_field(name="Max presences", value=guild.max_presences)
            if guild.max_video_channel_users:
                embed.add_field(name="Max video channel users", value=guild.max_video_channel_users)
            if guild.description:
                embed.add_field(name="Description", value=guild.description)
            embed.add_field(name="Two factor authorisation level", value=guild.mfa_level)
            embed.add_field(name="Verification level", value=guild.verification_level)
            embed.add_field(name="Explicit content filter", value=guild.explicit_content_filter)
            embed.add_field(name="Default notifications", value=guild.default_notifications)
            if guild.features:
                embed.add_field(name="Features", value=guild.features)
            if guild.splash:
                embed.add_field(name="Splash", value=guild.splash)
            embed.add_field(name="Premium",
                            value=f"Tier: {guild.premium_tier} | Boosts {guild.premium_subscription_count}")
            if guild.preferred_locale:
                embed.add_field(name="Preferred locale", value=guild.preferred_locale)
            if guild.discovery_splash:
                embed.add_field(name="Discovery splash", value=guild.discovery_splash)
            embed.add_field(name="Large", value=guild.large)
            embed.add_field(name="Members",
                            value=f"{len(guild.members)}{'/'+str(guild.max_members) if guild.max_members else ''} "
                                  f"| Bans: {len(await guild.bans())} | subscribers: {len(guild.premium_subscribers)}")
            embed.add_field(name="Channels",
                            value=f"Voice: {str(len(guild.voice_channels))} | Text: {str(len(guild.text_channels))} "
                                  "\n" + f"Total: {str(len(guild.channels))} | Categories: {str(len(guild.categories))}"
                            )
            embed.add_field(name="Roles", value=str(len(guild.roles)))
            embed.add_field(name="Invites", value=str(len(await guild.invites())))
            embed.add_field(name="Addons",
                            value=f"Webhooks: {len(await guild.webhooks())} | Integrations: {len(await guild.integrations())}")

            embed.add_field(name="System channel", value=str(guild.system_channel))
            if guild.rules_channel:
                embed.add_field(name="Rules channel", value=str(guild.rules_channel))
            if guild.public_updates_channel:
                embed.add_field(name="Public updates channel", value=str(guild.public_updates_channel))
            embed.add_field(name="Bitrate limit", value=guild.bitrate_limit)
            embed.add_field(name="Filesize limit", value=guild.filesize_limit)
            embed.add_field(name="Chunked", value=guild.chunked)
            embed.add_field(name="Shard ID", value=guild.shard_id)
            embed.add_field(name="Created at", value=guild.created_at)

        await ctx.send(embeds=[embed])

    @cog_ext.cog_slash(name="about", description="Show information about the bot")
    @is_enabled()
    async def about(self, ctx: SlashContext):
        embed = Embed(title=self.bot.user.display_name, description=self.bot.description)
        embed.set_author(name="Administrator", icon_url=self.bot.user.avatar_url, url="https://github.com/flifloo")
        flifloo = self.bot.get_user(177393521051959306)
        embed.set_footer(text=f"Made with ❤️ by {flifloo.display_name}", icon_url=flifloo.avatar_url)
        embed.add_field(name="Owned by",
                        value=(await self.bot.application_info()).owner.display_name)
        embed.add_field(name="Guilds", value=str(len(self.bot.guilds)))
        embed.add_field(name="Extensions", value=str(len(self.bot.extensions)))
        embed.add_field(name="Commands", value=str(len(self.bot.all_commands)+len(slash.commands)))
        embed.add_field(name="Latency", value=f"{round(self.bot.latency*1000)} ms")
        await ctx.send(embeds=[embed])

    def cog_unload(self):
        slash.remove_cog_commands(self)


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(Utils(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Utils")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")



