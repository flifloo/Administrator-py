import functools

from discord import Permissions
from discord.ext import commands
from discord.ext.commands import NoPrivateMessage, NotOwner, MissingPermissions

import db


class ExtensionDisabled(commands.CheckFailure):
    pass


def is_enabled():
    def check(func):
        @functools.wraps(func)
        async def wrapped(*args):
            ctx = args[1]
            if ctx.guild:
                s = db.Session()
                es = s.query(db.ExtensionState).get((args[0].qualified_name, ctx.guild.id))
                s.close()
                if es and not es.state:
                    return
                    # raise ExtensionDisabled()
                return await func(*args)
        return wrapped
    return check


def is_owner():
    def check(func):
        @functools.wraps(func)
        async def wrapped(*args):
            ctx = args[1]
            if not await ctx._discord.is_owner(ctx.author):
                raise NotOwner('You do not own this bot.')
            return await func(*args)
        return wrapped
    return check


def guild_only():
    def check(func):
        @functools.wraps(func)
        async def wrapped(*args):
            if args[1].guild is None:
                raise NoPrivateMessage()
            return await func(*args)
        return wrapped
    return check


def has_permissions(**perms):
    invalid = set(perms) - set(Permissions.VALID_FLAGS)
    if invalid:
        raise TypeError('Invalid permission(s): %s' % (', '.join(invalid)))

    def check(func):
        @functools.wraps(func)
        async def wrapped(*args):
            ctx = args[1]
            ch = ctx.channel
            permissions = ch.permissions_for(ctx.author)

            missing = [perm for perm, value in perms.items() if getattr(permissions, perm) != value]

            if not missing:
                return await func(*args)

            raise MissingPermissions(missing)
        return wrapped
    return check
