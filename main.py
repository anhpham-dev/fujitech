# main.py
import disnake
from disnake.ext import commands
import json
import os
import asyncio
import sys
import requests
from env import *

# Add the dev directory to the path for importing license key generator
sys.path.append('dev')
from lisenceKey import generate_license_key

# Constants for file paths
# CATEGORY_PATH = "database/category.json"
# PRODUCT_PATH = "database/product.json"
USERS_PATH = "database/users.json"
# DEFAULT_CHANNELS_PATH = "database/defaultChannels.json"
PRODUCT_PATH = requests.get("https://violet-betteanne-78.tiiny.site/product.json").text
DEFAULT_CHANNELS_PATH = requests.get("https://violet-betteanne-78.tiiny.site/defaultChannels.json").text
CATEGORY_PATH = requests.get("https://violet-betteanne-78.tiiny.site/category.json").text

# Role IDs
ADMIN_ROLE_ID = 1266005007363215472
DEFAULT_ROLE_ID = 1365888967358287882
MEMBERSHIP_ROLES = {
    "Platinum": 1365889467780431993,
    "Amethyst": 1365889418942222437,
    "Diamond": 1365889372880375868,
    "Gold": 1365889268500795442,
    "Iron": 1365889018704953354
}

# Utility functions
def load_json(file_path):
    """Load JSON data from a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return {}

def load_json_from_web(file_path):
    """Load JSON data from a file"""
    try:
        return json.loads(file_path)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return {}

def save_json(file_path, data):
    """Save JSON data to a file"""
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=4)
        return True
    except Exception as e:
        print(f"Error saving to {file_path}: {e}")
        return False

def get_item_by_attribute(iterable, **attributes):
    """Find items in iterables by attribute values"""
    for item in iterable:
        matches = True
        for attr_name, attr_value in attributes.items():
            if getattr(item, attr_name, None) != attr_value:
                matches = False
                break
        if matches:
            return item
    return None

# Setup bot
intents = disnake.Intents.default()
intents.members = True  # Enable member intents to track joins
bot = commands.InteractionBot(intents=intents)

# Event handlers
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")
    await bot.change_presence(activity=disnake.Activity(type=disnake.ActivityType.watching, name="Fuji Studio"))

@bot.event
async def on_member_join(member):
    """Grant default role to new members"""
    try:
        default_role = member.guild.get_role(DEFAULT_ROLE_ID)
        if default_role:
            await member.add_roles(default_role)
            print(f"Added default role to {member.name}")
    except Exception as e:
        print(f"Error adding default role to {member.name}: {e}")

# Load all cogs
def load_cogs():
    for filename in os.listdir("cogs"):
        if filename.endswith(".py"):
            bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"Loaded cog: {filename[:-3]}")

if __name__ == "__main__":
    # Create cogs directory if it doesn't exist
    if not os.path.exists("cogs"):
        os.makedirs("cogs")
    
    # Load all cogs
    load_cogs()
    
    # Run the bot
    bot.run(BOT_TOKEN)