"""
small program to browse most popular twitch streams, omitting the games you
don't care about
"""

import codecs
import collections
import re
import sys
import traceback
import platform
import webbrowser as wb  # make sure firefox is default for this to work

import requests


"""
TODO
how to get disk-backed membership testing for the ignored games?
ops needed:
    add string
    membership test
    remove string (may be offline)
bloom filters?
sqlite? how does its cache work?
LRU cache?
"""

# persistent store for games ignored
FILENAME = 'ignore_games.txt'


class Stream:
    def __init__(self, stream_json):
        self.viewers = stream_json.get('viewers', None)
        channel_json = stream_json['channel']
        self.name = channel_json.get('name', None)
        self.url = channel_json.get('url', None)
        self.status = channel_json.get('status', None)

        self.game = channel_json.get('game', None)
        if self.game is not None:
            self.game = self.game.strip().lower()


def build_retry_url(url, retry_streams):
    if len(retry_streams) == 0:
        return ''

    suffix = retry_streams[0].name
    for stream in retry_streams[1:]:
        suffix += ',' + stream.name
    return url.format(suffix)


def request_json(url, session, timeout_seconds):

    resp = session.get(url, timeout=timeout_seconds)
    streams = resp.json()
    return streams['streams']


class StreamStore:
    """
    pull stream info from twitch api and cache it
    """
    def __init__(self):

        self.streams = []
        self.url = 'https://api.twitch.tv/kraken/streams/?offset={}&limit={}'

        self.retry_streams = []
        # expects comma separated list
        self.retry_url = 'https://api.twitch.tv/kraken/streams/?channel={}'
        self.current_offset = 0  # page number
        self.limit = 100  # num streams to request
        self.ignore_games = set()
        self._load_ignored(FILENAME)
        self.timeout_seconds = 5

        self.session = requests.Session()
        # use ver 3 api
        # https://github.com/justintv/Twitch-API/tree/master/v3_resources
        self.session.headers.update(
            {'Accept': 'application/vnd.twitchtv3+json'})

    def _load_ignored(self, filename):
        self.games = set()
        with codecs.open(filename, 'r', 'utf8') as inp:
            for line in inp:
                self.ignore_game(line)

    def ignore_game(self, game):
        self.ignore_games.add(game.strip().lower())
        self.streams = list(filter(self._interesting, self.streams))

    def _interesting(self, stream):
        """
        yes if stream is not ignored
        """
        if stream.game and stream.game not in self.ignore_games:
            return True
        return False

    def _unknown(self, stream):
        if stream.game is None:
            return True
        return False

    def remove(self, num):
        self.streams = self.streams[num:]

    def request_streams(self):
        url_new = self.url.format(self.current_offset, self.limit)
        urls = [url_new]

        retry_url = build_retry_url(self.retry_url, self.retry_streams)
        num_retry = len(self.retry_streams)

        if num_retry:
            urls.append(retry_url)

        try:
            for url in urls:
                streams = request_json(
                    url, self.session, self.timeout_seconds)
                for stream_json in streams:
                    stream = Stream(stream_json)
                    if self._interesting(stream):
                        self.streams.append(stream)
                    if self._unknown(stream):
                        self.retry_streams.append(stream)

            self.current_offset += len(streams)  # next page

            # get rid of things we just retried
            self.retry_streams = self.retry_streams[num_retry:]
        except Exception:
            traceback.print_exc()

    def ensure(self, num_streams):
        """
        ensure we have cached at least num_streams
        """
        while len(self.streams) < num_streams:
            self.request_streams()


def stream_open(store, inp):
    # ui shows nums +1
    stream = store.streams[inp.stream_num - 1]
    url = stream.url
    name = stream.name
    if url:
        wb.open(url)
    else:
        wb.open('http://twitch.tv/' + name)


def print_streams(store, num):
    print('\n'*30)  # get new screen

    for i in range(num):
        stream = store.streams[i]
        viewers = stream.viewers
        name = stream.name
        url = stream.url
        title = stream.status
        game = stream.game

        if platform.system() == 'Windows':
            if title:
                title = title.encode('utf8').decode('cp866', 'replace')
            if game:
                game = game.encode('utf8').decode('cp866', 'replace')

        print('{}. ({}) {}'.format(i+1, game, title))
        print('{} {} {}'.format(viewers, url, name))
        print()


def print_help():
    print('q quit r restart <num> open i<num> ignore game <enter> continue')


UserInput = collections.namedtuple('Input', ['cmd', 'stream_num'])
RESET = 'reset'
QUIT = 'quit'
OPEN = 'open'
CONTINUE = 'continue'
INVALID_INPUT = 'invalid_input'
IGNORE = 'ignore'


def take_user_input(num_printed):
    inp = input()
    inp = inp.strip()

    number_found = re.match('\d+$', inp)
    ignore_found = re.match('i(\d+)$', inp)
    if inp == '':
        return UserInput(CONTINUE, None)
    elif RESET.startswith(inp):
        return UserInput(RESET, None)
    elif QUIT.startswith(inp):
        return UserInput(QUIT, None)
    elif number_found:
        num = int(inp)
        if 1 <= num and num <= num_printed:
            return UserInput(OPEN, num)
    elif ignore_found:
        num = int(ignore_found.groups()[0])
        if 1 <= num and num <= num_printed:
            return UserInput(IGNORE, num)

    return UserInput(INVALID_INPUT, None)


def take_valid_input(num_printed):
    inp = take_user_input(num_printed)
    while inp.cmd == INVALID_INPUT:
        print('invalid input, try again')
        print_help()
        inp = take_user_input(num_printed)
    return inp


def seq_sz(seq):
    sum = 0
    for el in seq:
        sum += sys.getsizeof(el)
    return sum


def ignore_game(store, inp, filename):
    stream = store.streams[inp.stream_num-1]
    if not stream.game:
        return
    store.ignore_game(stream.game)
    with codecs.open(filename, 'a', 'utf8') as f:
        f.write('\n' + stream.game.strip().lower())


def main():
    num_printed = 5

    store = StreamStore()
    print('store set size', seq_sz(store.ignore_games), 'bytes')
    while True:
        store.ensure(num_printed)
        print_streams(store, num_printed)
        print_help()

        inp = take_valid_input(num_printed)
        print('your input', inp)
        if inp.cmd == RESET:
            store = StreamStore()
        elif inp.cmd == QUIT:
            print('bye')
            sys.exit(0)
        elif inp.cmd == OPEN:
            stream_open(store, inp)
        elif inp.cmd == CONTINUE:
            store.remove(num_printed)
        elif inp.cmd == IGNORE:
            ignore_game(store, inp, FILENAME)


if __name__ == '__main__':
    main()
