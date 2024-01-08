import discord
from discord2rcon import DClient
from config import DISCORD_BOT_TOKEN


if __name__ == "__main__":
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.reactions = True
    app = DClient(intents=intents)
    app.run(DISCORD_BOT_TOKEN)
