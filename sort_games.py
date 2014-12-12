
import codecs
import shutil

FILENAME = 'ignore_games.txt'
BACKUP = FILENAME + '.bak'


def main():
    shutil.copy2(FILENAME, BACKUP)

    with codecs.open(BACKUP, 'r', 'utf8') as inp:
        uniq = set()
        for line in inp:
            line = line.strip().lower()
            if line != '':
                uniq.add(line)
        games = sorted(uniq)


    with codecs.open(FILENAME, 'w', 'utf8') as out:
        for game in games:
            out.write(game + '\n')

if __name__ == '__main__':
    main()
