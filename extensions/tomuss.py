import re
from datetime import datetime
from time import mktime

from discord import Embed, Forbidden, HTTPException
from discord.ext import commands, tasks
from discord.ext.commands import BadArgument
from discord_slash import SlashContext, cog_ext, SlashCommandOptionType
from discord_slash.utils import manage_commands
from feedparser import parse

import db
from administrator import slash
from administrator.check import is_enabled
from administrator.logger import logger


extension_name = "tomuss"
logger = logger.getChild(extension_name)
url_re = re.compile(r"https://tomuss\.univ-lyon1\.fr/S/[0-9]{4}/[a-zA-Z]+/rss/.+")


class Tomuss(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tomuss_loop.start()
        slash.get_cog_commands(self)

    def description(self):
        return "PCP Univ Lyon 1"

    @cog_ext.cog_subcommand(base="tomuss", name="set", description="Set your tomuss RSS feed", options=[
        manage_commands.create_option("url", "The RSS URL", SlashCommandOptionType.STRING, True)])
    async def tomuss_set(self, ctx: SlashContext, url: str):
        if not url_re.fullmatch(url):
            raise BadArgument()
        entries = parse(url).entries

        if not entries:
            raise BadArgument()
        last = datetime.fromtimestamp(mktime(sorted(entries, key=lambda e: e.published_parsed)[0].published_parsed))

        s = db.Session()
        t = s.query(db.Tomuss).get(ctx.author.id)
        if t:
            t.url = url
            t.last = last
        else:
            t = db.Tomuss(ctx.author.id, url, last)
        s.add(t)
        s.commit()
        s.close()

        await ctx.channel.send(f"Tomuss RSS set for {ctx.author.mention} \U0001f44d")

    @cog_ext.cog_subcommand(base="tomuss", name="unset", description="Unset your tomuss RSS feed")
    async def tomuss_unset(self, ctx: SlashContext):
        s = db.Session()
        t = s.query(db.Tomuss).get(ctx.author.id)
        if not t:
            raise BadArgument()
        s.delete(t)
        s.commit()
        s.close()
        await ctx.send(content="\U0001f44d")

    @tasks.loop(minutes=5)
    async def tomuss_loop(self):
        s = db.Session()

        for t in s.query(db.Tomuss).all():
            u = await self.bot.fetch_user(t.user_id)
            if not u:
                s.delete(t)
                s.commit()
                continue

            last = t.last.utctimetuple()
            entries = list(filter(lambda e: e.published_parsed > last,
                                  sorted(parse(t.url).entries, key=lambda e: e.published_parsed)))
            if entries:
                embed = Embed(title="Tomuss update !")
                for e in entries:
                    if len(e.title) > 256:
                        title = e.title[:253] + "..."
                    else:
                        title = e.title

                    summary = e.summary.replace("<br />", "\n").replace("<b>", "**").replace("</b>", "**")
                    if len(summary) > 1024:
                        summary = summary[:1021] + "..."

                    embed.add_field(name=title, value=summary)
                try:
                    await u.send(embed=embed)
                except Forbidden:
                    s.delete(t)
                    s.commit()
                    continue
                except HTTPException:
                    await u.send("Too much to send, I can't handle it sorry...")
                finally:
                    t.last = datetime.fromtimestamp(mktime(entries[-1].published_parsed))
                    s.add(t)
                    s.commit()

        s.close()

    def cog_unload(self):
        self.tomuss_loop.stop()


def setup(bot):
    logger.info(f"Loading...")
    try:
        bot.add_cog(Tomuss(bot))
    except Exception as e:
        logger.error(f"Error loading: {e}")
    else:
        logger.info(f"Load successful")


def teardown(bot):
    logger.info(f"Unloading...")
    try:
        bot.remove_cog("Tomuss")
    except Exception as e:
        logger.error(f"Error unloading: {e}")
    else:
        logger.info(f"Unload successful")
