import os
import json
import string
import discord
import asyncio
import factorio_rcon

from config import *


def load_data(filename):
    resp = ""
    if os.path.exists(filename):
        with open(filename, "r") as ufile:
            data = ufile.read()
            if not data:
                data = "{}"
            resp = json.loads(data)
    return resp


class DClient(discord.Client):
    rcon_client = None
    user_map = {}
    white_list = []
    white_list_enabled = False
    bot_enabled = True
    whitelist_polling_interval = WHITELIST_POLLING_INTERVAL

    async def mass_kick_players(self):
        players_to_kick = await self.get_players_to_kick()
        if len(players_to_kick) == 0:
            return
        str_players_to_kick = ", ".join(players_to_kick)
        await self.execute_rcon(
            f"! Игроки {str_players_to_kick},"
            f" в течении {KICK_WAIT_INTERVAL} секунд зайдите в любой из "
            f"{FACTORIO_VOICE_CHANNELS} в Discord-е, или будете кикнуты с сервера"
        )
        await asyncio.sleep(KICK_WAIT_INTERVAL)
        players_to_kick = await self.get_players_to_kick()
        for user in players_to_kick:
            await self.execute_rcon(f"/kick {user} Не в белом списке")

    async def get_players_to_kick(self):
        await self.update_bot_whitelist()
        result = (await self.execute_rcon(f"/players o")).replace(" (online)", "")
        online_players = [o.strip() for o in result.split("\n")[1:]]
        admins = await self.get_factorio_admins()
        players_to_kick = [ o for o in online_players if o not in self.white_list or o not in admins]
        # players_to_kick = [ o for o in online_players if o not in self.white_list]
        return players_to_kick

    async def add_user_to_whitelist(self, username):
        if username not in self.white_list:
            self.white_list.append(username)
        await self.execute_rcon(f"/whitelist add {username}")

    async def remove_user_from_whitelist(self, username):
        if username in self.white_list:
            self.white_list.remove(username)
        await self.execute_rcon(f"/whitelist remove {username}")

    async def update_server_whitelist(self):
        await self.execute_rcon("/whitelist clear")
        for username in self.white_list:
            await self.execute_rcon(f"/whitelist add {username}")

    async def update_bot_whitelist(self):
        result = await self.execute_rcon("/whitelist get")
        if result == "The whitelist is empty.":
            self.white_list = []
        else:
            whitelist = result.replace("Whitelisted players: ", "")
            if " and " in whitelist:
                parts = whitelist.split(" and ")
                game_whitelisted_players = parts[0].split(", ") + [parts[1]]
            else:
                game_whitelisted_players = [whitelist]
            self.white_list = game_whitelisted_players
        admins = await self.get_factorio_admins()
        for admin in admins:
            if admin not in self.white_list:
                self.white_list.append(admin)

    async def get_factorio_admins(self):
        admins = [u.strip().replace(" (online)", "") for u in (await self.execute_rcon("/admins")).split("\n")]
        return admins

    async def is_factorio_admin(self, member, check_roles=[]):
        is_admin = False
        roles = check_roles or member.roles
        for role in roles:
            if role.name == FACTORIO_ADMIN_ROLE:
                is_admin = True
        return is_admin

    async def set_polling_interval(self, interval):
        self.whitelist_polling_interval = interval

    async def get_whitelist_enabled(self):
        await asyncio.sleep(self.whitelist_polling_interval)
        data = await self.execute_rcon("/wlist-state")
        if bool(int(data)):
            if not self.white_list_enabled:
                self.white_list_enabled = True
                await self.execute_rcon(f"/whitelist enable")
                await self.mass_kick_players()
        else:
            if self.white_list_enabled:
                self.white_list_enabled = False
                await self.execute_rcon(f"/whitelist disable")
        self.loop.create_task(self.get_whitelist_enabled())

    async def execute_rcon(self, command, retry=3):
        try:
            responce = self.rcon_client.send_command(command)
        except Exception as e:
            print(e)
            self.rcon_client = factorio_rcon.RCONClient(RCON_ADDR, int(RCON_PORT), RCON_PASS)
            retry -= 1
            if retry > 0:
                responce = await self.execute_rcon(command, retry)
        return responce

    async def on_ready(self):
        self.rcon_client = factorio_rcon.RCONClient(RCON_ADDR, int(RCON_PORT), RCON_PASS)
        self.user_map = load_data(USER_MAP_FILE)
        self.loop.create_task(self.get_whitelist_enabled())
        print(f'We have logged in as {self.user}')

    # async def on_reaction_add(self, reaction, user):
    #     print(f"reaction: {reaction}, {reaction.emoji}")

    async def on_message(self, message):
        is_admin = await self.is_factorio_admin(message.author)
        author = message.author.name
        # print(message.channel.name, author, message.content)
        if message.channel.name != DISCORD_MAP_CHANNEL:
            return

        if author == DISCORD_BOT_NAME:
            return

        # команды, передаваемые на сервер факторио,
        # работают только для пользователей дискорда с ролью админа сервера факторио
        if message.content.startswith("/c") and is_admin:
            responce = await self.execute_rcon(message.content[3:])
            if responce:
                await message.channel.send(responce)

        # команды бота, часть команд (конфигурационные)
        # работают только у пользователей дискорда с ролью админа сервера факторио
        elif message.content.startswith("."):
            cmd = message.content[1:]
            if cmd.startswith("wl_polling") and is_admin:
                if message.content == "wl_polling":
                    await message.channel.send(f"{self.whitelist_polling_interval}")
                else:
                    try:
                        self.set_polling_interval(int(message.content.split(" ")[-1]))
                        await message.channel.send(
                            f"whitelist_polling_interval setted to {self.whitelist_polling_interval}")
                    except:
                        await message.channel.send(f"Bad value {message.content}")

            if cmd == "whitelist":
                await self.update_bot_whitelist()
                await message.channel.send(self.white_list)

            if cmd == "update_server_whitelist" and is_admin:
                await self.update_server_whitelist()
                await message.channel.send(f"Updated server whitelist to: {self.white_list}")

            if cmd == "user_map":
                await message.channel.send(self.user_map)

            if cmd == "players_to_kick":
                await message.channel.send(await self.get_players_to_kick())

        # код для маппинга юзера дискорда с юзером в факторио
        else:
            if len(message.content) < 2 or len(message.content) > 30:
                await message.channel.send(f"Factorio user name must be min 2 and max 30 letters!")
                return

            allowed = set(string.ascii_lowercase + string.ascii_uppercase + string.digits + '.' + '-' + '_')
            if not set(message.content) <= allowed:
                await message.channel.send(
                    f"Factorio user name must include only alphabetical characters, numbers and .- but provide {message.content}")
                return

            user_exists = ""
            for user in self.user_map:
                if self.user_map[user] == message.content:
                    user_exists = user
            if user_exists:
                await message.add_reaction("❌")
                await message.channel.send(
                    f"Игрок {message.content} уже привязан к пользователю {user_exists}")
            else:
                self.user_map.update({
                    author: message.content
                })
                with open(USER_MAP_FILE, "w") as ufile:
                    ufile.write(json.dumps(self.user_map))
                # await message.channel.send(f"Discord User {author} mapped to {message.content}")
                await message.add_reaction("✅")

    async def on_voice_state_update(self, member, before, after):
        if not self.bot_enabled:
            return
        if not member.name in self.user_map:
            return
        user = self.user_map[member.name]
        is_admin = await self.is_factorio_admin(member)
        before_channel = before.channel and before.channel.name or None
        after_channel = after.channel and after.channel.name or None

        if before_channel and before_channel in FACTORIO_VOICE_CHANNELS:
            if after_channel and after_channel in FACTORIO_VOICE_CHANNELS:
                print(f"{user} сменил голосовой канал с {before_channel} на {after_channel}")
            else:
                if is_admin:
                    return
                await self.remove_user_from_whitelist(user)
                print(f"self.white_list_enabled: {self.white_list_enabled}")
                if self.white_list_enabled:
                    await self.execute_rcon(f"/kick {user} Покинул голосовой канал {before_channel}")

        if after_channel and after_channel in FACTORIO_VOICE_CHANNELS:
            await self.add_user_to_whitelist(user)

    async def on_member_update(self, before, after):
        # print("before:", before.name, "=>", ", ".join([r.name for r in before.roles]))
        # print("after:", after.name, "=>", ", ".join([r.name for r in after.roles]))
        if not after.name in self.user_map:
            print(not after.name in self.user_map)
            return
        admins = await self.get_factorio_admins()
        # print(f"admins: {admins}")
        factorio_name = self.user_map[after.name]
        # print(f"factorio_name: {factorio_name}")
        is_admin = await self.is_factorio_admin(after)
        # print(f"is_admin: {is_admin}")
        if is_admin:
            if factorio_name not in admins:
                # print(f"/promote {factorio_name}")
                result = await self.execute_rcon(f"/promote {factorio_name}")
                # print(result)
        else:
            if factorio_name in admins:
                # print(f"/demote {factorio_name}")
                result = await self.execute_rcon(f"/demote {factorio_name}")
                # print(result)
