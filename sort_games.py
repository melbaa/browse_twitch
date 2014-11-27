
import codecs

with codecs.open('ignore_games.txt', 'r', 'utf8') as inp:
    games = [line.strip().lower() for line in inp if line.strip() != '']

games.sort()


with codecs.open('ignore_games.txt', 'w', 'utf8') as out:
    for game in games:
        out.write(game + '\n')
