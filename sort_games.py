
import codecs
import shutil

FILENAME = 'ignore_games.txt'
BACKUP = FILENAME + '.bak'

shutil.copy2(FILENAME, BACKUP)

with codecs.open(BACKUP, 'r', 'utf8') as inp:
    games = [line.strip().lower() for line in inp if line.strip() != '']

games.sort()


with codecs.open(FILENAME, 'w', 'utf8') as out:
    for game in games:
        out.write(game + '\n')
