A small command line application that helps browsing the currently live
twitch.tv streams.

![screenshot](https://github.com/melbaa/browse_twitch/blob/master/ss.png)

# Why
The program can be used to quickly find new games or old games you missed that
people still enjoy. It's also useful to confirm that there are close to 0
games that you still enjoy and it's time to move to a new hobby.

# Install
* get python 3
* pip install requests
* (optional) install VLC and pip install livestreamer

# Usage
run browse_twitch.py

The interface is somewhat self explanatory, you get the games from twitch.tv
with most viewers in descending order. You can ignore them, so you never see
them again.

The tool stores an ignore list in ignore_games.db. It gets created on first
run. It's safe to delete it if you want to start with a fresh ignore list,
just don't forget to close the application first.

You can edit your database with something like SQLiteStudio, but it's usually
not needed.

# Links
There's the somewhat similar, but much fancier
https://github.com/bastimeyer/livestreamer-twitch-gui