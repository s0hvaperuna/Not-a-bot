import os
from datetime import datetime, timedelta
from random import Random, choice

import discord
from discord.ext.commands import BucketType

from bot.bot import command, cooldown, group, has_permissions
from bot.globals import PLAYLISTS
from cogs.cog import Cog
from utils.utilities import call_later
from utils.utilities import read_lines


class WrestlingGif:
    def __init__(self, url, text):
        self.url = url
        self.text = text

    def build_embed(self, author, recipient):
        description = self.text.format(author=author, recipient=recipient)
        embed = discord.Embed(description=description)
        embed.set_image(url=self.url)
        return embed


wrestling_gifs = [
    WrestlingGif('https://i.imgur.com/xUi2Vq1.gif', "**{recipient.name}** tries to grab but it fails. **{author.name}** grabs **{recipient.name}**"),
    WrestlingGif('https://i.imgur.com/osDWTHG.gif', "**{recipient.name}** tries to escape but **{author.name}** pins them down"),
    WrestlingGif('https://i.imgur.com/HS6R463.gif', "**{author.name}** lifts **{recipient.name}** up. **{recipient.name}** is powerless to do anything"),
    WrestlingGif('https://i.imgur.com/jbE2XVt.gif', "**{author.name}** challenges **{recipient.name}** to a friendly wrestling match"),
    WrestlingGif('https://i.imgur.com/XVUjH9x.gif', "**{recipient.name}** tries to attack but **{author.name}** counters"),
    WrestlingGif('https://i.imgur.com/vTeoYAE.gif', "**{author.name}** and **{recipient.name}** engage in a battle of strength"),
    WrestlingGif('https://i.imgur.com/iu2kiVy.gif', "**{author.name}** gets a hold of **{recipient.name}**"),
    WrestlingGif('https://i.imgur.com/BulkVW1.gif', "**{author.name}** gets **{recipient.name}** with a knee strike"),
    WrestlingGif('https://i.imgur.com/zXaIYLp.gif', "**{author.name}** beats **{recipient.name}** down"),
    WrestlingGif('https://i.imgur.com/XNOMUcg.gif', "**{author.name}** delivers a low blow to **{recipient.name}**. Nasty strategy"),
    #WrestlingGif('https://i.imgur.com/oSG0V6a.gif', "to do"),
    WrestlingGif('https://i.imgur.com/u0H0ZSA.gif', "**{author.name}** grabs **{recipient.name}**s fucking pants <:GWjojoGachiGASM:363025405562585088>")
]


class gachiGASM(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.gachilist = self.bot.gachilist
        if not self.gachilist:
            self.reload_gachilist()

        self.reload_call = call_later(self._reload_and_post, self.bot.loop, self.time2tomorrow())

    def __unload(self):
        self.reload_call.cancel()

    async def _reload_and_post(self):
        self.reload_gachilist()

        for guild in self.bot.guilds:
            vid = Random(self.get_day()+guild.id).choice(self.gachilist)
            channel = self.bot.guild_cache.dailygachi(guild.id)
            if not channel:
                continue

            channel = guild.get_channel(channel)
            if not channel:
                continue

            try:
                await channel.send(f'Daily gachi {vid}')
            except:
                pass

        self.reload_call = call_later(self._reload_and_post, self.bot.loop,
                                      self.time2tomorrow())

    def reload_gachilist(self):
        self.bot.gachilist = read_lines(os.path.join(PLAYLISTS, 'gachi.txt'))
        self.gachilist = self.bot.gachilist

    @staticmethod
    def time2tomorrow():
        # Get utcnow, add 1 day to it and check how long it is to the next day
        # by subtracting utcnow from the gained date
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        return (tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
                - now).total_seconds()

    @staticmethod
    def get_day():
        return (datetime.utcnow() - datetime.min).days

    @command()
    @cooldown(1, 2, BucketType.channel)
    async def gachify(self, ctx, *, words):
        """Gachify a string"""
        if ' ' not in words:
            # We need to undo the string view or it will skip the first word
            ctx.view.undo()
            await self.gachify2.invoke(ctx)
        else:
            return await ctx.send(words.replace(' ', ' ♂ ').upper())

    @command()
    @cooldown(1, 2, BucketType.channel)
    async def gachify2(self, ctx, *, words):
        """An alternative way of gachifying"""
        return await ctx.send('♂ ' + words.replace(' ', ' ♂ ').upper() + ' ♂')

    @command(ignore_extra=True, aliases=['rg'])
    @cooldown(1, 5, BucketType.channel)
    async def randomgachi(self, ctx):
        await ctx.send(choice(self.gachilist))

    @group(ignore_extra=True, invoke_without_command=True)
    @cooldown(1, 5, BucketType.channel)
    async def dailygachi(self, ctx):
        await ctx.send(Random(self.get_day()+ctx.guild.id).choice(self.gachilist))

    @dailygachi.command()
    @cooldown(1, 5)
    @has_permissions(manage_guild=True)
    async def subscribe(self, ctx, *, channel: discord.TextChannel=None):
        if channel:
            await self.bot.guild_cache.set_dailygachi(ctx.guild.id, channel.id)
            return await ctx.send(f'New dailygachi channel set to {channel}')

        channel = self.bot.guild_cache.dailygachi(ctx.guild.id)
        channel = ctx.guild.get_channel(channel)

        if channel:
            await ctx.send(f'Current dailygachi channel is {channel}')
        else:
            await ctx.send('No dailygachi channel set')

    @dailygachi.command(ignore_extra=True)
    @cooldown(1, 5)
    @has_permissions(manage_guild=True)
    async def unsubscribe(self, ctx):
        await self.bot.guild_cache.set_dailygachi(ctx.guild.id, None)
        await ctx.send('Dailygachi channel no longer set')

    @command(no_pm=True)
    @cooldown(1, 5, BucketType.member)
    async def wrestle(self, ctx, *, user: discord.User):
        if user == ctx.author:
            await ctx.send('Wrestling against yourself...')
            return

        wrestling_gif = choice(wrestling_gifs)

        await ctx.send(embed=wrestling_gif.build_embed(ctx.author, user))


def setup(bot):
    bot.add_cog(gachiGASM(bot))
