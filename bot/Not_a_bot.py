"""
MIT License

Copyright (c) 2017 s0hvaperuna

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import logging

import discord
from discord.ext import commands
from discord.ext.commands import CommandNotFound, CommandError
from discord.ext.commands.view import StringView
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from bot.bot import Bot, Context
from bot import exceptions
from bot.cooldown import CooldownManager
from bot.servercache import ServerCache
from cogs.voting import Poll
from utils.utilities import (split_string, slots2dict, retry)
from bot.globals import BlacklistTypes
from datetime import datetime
from bot.globals import Auth
logger = logging.getLogger('debug')

initial_cogs = [
    'cogs.admin',
    'cogs.audio',
    'cogs.botadmin',
    'cogs.botmod',
    'cogs.command_blacklist',
    'cogs.emotes',
    'cogs.gachiGASM',
    'cogs.hearthstone',
    'cogs.jojo',
    'cogs.logging',
    'cogs.management',
    'cogs.misc',
    'cogs.moderator',
    'cogs.search',
    'cogs.settings',
    'cogs.utils',
    'cogs.voting']


class Object:
    def __init__(self):
        pass


class NotABot(Bot):
    def __init__(self, prefix, conf, perms=None, aiohttp=None, **options):
        super().__init__(prefix, conf, perms, aiohttp, **options)
        cdm = CooldownManager()
        cdm.add_cooldown('oshit', 3, 8)
        self.cdm = cdm
        self._server_cache = ServerCache(self)
        self._perm_values = {'user': 0x1, 'whitelist': 0x0, 'blacklist': 0x2, 'role': 0x4, 'channel': 0x8, 'server': 0x10}
        self._perm_returns = {1: True, 3: False, 4: True, 6: False, 8: True, 10: False, 16: True, 18: False}
        self._blacklist_messages = {3: 'Command has been blacklisted for you',
                                    6: 'Command has been blacklisted for a role you have',
                                    10: None, 18: None}

        if perms:
            perms.bot = self

        self.hi_new = {ord(c): '' for c in ", '"}
        self._setup()

    def _setup(self):
        db = 'test'
        engine = create_engine('mysql+pymysql://{0.db_user}:{0.db_password}@{0.db_host}:{0.db_port}/{1}?charset=utf8mb4'.format(self.config, db),
                               encoding='utf8')
        session_factory = sessionmaker(bind=engine)
        Session = scoped_session(session_factory)
        self._Session = Session
        self.mysql = Object()
        self.mysql.session = self.get_session
        self.mysql.engine = engine

    def load_polls(self):
        session = self.get_session
        sql = 'SELECT polls.title, polls.message, polls.channel, polls.expires_in, polls.ignore_on_dupe, polls.multiple_votes, polls.strict, emotes.emote FROM polls LEFT OUTER JOIN pollEmotes ON polls.message = pollEmotes.poll_id LEFT OUTER JOIN emotes ON emotes.emote = pollEmotes.emote_id'
        poll_rows = session.execute(sql)
        polls = {}
        for row in poll_rows:
            poll = polls.get(row['message'], Poll(self, row['message'], row['channel'], row['title'],
                                                  expires_at=row['expires_in'],
                                                  strict=row['strict'],
                                                  no_duplicate_votes=row['ignore_on_dupe'],
                                                  multiple_votes=row['multiple_votes']))

            if poll.message not in polls:
                polls[poll.message] = poll

            poll.add_emote(row['emote'])

        for poll in polls.values():
            poll.start()

    def cache_servers(self):
        servers = self.servers
        sql = 'SELECT * FROM `servers`'
        session = self.get_session
        ids = set()
        for row in session.execute(sql).fetchall():
            d = {**row}
            d.pop('server', None)
            print(d)
            self.server_cache.update_cached_server(str(row['server']), **d)
            ids.add(str(row['server']))

        new_servers = []
        for server in servers:
            if server.id in ids:
                continue

            new_servers.append('(%s)' % server.id)

        if new_servers:
            sql = 'INSERT INTO `servers` (`server`) VALUES ' + ', '.join(new_servers)
            print(sql)
            session.execute(sql)
            session.commit()

    @property
    def get_session(self):
        return self._Session()

    @property
    def server_cache(self):
        return self._server_cache

    async def on_ready(self):
        print('[INFO] Logged in as {0.user.name}'.format(self))
        await self.change_presence(game=discord.Game(name=self.config.game))

        for cog in initial_cogs:
            try:
                self.load_extension(cog)
            except Exception as e:
                print('Failed to load extension {}\n{}: {}'.format(cog, type(e).__name__, e))

        self.load_polls()
        self.cache_servers()

    async def on_message(self, message):
        await self.wait_until_ready()
        if message.author.bot or message.author == self.user:
            return

        management = getattr(self, 'management', None)

        if message.server and message.server.id == '217677285442977792' and management:
            if len(message.mentions) + len(message.role_mentions) > 10:
                whitelist = self.management.get_mute_whitelist(message.server.id)
                invulnerable = discord.utils.find(lambda r: r.id in whitelist,
                                                  message.server.roles)
                if invulnerable is None or invulnerable not in message.author.roles:
                    role = discord.utils.find(lambda r: r.id == '322837972317896704',
                                              message.server.roles)
                    if role is not None:
                        user = message.author
                        await self.add_roles(message.author, role)
                        d = 'Automuted user {0} `{0.id}`'.format(message.author)
                        embed = discord.Embed(title='Moderation action [AUTOMUTE]', description=d, timestamp=datetime.utcnow())
                        embed.add_field(name='Reason', value='Too many mentions in a message')
                        embed.set_thumbnail(url=user.avatar_url or user.default_avatar_url)
                        embed.set_footer(text=str(self.user), icon_url=self.user.avatar_url or self.user.default_avatar_url)
                        chn = message.server.get_channel(self.server_cache.get_modlog(message.server.id)) or message.channel
                        await self.send_message(chn, embed=embed)
                        return

        if message.server and message.server.id == '217677285442977792' and message.author.id != '123050803752730624':
            if discord.utils.find(lambda r: r.id == '323098643030736919', message.role_mentions):
                await self.replace_role(message.author, message.author.roles, (*message.author.roles, '323098643030736919'))

        # If the message is a command do that instead
        if message.content.startswith(self.command_prefix):
            await self.process_commands(message)
            return

        oshit = self.cdm.get_cooldown('oshit')
        if oshit and oshit.trigger(False) and message.content.lower().strip() == 'o shit':
            msg = 'waddup'
            await self.send_message(message.channel, msg)

            herecome = await self.wait_for_message(timeout=12, author=message.author, content='here come')
            if herecome is None:
                await self.send_message(message.channel, ':(')
            else:
                await self.send_message(message.channel, 'dat boi')
            return

    async def on_member_update(self, before, after):
        server = after.server
        if server.id == '217677285442977792':
            name = before.name if not before.nick else before.nick
            name2 = after.name if not after.nick else after.nick
            if name == name2:
                return

            await self._wants_to_be_noticed(after, server)

    async def on_server_join(self, server):
        session = self.get_session
        sql = 'INSERT INTO `servers` (`server`) ' \
              'VALUES (%s) ON DUPLICATE KEY IGNORE' % server.id
        session.execute(sql)
        session.commit()

        sql = 'SELECT * FROM `servers` WHERE server=%s' % server.id
        row = session.execute(sql).first()
        if not row:
            return

        self.server_cache.update_cached_server(server.id, **row)

    async def _wants_to_be_noticed(self, member, server, remove=True):
        role = list(filter(lambda r: r.id == '318762162552045568', server.roles))
        if not role:
            return

        role = role[0]

        name = member.name if not member.nick else member.nick
        if ord(name[0]) <= 46:
            for i in range(0, 2):
                try:
                    await self.add_roles(member, role)
                except:
                    pass
                else:
                    break

        elif remove and role in member.roles:
                await retry(self.remove_roles, member, role)

    @staticmethod
    def _parse_on_delete(msg, conf):
        content = msg.content
        user = msg.author

        message = conf['message']
        d = slots2dict(msg)
        d = slots2dict(user, d)
        for e in ['name', 'message']:
            d.pop(e, None)

        d['channel'] = msg.channel.mention
        message = message.format(name=str(user), message=content, **d)
        return split_string(message)

    async def raw_message_delete(self, data):
        id = data.get('id')
        if not id:
            return

        session = self.get_session
        result = session.execute('SELECT `message` `user_id` `server` FROM `messages` WHERE `message_id` = %s' % id)
        msg = result.first()
        if not msg:
            return

        message, user_id, server_id = msg['message'], msg['user_id'], msg['server']
        server = self.get_server(server_id)
        if not server:
            return

        user = server.get_member(user_id)
        if not user:
            return

        channel_id = session.execute('SELECT `on_delete_channel` FROM `servers` WHERE `server` = %s' % server_id).first()
        if not channel_id:
            return

        channel = server.get_channel(channel_id['channel_id'])

    def check_blacklist(self, command, user, ctx):
        session = self.get_session
        sql = 'SELECT * FROM `command_blacklist` WHERE type=%s AND %s ' \
              'AND (user=%s OR user IS NULL) LIMIT 1' % (BlacklistTypes.GLOBAL, command, user.id)
        rows = session.execute(sql).fetchall()

        if rows:
            return False

        if ctx.message.server is None:
            return True

        channel = ctx.message.channel.id
        if user.roles:
            roles = '(role IS NULL OR role IN ({}))'.format(', '.join(map(lambda r: r.id, user.roles)))
        else:
            roles = 'role IS NULL'

        sql = 'SELECT `type`, `role`, `user`, `channel`  FROM `command_blacklist` WHERE server=%s AND %s ' \
              'AND (user IS NULL OR user=%s) AND %s AND (channel IS NULL OR channel=%s)' % (user.server.id, command, user.id, roles, channel)
        rows = session.execute(sql).fetchall()
        if not rows:
            return None

        smallest = 18
        """
        Here are the returns
            1 user AND whitelist
            3 user AND blacklist
            4 whitelist AND role
            6 blacklist AND role
            8 channel AND whitelist
            10 channel AND blacklist
            16 whitelist AND server
            18 blacklist AND server
        """

        for row in rows:
            if row['type'] == BlacklistTypes.WHITELIST:
                v1 = self._perm_values['whitelist']
            else:
                v1 = self._perm_values['blacklist']

            if row['user'] is not None:
                v2 = self._perm_values['user']
            elif row['role'] is not None:
                v2 = self._perm_values['role']
            elif row['channel'] is not None:
                v2 = self._perm_values['channel']
            else:
                v2 = self._perm_values['server']

            v = v1 | v2
            if v < smallest:
                smallest = v

        return smallest

    def _check_auth(self, user_id, auth_level):
        session = self.get_session
        sql = 'SELECT `auth_level` FROM `bot_staff` WHERE user=%s' % user_id
        rows = session.execute(sql).fetchall()
        if not rows:
            return False

        if rows[0]['auth_level'] >= auth_level:
            return True
        else:
            return False


    # ----------------------------
    # - Overridden methods below -
    # ----------------------------

    async def process_commands(self, message):
        _internal_channel = message.channel
        _internal_author = message.author

        view = StringView(message.content)
        if self._skip_check(message.author, self.user):
            return

        prefix = await self._get_prefix(message)
        invoked_prefix = prefix

        if not isinstance(prefix, (tuple, list)):
            if not view.skip_string(prefix):
                return
        else:
            invoked_prefix = discord.utils.find(view.skip_string, prefix)
            if invoked_prefix is None:
                return

        invoker = view.get_word()
        tmp = {
            'bot': self,
            'invoked_with': invoker,
            'message': message,
            'view': view,
            'prefix': invoked_prefix,
            'user_permissions': None
        }
        if self.permissions:
            tmp['user_permissions'] = self.permissions.get_permissions(id=message.author.id)
        ctx = Context(**tmp)
        del tmp

        if invoker in self.commands:
            command = self.commands[invoker]
            if command.owner_only and self.owner != message.author.id:
                command.dispatch_error(exceptions.PermissionError('Only the owner can use this command'), ctx)
                return

            try:
                if command.auth > 0:
                    if not self._check_auth(message.author.id, command.auth):
                        await self.send_message(message.channel, "You aren't authorized to use this command")
                        return

                else:
                    overwrite_perms = self.check_blacklist('(command="%s" OR command IS NULL)' % command, message.author, ctx)
                    msg = self._blacklist_messages.get(overwrite_perms, None)
                    if isinstance(overwrite_perms, int):
                        if message.server.owner.id == message.author.id:
                            overwrite_perms = True
                        else:
                            overwrite_perms = self._perm_returns.get(overwrite_perms, False)

                    if overwrite_perms is False:
                        if msg is not None:
                            await self.send_message(message.channel, msg)
                        return
                    elif overwrite_perms is None and command.required_perms is not None:
                        perms = message.channel.permissions_for(message.author)

                        if not perms.is_superset(command.required_perms):
                            req = [r[0] for r in command.required_perms if r[1]]
                            await self.send_message(message.channel,
                                                    'Invalid permissions. Required perms are %s' % ', '.join(req),
                                                    delete_after=15)
                            return

                    ctx.override_perms = overwrite_perms
            except Exception as e:
                await self.on_command_error(e, ctx)
                return

            self.dispatch('command', command, ctx)
            try:
                await command.invoke(ctx)
            except discord.ext.commands.errors.MissingRequiredArgument as e:
                command.dispatch_error(exceptions.MissingRequiredArgument(e), ctx)
            except CommandError as e:
                ctx.command.dispatch_error(e, ctx)
            else:
                self.dispatch('command_completion', command, ctx)
        elif invoker:
            exc = CommandNotFound('Command "{}" is not found'.format(invoker))
            self.dispatch('command_error', exc, ctx)
