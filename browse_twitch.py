"""
small program to browse most popular twitch streams, omitting the games you
don't care about
"""


import argparse
import collections
import os.path
import platform
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback
import json
import webbrowser as wb  # make sure firefox is default for this to work

import requests


# persistent store for games ignored
DBNAME = os.path.dirname(os.path.realpath(__file__)) + '/ignore_games.db'

INIT_DB_QRY = """
create table if not exists games (
    name TEXT NOT NULL DEFAULT('') PRIMARY KEY,
    date_added INT NOT NULL DEFAULT(0)
);

create index if not exists date_added_idx on games (date_added ASC);
"""

MEMBERSHIP_QRY = """
select name from games
where name = ?
"""

INSERT_QRY = """
insert into games(name, date_added)
values (?, ?)
"""


def read_config(filename):
    with open(filename) as f:
        config = json.loads(f.read())
    return config


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

    def __repr__(self):
        return '{} name={}'.format(self.__class__, self.name)


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
    def __init__(self, client_id):

        self.db_conn, self.db_curr = self._init_db()
        self.streams = []
        self.url = 'https://api.twitch.tv/kraken/streams/?offset={}&limit={}'
        self.client_id = client_id

        self.retry_streams = []
        # expects comma separated list
        self.retry_url = 'https://api.twitch.tv/kraken/streams/?channel={}'
        self.current_offset = 0  # page number
        self.limit = 100  # num streams to request
        self.timeout_seconds = 5

        self.session = requests.Session()
        # use ver 3 api
        # https://github.com/justintv/Twitch-API/tree/master/v3_resources
        self.session.headers.update({
            'Accept': 'application/vnd.twitchtv3+json',
            'Client-ID': client_id
        })

    def _init_db(self):
        db = sqlite3.connect(DBNAME)
        curr = db.cursor()
        curr.executescript(INIT_DB_QRY)
        db.commit()

        return db, curr

    def close(self):
        self.db_curr.close()
        self.db_conn.close()

    def ignore_game(self, game):
        game = game.strip().lower()
        self.db_curr.execute(INSERT_QRY, (game, int(time.time())))
        self.db_conn.commit()
        self.streams = list(filter(self._interesting, self.streams))

    def _interesting(self, stream):
        """
        true if stream is not ignored
        """
        if not stream.game:
            return False

        res = self.db_curr.execute(MEMBERSHIP_QRY, (stream.game,)).fetchall()
        self.db_conn.commit()
        return len(res) == 0

    def _unknown(self, stream):
        return stream.game is None

    def remove(self, num):
        self.streams = self.streams[num:]

    def request_streams(self):
        url_new = self.url.format(self.current_offset, self.limit)
        urls = [url_new]

        """
        the url can become too long. batching can help, but it brings its own
        problems eg. have to keep track how many batches succeeded to avoid
        showing dups. currently we show dups but code is simpler
        """
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

                self.current_offset += len(streams)  # move to next page

            # get rid of things we just retried
            self.retry_streams = self.retry_streams[num_retry:]
        except Exception:
            traceback.print_exc()
            import pdb;pdb.set_trace()

    def ensure(self, num_streams):
        """
        ensure we have cached at least num_streams
        """
        while len(self.streams) < num_streams:
            self.request_streams()

def get_streamer():
    streamer = shutil.which('streamlink') or shutil.which('livestreamer')
    return streamer

def stream_open(store, inp):
    # ui shows nums +1
    stream = store.streams[inp.stream_num - 1]
    stream.url
    stream.name
    url = stream.url or ('http://twitch.tv/' + stream.name)
    url = shlex.quote(url)

    streamer = get_streamer()
    if platform.system() == 'Windows' and streamer:
        subprocess.call(['start', streamer, url, 'best'], shell=True)
    else:
        wb.open(url)


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
    print("q quit r restart <num> open i<num> ignore game <enter> continue")


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


def ignore_game(store, inp):
    stream = store.streams[inp.stream_num-1]
    if not stream.game:
        return
    store.ignore_game(stream.game)


def main():
    num_printed = 5

    parser = argparse.ArgumentParser()
    parser.add_argument('CONFIGPATH', type=str, help='path to secrets.json')
    args = parser.parse_args()
    config = read_config(args.CONFIGPATH)
    client_id = config['client_id']

    store = StreamStore(client_id)
    while True:
        store.ensure(num_printed)
        print_streams(store, num_printed)
        print_help()

        inp = take_valid_input(num_printed)
        print('your input', inp)
        if inp.cmd == RESET:
            store.close()
            store = StreamStore(client_id)
        elif inp.cmd == QUIT:
            print('closing db')
            store.close()
            print('bye')
            sys.exit(0)
        elif inp.cmd == OPEN:
            stream_open(store, inp)
        elif inp.cmd == CONTINUE:
            store.remove(num_printed)
        elif inp.cmd == IGNORE:
            ignore_game(store, inp)


if __name__ == '__main__':
    main()
