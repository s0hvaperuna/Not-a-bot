import logging
import os
import shlex
import subprocess
import sys
import time
import inspect
from datetime import datetime
from email.utils import formatdate as format_rfc2822
import textwrap
from io import StringIO

import discord
import psutil
from discord.ext.commands import cooldown, BucketType, bot_has_permissions, Group
from discord.ext.commands.errors import BadArgument
from sqlalchemy.exc import SQLAlchemyError

from bot.bot import command
from cogs.cog import Cog
from utils.unzalgo import unzalgo, is_zalgo
from utils.utilities import (random_color, get_avatar, split_string,
                             get_emote_url,
                             send_paged_message)

logger = logging.getLogger('debug')
terminal = logging.getLogger('terminal')


class Utilities(Cog):
    def __init__(self, bot):
        super().__init__(bot)

    @command(ignore_extra=True)
    async def ping(self, ctx):
        """Ping pong"""
        local_delay = datetime.utcnow().timestamp() - ctx.message.created_at.timestamp()
        t = time.perf_counter()
        await ctx.trigger_typing()
        t = time.perf_counter() - t
        message = 'Pong!\n🏓 took {:.0f}ms\nLocal delay {:.0f}ms\nWebsocket ping {:.0f}ms'.format(t*1000, local_delay*1000, self.bot.latency*1000)
        if hasattr(self.bot, 'get_session'):
            sql_t = time.time()
            try:
                self.bot.get_session.execute('SELECT 1').fetchall()
                sql_t = time.time() - sql_t
                message += '\nDatabase ping {:.0f}ms'.format(sql_t * 1000)
            except SQLAlchemyError:
                message += '\nDatabase could not be reached' \

        await ctx.send(message)

    @command(aliases=['e', 'emoji'])
    async def emote(self, ctx, emote: str):
        """Get the link to an emote"""
        emote = get_emote_url(emote)
        if emote is None:
            return await ctx.send('You need to specify an emote. Default (unicode) emotes are not supported ~~yet~~')

        await ctx.send(emote)

    @cooldown(1, 1, type=BucketType.user)
    @command(aliases=['howtoping'])
    async def how2ping(self, ctx, *, user):
        """Searches a user by their name and get the string you can use to ping them"""
        if ctx.guild:
            members = ctx.guild.members
        else:
            members = self.bot.get_all_members()

        def filter_users(predicate):
            for member in members:
                if predicate(member):
                    return member

                if member.nick and predicate(member.nick):
                    return member

        if ctx.message.raw_role_mentions:
            i = len(ctx.invoked_with) + len(ctx.prefix) + 1

            user = ctx.message.clean_content[i:]
            user = user[user.find('@')+1:]

        found = filter_users(lambda u: str(u).startswith(user))
        s = '`<@!{}>` {}'
        if found:
            return await ctx.send(s.format(found.id, str(found)))

        found = filter_users(lambda u: user in str(u))

        if found:
            return await ctx.send(s.format(found.id, str(found)))

        else:
            return await ctx.send('No users found with %s' % user)

    @command(aliases=['src', 'source_code'])
    @cooldown(1, 5, BucketType.user)
    async def source(self, ctx, *cmd):
        """Source code for this bot"""
        if cmd:
            full_name = ' '.join(cmd)
            cmnd = self.bot.all_commands.get(cmd[0])
            if cmnd is None:
                raise BadArgument(f'Command "{full_name}" not found')

            for c in cmd[1:]:
                if not isinstance(cmnd, Group):
                    raise BadArgument(f'Command "{full_name}" not found')

                cmnd = cmnd.get_command(c)

            cmd = cmnd

        if not cmd:
            await ctx.send('You can find the source code for this bot here https://github.com/s0hvaperuna/Not-a-bot')
            return

        source = inspect.getsource(cmd.callback)
        original_source = textwrap.dedent(source)
        source = original_source.replace('```', '`\u200b`\u200b`')  # Put zero width space between backticks so they can be within a codeblock
        source = f'```py\n{source}\n```'
        if len(source) > 2000:
            file = discord.File(StringIO(original_source), filename=f'{full_name}.py')
            await ctx.send(f'Content was longer than 2000 ({len(source)} > 2000)', file=file)
            return
        await ctx.send(source)

    @command(ignore_extra=True)
    @cooldown(1, 10, BucketType.user)
    async def invite(self, ctx):
        """This bots invite link"""
        await ctx.send('https://discordapp.com/api/oauth2/authorize?client_id=214724376669585409&permissions=1342557248&scope=bot')

    @staticmethod
    def _unpad_zero(value):
        if not isinstance(value, str):
            return
        return value.lstrip('0')

    @command(ignore_extra=True, aliases=['bot', 'about', 'botinfo'])
    @cooldown(2, 5, BucketType.user)
    @bot_has_permissions(embed_links=True)
    async def stats(self, ctx):
        """Get stats about this bot"""
        pid = os.getpid()
        process = psutil.Process(pid)
        uptime = time.time() - process.create_time()
        d = datetime.utcfromtimestamp(uptime)
        uptime = f'{d.day-1}d {d.hour}h {d.minute}m {d.second}s'
        current_memory = round(process.memory_info().rss / 1048576, 2)
        memory_usage = f' Current: {current_memory}MB'
        if sys.platform == 'linux':
            try:
                # use pmap to find the memory usage of this process and turn it to megabytes
                # Since shlex doesn't care about pipes | I have to do this
                s1 = subprocess.Popen(shlex.split('pmap %s' % os.getpid()),
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
                s2 = subprocess.Popen(
                    shlex.split('grep -Po "total +\K([0-9])+(?=K)"'),
                    stdin=s1.stdout, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
                s1.stdin.close()
                memory = round(int(s2.communicate()[0].decode('utf-8')) / 1024, 1)
                usable_memory = str(memory) + 'MB'
                memory_usage = f'{current_memory}MB/{usable_memory} ({(current_memory/memory*100):.1f}%)'

            except:
                logger.exception('Failed to get extended mem usage')

        users = len([a for a in self.bot.get_all_members()])
        guilds = len(self.bot.guilds)

        try:
            # Get the last time the bot was updated
            last_updated = format_rfc2822(os.stat('.git/refs/heads/rewrite').st_mtime, localtime=True)
        except OSError:
            logger.exception('Failed to get last updated')
            last_updated = 'N/A'

        sql = 'SELECT * FROM `command_stats` ORDER BY `uses` DESC LIMIT 3'
        session = self.bot.get_session
        try:
            rows = session.execute(sql)
        except SQLAlchemyError:
            logger.exception('Failed to get command stats')
            top_cmd = 'Failed to get command stats'
        else:
            top_cmd = ''
            i = 1
            for row in rows:
                name = row['parent']
                cmd = row['cmd']
                if cmd:
                    name += ' ' + cmd

                top_cmd += f'{i}. `{name}` with {row["uses"]} uses\n'
                i += 1

        embed = discord.Embed(title='Stats', colour=random_color())
        embed.add_field(name='discord.py version', value=discord.__version__)
        embed.add_field(name='Uptime', value=uptime)
        embed.add_field(name='Servers', value=str(guilds))
        embed.add_field(name='Users', value=str(users))
        embed.add_field(name='Memory usage', value=memory_usage)
        embed.add_field(name='Last updated', value=last_updated)
        embed.add_field(name='Most used commands', value=top_cmd, inline=False)
        embed.set_thumbnail(url=get_avatar(self.bot.user))
        embed.set_author(name=self.bot.user.name, icon_url=get_avatar(self.bot.user))

        await ctx.send(embed=embed)

    @command(name='roles', ignore_extra=True, no_pm=True)
    @cooldown(1, 5, type=BucketType.guild)
    async def get_roles(self, ctx, page=''):
        """Get roles on this server"""
        guild_roles = sorted(ctx.guild.roles, key=lambda r: r.name)
        idx = 0
        if page:
            try:
                idx = int(page) - 1
                if idx < 0:
                    return await ctx.send('Index must be bigger than 0')
            except ValueError:
                return await ctx.send('%s is not a valid integer' % page, delete_after=30)

        roles = 'A total of %s roles\n' % len(guild_roles)
        for role in guild_roles:
            roles += '{}: {}\n'.format(role.name, role.mention)

        roles = split_string(roles, splitter='\n', maxlen=1990)
        await send_paged_message(self.bot, ctx, roles, starting_idx=idx, page_method=lambda p, i: '```{}```'.format(p))

    @command(aliases=['created_at', 'snowflake'], ignore_extra=True)
    @cooldown(1, 5, type=BucketType.guild)
    async def snowflake_time(self, ctx, id: int):
        """Gets creation date from the specified discord id"""
        try:
            int(id)
        except ValueError:
            return await ctx.send("{} isn't a valid integer".format(id))

        await ctx.send(str(discord.utils.snowflake_time(id)))

    @command(name='unzalgo')
    @cooldown(2, 5, BucketType.guild)
    async def unzalgo_(self, ctx, *, text=None):
        if text is None:
            messages = self.bot._connection._messages
            for i in range(-1, -100, -1):
                try:
                    msg = messages[i]
                except IndexError:
                    break

                if msg.channel.id != ctx.channel.id:
                    continue

                if is_zalgo(msg.content):
                    text = msg.content
                    break

        if text is None:
            await ctx.send("Didn't find a zalgo message")
            return

        await ctx.send(unzalgo(text))

    @command()
    @cooldown(1, 120, BucketType.user)
    async def feedback(self, ctx, *, feedback):
        """
        Send feedback of the bot.
        Bug reports should go to https://github.com/s0hvaperuna/Not-a-bot/issues
        """

        webhook = self.bot.config.feedback_webhook
        if not webhook:
            return await ctx.send('This command is unavailable atm')

        json = {'content': feedback,
                'avatar_url': ctx.author.avatar_url,
                'username': ctx.author.name}
        headers = {'Content-type': 'application/json'}

        await self.bot.aiohttp_client.post(webhook, json=json, headers=headers)

    @command(aliases=['bug'], ignore_extra=True)
    @cooldown(1, 10, BucketType.user)
    async def bugreport(self, ctx):
        await ctx.send('If you have noticed a bug in my bot report it here https://github.com/s0hvaperuna/Not-a-bot/issues')


def setup(bot):
    bot.add_cog(Utilities(bot))
