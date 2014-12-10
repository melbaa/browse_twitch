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


class Stream:
    def __init__(self, stream_json):
        self.viewers = stream_json.get('viewers', None)
        channel_json = stream_json['channel']
        self.name = channel_json.get('name', None)
        self.url = channel_json.get('url', None)
        self.status = channel_json.get('status', None)
        self.game = channel_json.get('game', None)


class StreamStore:
    """
    pull stream info from twitch api and cache it
    """
    def __init__(self):
        self.streams = []
        self.url = 'https://api.twitch.tv/kraken/streams/?offset={}&limit={}'
        self.current_offset = 0  # page number
        self.limit = 100  # num streams to request
        self.ignore_games = self._load_ignored()
        self.timeout_seconds = 5

        self.session = requests.Session()
        # use ver 3 api
        # https://github.com/justintv/Twitch-API/tree/master/v3_resources
        self.session.headers.update(
            {'Accept': 'application/vnd.twitchtv3+json'})

    def _load_ignored(self):
        games = set()
        with codecs.open('ignore_games.txt', 'r', 'utf8') as inp:
            for line in inp:
                games.add(line.strip().lower())
        return games

    def _interesting(self, stream):
        """
        yes if stream is not ignored
        """
        if stream.game and stream.game.lower() in self.ignore_games:
            return False
        return True

    def remove(self, num):
        self.streams = self.streams[num:]

    def request_streams(self):
        url = self.url.format(self.current_offset, self.limit)
        try:
            resp = self.session.get(url, timeout=self.timeout_seconds)
            streams = resp.json()
            for stream_json in streams['streams']:
                stream = Stream(stream_json)
                if self._interesting(stream):
                    self.streams.append(stream)

                self.current_offset += 1  # next page

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
    print('q quit r restart <num> open <enter> continue')


UserInput = collections.namedtuple('Input', ['cmd', 'stream_num'])
RESET = 'reset'
QUIT = 'quit'
OPEN = 'open'
CONTINUE = 'continue'
INVALID_INPUT = 'invalid_input'


def take_user_input(num_printed):
    inp = input()
    inp = inp.strip()

    number_found = re.match('\d+', inp)
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

    return UserInput(INVALID_INPUT, None)


def take_valid_input(num_printed):
    inp = take_user_input(num_printed)
    while inp.cmd == INVALID_INPUT:
        print('invalid input, try again')
        print_help()
        inp = take_user_input(num_printed)
    return inp


def main():
    num_printed = 5

    store = StreamStore()
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


if __name__ == '__main__':
    main()
