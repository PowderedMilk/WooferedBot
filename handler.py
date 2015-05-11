import time
import re
import json
import random
import datetime
import urllib
import sys
import math
from collections import deque
from threading import Semaphore
from twisted.internet import reactor
from settings import config

YOUTUBE_LINK = re.compile(r"""\b(?:https?://)?(?:m\.|www\.)?youtu(?:be\.com|\.be)/(?:v/|watch/|.*?(?:embed|watch).*?v=)?([a-zA-Z0-9\-_]+)""")

class WooferBotCommandHandler():
    def __init__(self):
        self.die = False
        self.semaphore = Semaphore(0)
        self.commandQueue = deque()

    def handleMessage(self, bot, user, channel, message):
        self.updateDogs(bot, channel, message)
        self.handleYoutube(bot, user, channel, message)
        for (prefix, handler, dispatch) in self.commands:
            if message.lower().startswith(prefix):
                if dispatch: # handle in separate thread
                    args = (handler, bot, user, channel, message)
                    self.commandQueue.append(args)
                    self.semaphore.release()
                else:
                    try:
                        getattr(self, handler)(bot, user, channel, message)
                    except Exception as e:
                        print 'Error while handling command: ' + e.message
                        print sys.exc_traceback.tb_lineno 

    def updateDogs(self, bot, channel, message):
        for dog in config['dogs']:
            if dog in message and channel in config['dogchannels']:
                config['dogCount'][channel][dog] += 1
                if config['dogCount'][channel][dog] == 3:
                    # say dog name in channel
                    bot.say(channel, dog)
                    config['dogCount'][channel][dog] = 0

    def handleYoutube(self, bot, user, channel, message):
        if not channel in config['youtubechannels']: return
        match = YOUTUBE_LINK.search(message)
        if not match:
            return

        self.commandQueue.append(('executeYoutube', bot, user, channel, match.group(1)))
        self.semaphore.release()

    def executeJoin(self, bot, user, channel, message):
        parts = message.split(' ')
        # this command can be used in two ways:
        # 1) any user can enter +join in any of the bot admin channels,
        #    causing the bot to join the user's channel
        # 2) admins can request the bot to join anybodies channel
        #    entering +join <user>
        if len(parts) == 1 and channel in config['admin_channels']:
            joinChannel = user
        elif len(parts) == 2 and user in config['admin_channels']:
            joinChannel = parts[1]
        else:
            return # invalid syntax

        if joinChannel in config['channels']:
            bot.say(channel, '{} is already in channel #{}!'.format(config['nickname'], joinChannel))
        else:
            bot.say(channel, '{} will join #{} shortly.'.format(config['nickname'], joinChannel))
            config['dogchannels'].append(joinChannel)
            config.save()
            bot.factory.addChannel(joinChannel)

    def executePart(self, bot, user, channel, message):
        bot.leave(channel, 'requested by {}'.format(user))
        config['channels'].remove(channel)
        config.save()

    def executeAdd(self, bot, user, channel, message):
        if user == channel: # limit to owner of channel
            cmd = message.lower().split(' ')[1]
            lookup = {
                'youtube': 'youtubechannels',
                'kadgar': 'kadgarchannels',
                'speedrun': 'speedrunchannels',
                'dogfacts': 'dogfactschannels',
                'dogs': 'dogchannels'
            }
            if (cmd not in lookup.keys()):
                bot.say(channel, 'I don\'t know \'{}\', choose from {}'.format(cmd, ', '.join(lookup.keys())))
            elif channel not in config[lookup[cmd]]:
                config[lookup[cmd]].append(channel)
                config.save()
                bot.say(channel, 'You can now use functionality of \'{}\' in this channel!'.format(cmd))
            else:
                bot.say(channel, '\'{}\' already works in your channel!'.format(cmd))

    def executeDisable(self, bot, user, channel, message):
        if user == channel: # limit to owner of channel
            cmd = message.lower().split(' ')[1]
            lookup = {
                'youtube': 'youtubechannels',
                'kadgar': 'kadgarchannels',
                'speedrun': 'speedrunchannels',
                'dogfacts': 'dogfactschannels',
                'dogs': 'dogchannels'
            }
            if (cmd not in lookup.keys()):
                bot.say(channel, 'I don\'t know \'{}\', choose from {}'.format(cmd, ', '.join(lookup.keys())))
            elif channel in config[lookup[cmd]]:
                config[lookup[cmd]].remove(channel)
                config.save()
                bot.say(channel, 'This channel can no longer use the functionality of \'{}\'!'.format(cmd))
            else:
                bot.say(channel, '\'{}\' is already off in this channel!'.format(cmd))

    def executePb(self, bot, user, channel, message):
        if not channel in config['speedrunchannels']: return
        try:
            record = message.split(' ',3)
            runner = record[1].lower()
            game = record[2].lower()
            category = record[3].lower()
            url = "http://www.speedrun.com/api_records.php?game=" + game + "&user=" + runner
            response = urllib.urlopen(url);
            data = self.lowerDict(json.load(response))
            pbTime = 0
            x = [0, 0]
            for key,value in data.values()[0][category].iteritems():
                pbTime = value['time'] if 'timeigt' not in value.keys() else value['timeigt']
            if '.' in str(pbTime):
                x = float(pbTime)
                x = math.modf(x)
                pbTime = x[1]
            game = data.keys()[0]
            print pbTime
            if int(pbTime) > 3600:
                timeString = str(datetime.timedelta(seconds=int(pbTime)))
            elif int(pbTime) < 3600:
                timeString = str(int(int(pbTime)/60)).zfill(2)+":"+str(int(pbTime)%60).zfill(2)
            if pbTime == 0:
                bot.say(channel, "The user does not have a time in this category.")
            elif pbTime != 0 and float(x[0]) == 0:
                bot.say(channel, "{}'s personal record in {} {} is {}".format(runner.title(), game.title(), category.title(), timeString))
            elif pbTime != 0 and float(x[0]) != 0:
                pbDec = str(x[0])
                bot.say(channel, "{}'s personal record in {} {} is {}{}".format(runner.title(), game.title(), category.title(), timeString, pbDec[1:]))
        except Exception, e:
            bot.say(channel, "Error handling request")
            print e
            print sys.exc_traceback.tb_lineno 

    def executeWr(self, bot, user, channel, message):
        if not channel in config['speedrunchannels']: return
        try:
            record = message.split(' ', 2)
            game = record[1].lower()
            category = record[2].lower()
            url = "http://www.speedrun.com/api_records.php?game=" + game
            response = urllib.urlopen(url)
            data = self.lowerDict(json.load(response))
            value = data.values()[0][category]
            wrTime = value['time'] if 'timeigt' not in value.keys() else value['timeigt']
            x = [0, 0]
            runner = value['player']
            game = data.keys()[0]
            if '.' in str(wrTime):
                x = float(wrTime)
                x = math.modf(x)
                wrTime = x[1]
            game = data.keys()[0]
            if int(wrTime) > 3600:
                timeString = str(datetime.timedelta(seconds=int(wrTime)))
            elif int(wrTime) < 3600:
                timeString = str(int(int(wrTime)/60)).zfill(2)+":"+str(int(wrTime)%60).zfill(2)
            if wrTime == 0:
                bot.say(channel, "The specified category doesn't exist")
            elif wrTime != 0 and float(x[0]) == 0:
                bot.say(channel, "The world record in {} {} is {} by {}.".format(game.title(), category.title(), timeString, runner.title()))
            elif wrTime != 0 and float(x[0]) != 0:
                wrDec = str(x[0])
                bot.say(channel, "The world record in {} {} is {}{} by {}".format(game.title(), category.title(), timeString, wrDec[1:], runner.title()))
        except Exception, e:
            bot.say(channel, "Error handling request")
            print e
            print sys.exc_traceback.tb_lineno 

    def executeSplits(self, bot, user, channel, message):
        if not channel in config['speedrunchannels']: return
        try:
            record = message.split(' ',3)
            runner = record[1].lower()
            game = record[2].lower()
            category = record[3].lower()
            url = "http://www.speedrun.com/api_records.php?game=" + game + "&amount=1500"
            response = urllib.urlopen(url);
            data = self.lowerDict(json.load(response))
            splitid = 0
            x = [0, 0]
            for key,value in data.values()[0][category].iteritems():
                if 'player' in value.keys() and value['player'].lower() == runner:
                    splitid = value['splitsio']
            game = data.keys()[0]
            if splitid == 0:
                bot.say(channel, "The user does splits for this category on speedrun.com.")
            elif splitid != 0:
                bot.say(channel, "{}'s splits for {} {} is splits.io/{}".format(runner.title(), game.title(), category.title(), splitid))
        except Exception, e:
            bot.say(channel, "Error handling request")
            print e
            print sys.exc_traceback.tb_lineno 

    def lowerDict(self,d):
        e = {}
        for k, v in d.iteritems():
            if isinstance(v, dict):
                e[k.lower()] = self.lowerDict(v)
            elif isinstance(v, str):
                e[k.lower()] = v.lower()
            else:
                e[k.lower()] = v
        return e

    def executeYoutube(self, bot, user, channel, video_id):
        url = "https://www.googleapis.com/youtube/v3/videos?part=snippet%2CcontentDetails%2Cstatistics&id={}&fields=items(id%2Csnippet(title%2CchannelTitle)%2CcontentDetails(duration)%2Cstatistics(viewCount%2ClikeCount%2CdislikeCount))&key={}".format(video_id, config["YTAuthKey"])
        response = urllib.urlopen(url)
        data = json.load(response)
        title = data['items'][0]['snippet']['title']
        videoPoster = data['items'][0]['snippet']['channelTitle']
        bot.say(channel,'{} linked : {} by {}'.format(user, title, videoPoster))

    def executeDogs(self, bot, user, channel, message):
        if channel in config['dogchannels']:
            bot.say(channel, ' '.join(config['dogs']))

    def executeZimbabwe(self, bot, user, channel, message):
        if user == "spookas_":
            bot.say(channel, 'deeFelco')
        else:
            bot.say(channel, 'FrankerZ LilZ RalpherZ ZreknarF ZliL ZrehplaR')

    def executeRwanda(self, bot, user, channel, message):
        if user == "spookas_":
            bot.say(channel,'deeBenis')
        else:
            bot.say(channel,'FrankerZ LilZ RalpherZ ZreknarF ZliL ZrehplaR')

    def executeDjibouti(self, bot, user, channel, message):
        if user=="spookas_":
            bot.say(channel,'deeAyeSir')
        else:
            bot.say(channel,'FrankerZ LilZ RalpherZ ZreknarF ZliL ZrehplaR')

    def executeBotswana(self, bot, user, channel, message):
        if user == "spookas_":
            bot.say(channel,'deeArma')
        else:
            bot.say(channel,'FrankerZ LilZ RalpherZ ZreknarF ZliL ZrehplaR')

    def executeDogFacts(self, bot, user, channel, message):
        if not channel in config['dogfactschannels']: return

        with open('dogFacts.txt') as d:
            dogFacts = d.readlines()
            fact = random.choice(dogFacts).strip()
            dog1 = random.choice(config['dogs'])
            dog2 = random.choice(config['dogs'])
            bot.say(channel, "{}: {} {} {}\r\n".format(user.title(), dog1, fact, dog2))

    def executeKadgar(self, bot, user, channel, message):
        if channel not in config['kadgarchannels']: return
        mchannels = message.split(' ')[1:]
        bot.say(channel, 'http://kadgar.net/live/{}'.format('/'.join(mchannels)))

    def executeAbout(self, bot, user, channel, message):
        bot.say(channel, "I'm a bot made by powderedmilk_ or something")

    def executePing(self, bot, user, channel, message):
        if user == "powderedmilk_":
            bot.say(channel, "PONG")

    def getSpeedruncom(self, game, category, wr):
        if wr:
            url = "http://www.speedrun.com/api_records.php?game=" + game
        else:
            url = "http://www.speedrun.com/api_records.php?game=" + game + "&amount=1500"
        data = json.load(urllib.urlopen(url))
        return data

    def start(self):
        reactor.callInThread(self.loop)

    def stop(self):
        self.die = True
        self.semaphore.release()

    def loop(self):
        while True:
            self.semaphore.acquire()
            if self.die: break
            (handler, bot, user, channel, message) = self.commandQueue.popleft()
            try:
                getattr(self, handler)(bot, user, channel, message)
            except Exception as e:
                print 'Error while handling command: ' + e.message

    ''' (prefix, handler, dispatch)
        prefix: how user calls the command
        handler: function that handles the command
        dispatch: if False, handle this function immediately (from socket thread),
                  if True, dispatch to worker thread - use for slow commands like wr lookup
    '''
    commands = [
        ('+join', 'executeJoin', False),
        ('+part', 'executePart', False),
        ('+add', 'executeAdd', False),
        ('+disable', 'executeDisable', False),
        ('+pb', 'executePb', True),
        ('+wr', 'executeWr', True),
        ('+splits','executeSplits', True),
        ('+dogs', 'executeDogs', False),
        ('+dogfacts', 'executeDogFacts', False),
        ('+kadgar', 'executeKadgar', False),
        ('zimbabwe', 'executeZimbabwe', False),
        ('+about', 'executeAbout', False),
        ('ping', 'executePing', False),
        ('djibouti','executeDjibouti',False),
        ('botswana','executeBotswana',False),
        ('rwanda','executeRwanda',False)
    ]


WooferHandler = WooferBotCommandHandler()
