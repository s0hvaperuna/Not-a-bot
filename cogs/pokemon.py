import re
import math
import csv
import json
from bot.globals import POKESTATS
import os
from cogs.cog import Cog
from bot.bot import command
from discord.ext.commands import cooldown
from bot.exceptions import BotException
from discord.ext.commands.errors import BadArgument


pokestats = re.compile(r'Level (?P<level>\d+) (?P<name>.+?)\n.+?\nNature: (?P<nature>\w+)\nHP: (?P<hp>\d+)\nAttack: (?P<attack>\d+)\nDefense: (?P<defense>\d+)\nSp. Atk: (?P<spattack>\d+)\nSp. Def: (?P<spdefense>\d+)\nSpeed: (?P<speed>\d+)')
pokemon = {}
stat_names = ('hp', 'attack', 'defense', 'spattack', 'spdefense', 'speed')
MAX_IV = (31, 31, 31, 31, 31, 31)
MIN_IV = (0, 0, 0, 0, 0, 0)

# Stats taken from https://www.kaggle.com/mylesoneill/pokemon-sun-and-moon-gen-7-stats
with open(os.path.join(POKESTATS, 'pokemon.csv'), 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    keys = ('ndex', 'hp', 'attack', 'defense', 'spattack', 'spdefense', 'speed')
    for row in reader:
        pokemon[row['species'].lower()] = {k: int(row[k]) for k in keys}

with open(os.path.join(POKESTATS, 'natures.json'), 'r') as f:
    natures = json.load(f)


# Below functions ported from https://github.com/dalphyx/pokemon-stat-calculator
def calc_stat(iv, base_stat, ev=0, level=1, nature=1):
    base_result = math.floor(((iv + base_stat * 2 + ev / 4) * level / 100 + 5))
    result = math.floor(base_result * nature)
    return result


def calc_hp_stats(iv, base_stat, ev, level):
    # No.292 Shedinja's HP always be 1.
    if base_stat == 1:
        return 1

    result = math.floor((iv + base_stat * 2 + ev / 4) * level / 100 + 10 + level)
    return result


def get_base_stats(name: str):
    poke = pokemon.get(name.lower())
    if not poke:
        raise BotException(f"Could not find pokemon `{name}`"
                           "Make sure you replace the nickname to the pokemons real name or this won't work")

    return tuple(poke[stat] for stat in stat_names)


def calc_all_stats(name, level, nature, evs=(100, 100, 100, 100, 100, 100), ivs=MAX_IV):
    stats = []

    base_stats = get_base_stats(name)
    stats.append(calc_hp_stats(ivs[0], base_stats[0], evs[0], level))

    if isinstance(nature, str):
        nature_ = natures.get(nature.lower())
        if not nature_:
            raise BotException(f'Could not find nature `{nature}`')

        nature = nature_

    for i in range(1, 6):
        stats.append(calc_stat(ivs[i], base_stats[i], evs[i], level, nature[i - 1]))

    return stats


def from_max_stat(min: int, max: int, value: int) -> tuple:
    """
    Gets where the stats stands between the max and min
    Args:
        min: min value
        max: max value
        value: the current value of the stat

    Returns: tuple
        Percentage on how close the value is to the max and the actual diff to max
    """
    d = value - min
    from_max = max - value
    return d/(max-min), from_max


class Pokemon(Cog):
    def __init__(self, bot):
        super().__init__(bot)

    @command(aliases=['pstats'])
    @cooldown(1, 3)
    async def poke_stats(self, ctx, *, stats):
        match = pokestats.match(stats)
        if not match:
            await ctx.send("Failed to parse stats. Make sure it's the correct format")
            return

        stats = match.groupdict()
        try:
            level = int(stats['level'])
        except ValueError:
            raise BadArgument('Could not convert level to integer')

        try:
            for name in stat_names:
                stats[name] = int(stats[name])
        except ValueError:
            raise BadArgument(f'Failed to convert {name} to integer')

        try:
            max_stats = calc_all_stats(stats['name'], level, stats['nature'])
            min_stats = calc_all_stats(stats['name'], level, stats['nature'], ivs=MIN_IV, evs=MIN_IV)
        except KeyError as e:
            return await ctx.send(f"{e}\nMake sure you replace the nickname to the pokemons real name or this won't work")

        s = f'```py\nLevel {stats["level"]} {stats["name"]}\nStat: max value | delta | percentage\n'
        for min, max, name in zip(min_stats, max_stats, stat_names):
            diff, from_max = from_max_stat(min, max, stats[name])
            fill = ' ' * (11 - len(name))
            fill2 = ' ' * (4 - len(str(max)))
            fill3 = ' ' * (6 - len(str(from_max)))

            s += f'{name}:{fill}{max}{fill2}| {from_max}{fill3}| {diff*100:.0f}%\n'
        s += '```'
        await ctx.send(s)


def setup(bot):
    bot.add_cog(Pokemon(bot))
