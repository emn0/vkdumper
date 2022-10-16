# -*- coding: utf-8 -*-

import json
import os
import time
from colorama import init
from shutil import copy
from vk_api import VkApi
from vk_api.exceptions import AuthError, VkApiError

TZ = 3600 * 3
USER_AGENT = 'KateMobileAndroid/52.4 (Android 8.1; SDK 27; armeabi-v7a; Xiaomi Redmi 5A; ru)'

config = {}


class Colors:
    INFO = '\033[34;1m'
    OK = '\033[32;1m'
    WARNING = '\033[33;1m'
    ERROR = '\033[31;1m'
    RESET = '\033[0m'


def con(text):
    print(text + Colors.RESET)


def captcha_handler(captcha):
    r = input('Введите капчу ' + captcha.get_url() + ': ').strip()
    return captcha.try_again(r)


def main():
    init()

    global config
    try:
        with open('config.json') as f:
            config = json.load(f)

    except FileNotFoundError:
        config = {'limit': 1000, 'types': {'chats': True, 'groups': True, 'users': True}}

        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)

    if config['limit'] <= 0:
        config['limit'] = 1e10

    s = input('Введите "логин:пароль" или токен: ')

    if len(s) >= 85:
        vk = VkApi(token=s, captcha_handler=captcha_handler)

        vk.http.headers.update({
            'User-agent': USER_AGENT
        })

    elif ':' in s:
        sp = s.split(':')
        vk = VkApi(sp[0], sp[1], app_id=2685278, captcha_handler=captcha_handler)

        vk.http.headers.update({
            'User-agent': USER_AGENT
        })

        try:
            vk.auth(token_only=True)
        except AuthError:
            con(Colors.ERROR + 'Неверный логин или пароль')
            return
    else:
        con(Colors.WARNING + 'Введите данные для входа в виде "логин:пароль" или "токен"')
        return

    try:
        user = vk.method('users.get')[0]
    except VkApiError as ex:
        if ex.__dict__['error']['error_code'] == 5:
            error_text = 'неверный токен'
        else:
            error_text = str(ex)

        con(Colors.ERROR + 'Ошибка входа: ' + error_text)
        return

    con(Colors.OK + 'Вход выполнен')

    infos = []

    count = vk.method('messages.getConversations', {'count': 0})['count']

    for offset in range((count - 1) // 200 + 1):
        peers = vk.method('messages.getConversations', {'count': 200, 'extended': 1, 'offset': offset * 200})

        for peer in peers['items']:
            peer_id = peer['conversation']['peer']['id']
            peer_type = peer['conversation']['peer']['type']

            if peer_type == 'group' and config['types']['groups']:
                info = [i for i in peers['groups'] if i['id'] == -peer_id][0]
                name = info['screen_name'] if 'screen_name' in info else 'club' + str(info['id'])
                infos.append((peer_id, name, info['name']))

            elif peer_type == 'user' and config['types']['users']:
                info = [i for i in peers['profiles'] if i['id'] == peer_id][0]
                name = info['screen_name'] if 'screen_name' in info else 'id' + str(info['id'])
                infos.append((peer_id, name, info['first_name'] + ' ' + info['last_name']))

            elif peer_type == 'chat' and config['types']['chats']:
                infos.append((peer_id, '', peer['conversation']['chat_settings']['title']))

    base_dir = 'messages_' + str(user['id']) + '/'
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)

    copy('files/favicon.ico', base_dir)
    copy('files/style.css', base_dir)

    name = user['first_name'] + ' ' + user['last_name']

    with open('files/index_pre.html', encoding='utf-8') as f:
        index_file = f.read().replace('\n', '').format(user['id'], name)

    for i in infos:
        if i[1]:
            index_file += '<div class="item"><div class="item__main"><a href="messages/{0}.html">{1}</a></div><div class="item__tertiary">@{2}</div></div>'.format(i[0], i[2], i[1])
        else:
            index_file += '<div class="item"><a href="messages/{0}.html">{1}</a></div>'.format(i[0], i[2])

    with open('files/index_post.html', encoding='utf-8') as f:
        index_file += f.read().replace('\n', '')

    with open(base_dir + 'index.html', 'w', encoding='utf-8') as f:
        f.write(index_file)

    messages_dir = base_dir + 'messages/'
    if not os.path.exists(messages_dir):
        os.makedirs(messages_dir)

    total = ' \\ ' + str(len(infos))

    for num in range(len(infos)):
        info = infos[num]
        msgs = []
        msg_count = vk.method('messages.getHistory', {'peer_id': info[0], 'count': 0})['count']

        con(Colors.INFO + 'Сохранение диалога ' + str(num + 1) + total)

        for offset in range(min(((msg_count - 1) // 200 + 1), config['limit'] // 200)):
            try:
                chunk = vk.method('messages.getHistory', {'peer_id': info[0], 'count': 200, 'extended': 1, 'offset': offset * 200})

                for msg in chunk['items']:
                    if msg['from_id'] < 0:
                        item = [i for i in chunk['groups'] if i['id'] == -msg['from_id']][0]
                        sender = 'club' + str(-msg['from_id'])
                        sender_name = item['name']

                    else:
                        item = [i for i in chunk['profiles'] if i['id'] == msg['from_id']][0]
                        sender = 'id' + str(msg['from_id'])
                        sender_name = item['first_name'] + ' ' + item['last_name']

                    text = 'Служебное сообщение ' + msg['action']['type'] if 'action' in msg else msg['text']

                    a = []
                    for i in msg['attachments']:
                        link = ''

                        if i['type'] == 'photo':
                            photo = ''
                            current = 0
                            sizes = i['photo']['sizes']
                            for size in sizes:
                                if size['type'] == 'w':
                                    photo = size['url']
                                    break
                                elif size['type'] == 's' and current < 1:
                                    current = 1
                                    photo = size['url']
                                elif size['type'] == 'm' and current < 2:
                                    current = 2
                                    photo = size['url']
                                elif size['type'] == 'x' and current < 3:
                                    current = 3
                                    photo = size['url']
                                elif size['type'] == 'y' and current < 4:
                                    current = 4
                                    photo = size['url']
                                elif size['type'] == 'z' and current < 5:
                                    current = 5
                                    photo = size['url']

                            desc = 'Фотография'
                            link = photo

                        elif i['type'] == 'video':
                            desc = 'Видеозапись'
                            link = 'https://vk.com/video' + str(i['video']['owner_id']) + '_' + str(i['video']['id'])

                        elif i['type'] == 'audio':
                            desc = 'Аудиозапись ' + i['audio']['title']

                        elif i['type'] == 'doc':
                            desc = 'Документ'
                            link = i['doc']['url']

                        elif i['type'] == 'link':
                            desc = 'Ссылка'
                            link = i['link']['url']

                        elif i['type'] == 'market':
                            desc = 'Товар'
                            link = 'https://vk.com/market' + str(i['market']['owner_id']) + '_' + str(i['market']['id'])

                        elif i['type'] == 'wall':
                            desc = 'Запись на стене'
                            link = 'https://vk.com/wall' + str(i['wall']['to_id']) + '_' + str(i['wall']['id'])

                        elif i['type'] == 'wall_reply':
                            if 'deleted' in i['wall_reply']:
                                desc = 'Комментарий на стене (удалён)'
                            else:
                                desc = 'Комментарий на стене'
                                link = 'https://vk.com/wall' + str(i['wall_reply']['owner_id']) + '_' + str(i['wall_reply']['post_id']) + '?reply=' + str(i['wall_reply']['id'])

                        elif i['type'] == 'sticker':
                            desc = 'Стикер ID ' + str(i['sticker']['sticker_id'])

                        elif i['type'] == 'gift':
                            desc = 'Подарок ID ' + str(i['gift']['id'])

                        elif i['type'] == 'audio_message':
                            desc = 'Аудиосообщение'
                            link = i['audio_message']['link_mp3']

                        elif i['type'] == 'poll':
                            desc = 'Опрос'
                            link = 'https://vk.com/poll' + str(i['poll']['owner_id']) + '_' + str(i['poll']['id'])

                        else:
                            desc = ''

                        attach = '<div class="attachment__description">' + desc + '</div>'
                        if link:
                            attach += '<a class="attachment__link" href="' + link + '" target="_blank">' + link + '</a>'

                        a.append(attach)

                    msgs.append((sender, msg['date'], sender_name, text, a))

            except KeyError:
                con(Colors.WARNING + 'Ошибка при сохранении диалога ' + str(info[0]))

        with open('files/messages_pre.html', encoding='utf-8') as f:
            file = f.read().replace('\n', '').format(user['id'], name, info[2])

        for msg in msgs:
            link = '<a href="https://vk.com/' + str(msg[0]) + '" target="_blank">' + msg[2] + '</a>, '
            tm = time.strftime('%d.%m.%Y %H:%M:%S', time.gmtime(msg[1] + TZ))
            attach = '<div class="kludges">' + '\n'.join(msg[4]) + '</div>' if msg[4] else ''

            file += '<div class="item"><div class="item__main"><div class="message"><div class="message__header">{0}{2}</div><div>{1}</div></div></div></div>'.format(link + tm, msg[3], attach)

        with open('files/index_post.html', encoding='utf-8') as f:
            file += f.read().replace('\n', '')

        with open(messages_dir + str(info[0]) + '.html', 'w', encoding='utf-8') as f:
            f.write(file)

    con(Colors.OK + 'Готово!')


if __name__ == "__main__":
    main()
