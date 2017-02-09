#!/usr/bin/env python
# -*-coding=utf-8 -*-

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

import json
from datetime import datetime

import discord
from aiohttp import ClientSession
from validators import url as test_url

from bot import audio
from bot.bot import Bot
from bot.globals import *
from bot.permissions import owner_only
from utils import gachiGASM, wolfram, memes
from utils.search import Search
from utils.utilities import write_playlist, read_playlist, empty_file


def start(config, permissions):
    client = ClientSession()
    bot = Bot(command_prefix='!', config=config, aiohttp_client=client, pm_help=True, permissions=permissions)

    sound = audio.Audio(bot, client)
    search = Search(bot, client)

    @bot.event
    async def on_ready():
        print('[INFO] Logged in as {0.user.name}'.format(bot))
        await bot.change_presence(game=discord.Game(name=config.game))

    async def get_ow(bt):
        async with client.get('https://api.lootbox.eu/pc/eu/%s/profile' % bt) as r:
            if r.status == 200:
                js = await r.json()
                js = js['data']
                print(js)
                quick = js['games']['quick']
                cmp = js['games']['competitive']
                winrate_qp = round(int(quick['wins']) / int(quick['played']) * 100, 2)
                winrate_cmp = round(int(cmp['wins']) / int(cmp['played']) * 100, 2)

                return 'Winrate for {0} is {1}% in quick play and {2}% in ' \
                       'competitive.'.format(bt.replace('-', '#'), winrate_qp,
                                             winrate_cmp)

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return

        # If the message is a command do that instead
        if message.content.startswith('!'):
            await bot.process_commands(message)
            return

        if message.content.lower() == 'o shit':
            msg = 'waddup'
            await bot.send_message(message.channel, msg)

            herecome = await bot.wait_for_message(timeout=6.0, author=message.author, content='here come')
            if herecome is None:
                await bot.send_message(message.channel, ':(')
            else:
                await bot.send_message(message.channel, 'dat boi')
            return

    @bot.command(pass_context=True)
    async def set_battletag(ctx, battletag):
        """
        Set a battletag that matches your discord account
        so you don't have to specify it all the time.
        """
        msg = ctx.message
        with open('battletags.json', 'r+') as f:
            data = json.load(f)
            battletag = battletag.replace('#', '-')
            data['users'][msg.author.id] = battletag
            f.seek(0)
            json.dump(data, f, indent=4)
        await bot.send_message(msg.channel, "Battle.net account for %s was set." % msg.author.name)

    @bot.command(pass_context=True)
    async def ow_stats(ctx, battletag=None):
        """Gets your winrate in competitive and quick play"""
        msg = ctx.message

        with open('battletags.json', 'r+') as f:
            data = json.load(f)

        if battletag is None:
            try:
                battletag = data['users'][msg.author.id]
            except KeyError:
                await bot.send_message(msg.channel, "No battle.net account associated with this discord user.")
                return

        await bot.send_message(msg.channel, await get_ow(battletag))

    @bot.command(pass_context=True)
    async def math(ctx, *args):
        """Queries a math problem to be solved by wolfram alpha"""
        calc = ' '.join([*args])
        await bot.send_message(ctx.message.channel, await wolfram.math(calc, client, config.wolfram_key))

    @bot.command(pass_context=True, no_pm=True, aliases=['gachiGASM'], ignore_extra=True)
    async def gachi(ctx, amount=1):
        """gachiGASM Now this is what I call music gachiGASM"""
        if amount <= 0:
            amount = 1

        resp = await gachiGASM.random_gachi(sound, ctx, amount)
        if not resp:
            await bot.say_timeout('Could not get a suitable video', ctx.message.channel, 60)

    @bot.command(pass_context=True, ignore_extra=True)
    @owner_only
    async def update_gachi(ctx):
        """Update the gachi list. This can be done once per day"""

        path = os.path.join(os.getcwd(), 'utils', 'gachi.txt')
        today = datetime.now().strftime('%Y %m %d')
        try:
            modified = os.path.getmtime(path)
        except OSError:
            modified = 0
        last_update = datetime.fromtimestamp(modified).strftime('%Y %m %d')

        if last_update == today:
            return await bot.say_timeout('You can only update the list once per day',
                                         ctx.message.channel, 60)

        with open(path, 'w') as f:

            data = await gachiGASM.update_gachi()

            json.dump(data, f, indent=4)

    @bot.command(pass_context=True, ignore_extra=True)
    async def spam(ctx):
        """Random twitch quote from twitchquotes.com"""
        await bot.send_message(ctx.message.channel, await memes.twitch_poems(client))

    @bot.command(name='say', pass_context=True)
    async def say_command(ctx, *, words):
        """Says the text that was put as a parameter"""
        await bot.send_message(ctx.message.channel, '{0} {1}'.format(ctx.message.author.mention, words))

    @bot.command(pass_context=True, ignore_extra=True)
    @owner_only
    async def add_all(ctx):
        songs = set(read_playlist(ADD_AUTOPLAYLIST))

        invalid = []
        for song in list(songs):
            if not test_url(song):
                songs.remove(song)
                invalid.append(song)

        if invalid:
            await bot.say_timeout('Invalid url(s):\n%s' % ', '.join(invalid), ctx.message.channel, 40)

        write_playlist(AUTOPLAYLIST, songs, 'a')
        empty_file(ADD_AUTOPLAYLIST)

        amount = len(songs)
        await bot.say_timeout('Added %s song(s) to autoplaylist' % amount, ctx.message.channel, 60)

    @bot.command(pass_context=True, ignore_extra=True)
    @owner_only
    async def delete_all(ctx):
        delete_songs = set(read_playlist(DELETE_AUTOPLAYLIST))

        songs = set(read_playlist(AUTOPLAYLIST))

        failed = 0
        succeeded = 0
        for song in delete_songs:
            try:
                songs.remove(song)
                succeeded += 1
            except KeyError as e:
                failed += 1
                print('[EXCEPTION] KeyError: %s' % e)

        write_playlist(AUTOPLAYLIST, songs)

        empty_file(DELETE_AUTOPLAYLIST)

        await bot.say_timeout('Successfully deleted {0} songs and failed {1}'.format(succeeded, failed),
                              ctx.message.channel, 60)

    @bot.command(pass_context=True, ignore_extra=True)
    async def playlists(ctx):
        p = os.path.join(os.getcwd(), 'data', 'playlists')
        files = os.listdir(p)
        sort = filter(lambda f: os.path.isfile(os.path.join(p, f)), files)
        await bot.say_timeout('Playlists: {}'.format(', '.join(sort)), ctx.message.channel)

    @bot.command(pass_context=True)
    @owner_only
    async def shutdown(ctx):
        try:
            await bot.change_presence()
            await sound.shutdown()
            for message in bot.timeout_messages:
                await message.delete_now()
                message.cancel_tasks()

            bot.aiohttp_client.close()

        except Exception as e:
            print('[ERROR] Error while shutting down %s' % e)
        finally:
            await bot.close()

    bot.add_cog(search)
    bot.add_cog(sound)
    bot.run(config.token)
