import disnake
from disnake.ext import commands
import asyncio
import json
import datetime
from typing import Optional, Union
from main import ADMIN_ROLE_ID


class Misc(commands.Cog):
    """Miscellaneous utility commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.ghost_ping_logs = {}
    
    def has_admin_role():
        async def predicate(inter):
            admin_role = inter.guild.get_role(ADMIN_ROLE_ID)
            if admin_role in inter.author.roles:
                return True
            await inter.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return False
        return commands.check(predicate)
    
    @commands.slash_command(name="slowmode", description="Set the slowmode for the current channel")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, inter: disnake.ApplicationCommandInteraction, seconds: int):
        """
        Set the slowmode for the current channel
        
        Parameters
        ----------
        seconds: The slowmode delay in seconds (0 to disable)
        """
        if seconds < 0:
            await inter.response.send_message("Slowmode delay cannot be negative.", ephemeral=True)
            return
        
        try:
            await inter.channel.edit(slowmode_delay=seconds)
            
            if seconds == 0:
                await inter.response.send_message("Slowmode has been disabled for this channel.")
            else:
                await inter.response.send_message(f"Slowmode set to {seconds} seconds for this channel.")
        except Exception as e:
            await inter.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        # Skip if message has no mentions or is from a bot
        if not message.mentions or message.author.bot:
            return
        
        # Check if the message was deleted within 5 seconds of being sent
        time_diff = datetime.datetime.now(datetime.timezone.utc) - message.created_at
        if time_diff.total_seconds() > 5:
            return
        
        # Log the ghost ping
        staff_channel = self.bot.get_channel(1364933402234458162)
        if staff_channel:
            mentioned_users = ", ".join([user.mention for user in message.mentions])
            
            embed = disnake.Embed(
                title="👻 Ghost Ping Detected",
                description=f"A message with mentions was deleted shortly after being sent.",
                color=disnake.Color.red(),
                timestamp=datetime.datetime.now()
            )
            embed.add_field(name="Author", value=f"{message.author.mention} ({message.author.name})", inline=False)
            embed.add_field(name="Channel", value=message.channel.mention, inline=False)
            embed.add_field(name="Mentioned Users", value=mentioned_users, inline=False)
            embed.add_field(name="Message Content", value=message.content[:1024] if message.content else "No content", inline=False)
            embed.set_footer(text=f"Author ID: {message.author.id}")
            
            await staff_channel.send(embed=embed)


def setup(bot):
    bot.add_cog(Misc(bot))
