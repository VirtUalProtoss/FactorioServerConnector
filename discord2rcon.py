import os
import json
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

    async def add_user_to_whitelist(self, username):
        self.white_list.append(username)
        await self.execute_rcon(f"/whitelist add {username}")

    async def remove_user_from_whitelist(self, username):
        del self.white_list[username]
        await self.execute_rcon(f"/whitelist remove {username}")

    async def update_server_whitelist(self):
        await self.execute_rcon("/whitelist clear")
        for username in self.white_list:
            await self.execute_rcon(f"/whitelist add {username}")

    async def is_factorio_admin(self, member):
        is_admin = False
        for role in member.roles:
            if role.name == FACTORIO_ADMIN_ROLE:
                is_admin = True
        return is_admin

    async def set_polling_interval(self, interval):
        self.whitelist_polling_interval = interval

    async def get_whitelist_enabled(self):
        await asyncio.sleep(self.whitelist_polling_interval)
        data = await self.execute_rcon("/wlist-state")
        print(f"get_whitelist_enabled: {data}")
        if bool(data):
            await self.execute_rcon(f"/whitelist enable")
        else:
            await self.execute_rcon(f"/whitelist disable")
        self.loop.create_task(self.get_whitelist_enabled())
    
    async def get_bot_enabled(self):
        await asyncio.sleep(self.whitelist_polling_interval)
        data = await self.execute_rcon("/bot-state")
        print(f"get_bot_enabled: {data}")
        if data == "on":
            self.bot_enabled = True
        else:
            self.bot_enabled = False
        self.loop.create_task(self.get_bot_enabled())

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
        self.loop.create_task(self.get_bot_enabled())
        print(f'We have logged in as {self.user}')

    async def on_message(self, message):
        # print(message)
        # if not self.bot_enabled:
        #     return
        is_admin = await self.is_factorio_admin(message.author)
        author = message.author.name
        if message.channel.name == DISCORD_MAP_CHANNEL:
            if is_admin:
                if message.content.startswith("/c"):
                    responce = await self.execute_rcon(message.content[3:])
                    if responce:
                        await message.channel.send(responce)
                if message.content.startswith(".wl_polling"):
                    if message.content == ".wl_polling":
                        await message.channel.send(f"{self.whitelist_polling_interval}")
                    else:
                        try:
                            self.set_polling_interval(int(message.content.split(" ")[-1]))
                            await message.channel.send(f"whitelist_polling_interval setted to {self.whitelist_polling_interval}")
                        except:
                            await message.channel.send(f"Bad value {message.content}")

            if message.content.startswith(".whitelist"):
                self.whitelist = await self.execute_rcon("/whitelist get")
                await message.channel.send(self.whitelist)

            elif message.content.startswith(".user_map"):
                await message.channel.send(self.user_map)

            else:
                if author != DISCORD_BOT_NAME and not message.content.startswith(".") and not message.content.startswith("/c"):
                    user_exists = ""
                    for user in self.user_map:
                        if self.user_map[user] == message.content:
                            user_exists = user
                    if user_exists:
                        await message.channel.send(f"Factorio user {message.content} already mapped to Discord user {user_exists}")
                    else:
                        self.user_map.update({
                            author: message.content
                        })
                        with open(USER_MAP_FILE, "w") as ufile:
                            ufile.write(json.dumps(self.user_map))
                        await message.channel.send(f"Discord User {author} mapped to {message.content}")

    async def on_voice_state_update(self, member, before, after):
        if not self.bot_enabled:
            return
        is_admin = await self.is_factorio_admin(member)
        before_channel = before.channel and before.channel.name or None
        after_channel = after.channel and after.channel.name or None
        if before_channel and before_channel in FACTORIO_VOICE_CHANNELS:
            if after_channel and after_channel in FACTORIO_VOICE_CHANNELS:
                print(f"{self.user_map[member.name]} сменил голосовой канал с {before_channel} на {after_channel}")
            else:
                if not is_admin:
                    print(f"/kick {user_map[member.name]} Покинул голосовой канал {before_channel}")
                    await self.remove_user_from_whitelist(self.user_map[member.name])
                    await self.execute_rcon(f"/kick {self.user_map[member.name]} Покинул голосовой канал {before_channel}")
        if after_channel and after_channel in FACTORIO_VOICE_CHANNELS:
            await self.add_user_to_whitelist(self.user_map[member.name])
