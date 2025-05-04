import disnake
from disnake.ext import commands
import asyncio
import json
import datetime
from typing import Optional, Union
from main import ADMIN_ROLE_ID


class Moderations(commands.Cog):
    """Advanced moderation commands for server management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.warnings = {}
        self.load_warnings()
    
    def load_warnings(self):
        try:
            with open("database/warnings.json", "r") as f:
                self.warnings = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.warnings = {}
            self.save_warnings()
    
    def save_warnings(self):
        with open("database/warnings.json", "w") as f:
            json.dump(self.warnings, f, indent=4)
    
    def has_admin_role():
        async def predicate(inter):
            admin_role = inter.guild.get_role(ADMIN_ROLE_ID)
            if admin_role in inter.author.roles:
                return True
            await inter.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return False
        return commands.check(predicate)
    
    @commands.slash_command(name="warn", description="Warn a user for breaking rules")
    @commands.has_permissions(kick_members=True)
    async def warn(self, inter: disnake.ApplicationCommandInteraction, 
                  user: disnake.User, 
                  reason: str = "No reason provided"):
        """
        Warn a user for breaking rules
        
        Parameters
        ----------
        user: The user to warn
        reason: The reason for the warning
        """
        guild_id = str(inter.guild.id)
        user_id = str(user.id)
        
        if guild_id not in self.warnings:
            self.warnings[guild_id] = {}
        
        if user_id not in self.warnings[guild_id]:
            self.warnings[guild_id][user_id] = []
        
        warning = {
            "reason": reason,
            "timestamp": datetime.datetime.now().isoformat(),
            "moderator": str(inter.author.id)
        }
        
        self.warnings[guild_id][user_id].append(warning)
        self.save_warnings()
        
        # Create and send warning embed
        embed = disnake.Embed(
            title="⚠️ Warning Issued",
            description=f"{user.mention} has been warned.",
            color=disnake.Color.yellow()
        )
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Warnings", value=str(len(self.warnings[guild_id][user_id])))
        embed.set_footer(text=f"Warned by {inter.author.display_name}")
        
        await inter.response.send_message(embed=embed)
        
        # DM the user
        try:
            user_embed = disnake.Embed(
                title="⚠️ Warning Received",
                description=f"You have received a warning in {inter.guild.name}",
                color=disnake.Color.yellow()
            )
            user_embed.add_field(name="Reason", value=reason)
            user_embed.add_field(name="Total Warnings", value=str(len(self.warnings[guild_id][user_id])))
            
            await user.send(embed=user_embed)
        except disnake.Forbidden:
            await inter.followup.send("Could not DM the user about their warning.", ephemeral=True)
    
    @commands.slash_command(name="warnings", description="View warnings for a user")
    @commands.has_permissions(kick_members=True)
    async def warnings(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        """
        View warnings for a user
        
        Parameters
        ----------
        user: The user to check warnings for
        """
        guild_id = str(inter.guild.id)
        user_id = str(user.id)
        
        if guild_id not in self.warnings or user_id not in self.warnings[guild_id] or not self.warnings[guild_id][user_id]:
            embed = disnake.Embed(
                title="Warnings",
                description=f"{user.mention} has no warnings.",
                color=disnake.Color.green()
            )
            await inter.response.send_message(embed=embed)
            return
        
        warnings_list = self.warnings[guild_id][user_id]
        
        embed = disnake.Embed(
            title=f"Warnings for {user.display_name}",
            description=f"{user.mention} has {len(warnings_list)} warning(s).",
            color=disnake.Color.yellow()
        )
        
        for i, warning in enumerate(warnings_list, 1):
            moderator = inter.guild.get_member(int(warning["moderator"]))
            mod_name = moderator.display_name if moderator else "Unknown Moderator"
            
            timestamp = datetime.datetime.fromisoformat(warning["timestamp"])
            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            embed.add_field(
                name=f"Warning #{i}",
                value=f"**Reason:** {warning['reason']}\n**By:** {mod_name}\n**When:** {formatted_time}",
                inline=False
            )
        
        await inter.response.send_message(embed=embed)
    
    @commands.slash_command(name="clearwarnings", description="Clear warnings for a user")
    @has_admin_role()
    async def clearwarnings(self, inter: disnake.ApplicationCommandInteraction, 
                           user: disnake.User, 
                           warning_id: Optional[int] = None):
        """
        Clear warnings for a user
        
        Parameters
        ----------
        user: The user to clear warnings for
        warning_id: Specific warning ID to clear (optional)
        """
        guild_id = str(inter.guild.id)
        user_id = str(user.id)
        
        if guild_id not in self.warnings or user_id not in self.warnings[guild_id] or not self.warnings[guild_id][user_id]:
            await inter.response.send_message(f"{user.mention} has no warnings to clear.", ephemeral=True)
            return
        
        if warning_id is not None:
            if 1 <= warning_id <= len(self.warnings[guild_id][user_id]):
                self.warnings[guild_id][user_id].pop(warning_id - 1)
                self.save_warnings()
                await inter.response.send_message(f"Cleared warning #{warning_id} for {user.mention}.")
            else:
                await inter.response.send_message(f"Invalid warning ID. User has {len(self.warnings[guild_id][user_id])} warnings.", ephemeral=True)
        else:
            self.warnings[guild_id][user_id] = []
            self.save_warnings()
            await inter.response.send_message(f"Cleared all warnings for {user.mention}.")
    
    @commands.slash_command(name="timeout", description="Timeout a user for a specified duration")
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, inter: disnake.ApplicationCommandInteraction, 
                     user: disnake.Member, 
                     duration: str, 
                     reason: str = "No reason provided"):
        """
        Timeout a user for a specified duration
        
        Parameters
        ----------
        user: The user to timeout
        duration: Duration in format: 1d, 2h, 30m, 45s (d=days, h=hours, m=minutes, s=seconds)
        reason: Reason for the timeout
        """
        if user.top_role >= inter.author.top_role and inter.author.id != inter.guild.owner_id:
            await inter.response.send_message("You cannot timeout someone with a role higher than or equal to yours.", ephemeral=True)
            return
        
        # Parse duration
        duration_seconds = 0
        time_units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
        
        try:
            unit = duration[-1].lower()
            if unit not in time_units:
                raise ValueError("Invalid time unit")
            
            value = int(duration[:-1])
            duration_seconds = value * time_units[unit]
            
            if duration_seconds > 2419200:  # 28 days in seconds (Discord's max timeout)
                await inter.response.send_message("Timeout duration cannot exceed 28 days.", ephemeral=True)
                return
                
        except (ValueError, IndexError):
            await inter.response.send_message("Invalid duration format. Use format like: 1d, 2h, 30m, 45s", ephemeral=True)
            return
        
        # Apply timeout
        until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=duration_seconds)
        await user.timeout(until=until, reason=reason)
        
        # Format human-readable duration
        if unit == "d":
            readable_duration = f"{value} day(s)"
        elif unit == "h":
            readable_duration = f"{value} hour(s)"
        elif unit == "m":
            readable_duration = f"{value} minute(s)"
        else:
            readable_duration = f"{value} second(s)"
        
        # Create and send timeout embed
        embed = disnake.Embed(
            title="⏰ User Timed Out",
            description=f"{user.mention} has been timed out for {readable_duration}.",
            color=disnake.Color.orange()
        )
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Timed out by {inter.author.display_name}")
        
        await inter.response.send_message(embed=embed)
        
        # DM the user
        try:
            user_embed = disnake.Embed(
                title="⏰ You Have Been Timed Out",
                description=f"You have been timed out in {inter.guild.name} for {readable_duration}.",
                color=disnake.Color.orange()
            )
            user_embed.add_field(name="Reason", value=reason)
            
            await user.send(embed=user_embed)
        except disnake.Forbidden:
            pass
    
    @commands.slash_command(name="kick", description="Kick a user from the server")
    @commands.has_permissions(kick_members=True)
    async def kick(self, inter: disnake.ApplicationCommandInteraction, 
                  user: disnake.Member, 
                  reason: str = "No reason provided"):
        """
        Kick a user from the server
        
        Parameters
        ----------
        user: The user to kick
        reason: Reason for the kick
        """
        if user.top_role >= inter.author.top_role and inter.author.id != inter.guild.owner_id:
            await inter.response.send_message("You cannot kick someone with a role higher than or equal to yours.", ephemeral=True)
            return
        
        # Create and send kick embed
        embed = disnake.Embed(
            title="👢 User Kicked",
            description=f"{user.mention} has been kicked from the server.",
            color=disnake.Color.red()
        )
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Kicked by {inter.author.display_name}")
        
        # DM the user before kicking
        try:
            user_embed = disnake.Embed(
                title="👢 You Have Been Kicked",
                description=f"You have been kicked from {inter.guild.name}.",
                color=disnake.Color.red()
            )
            user_embed.add_field(name="Reason", value=reason)
            
            await user.send(embed=user_embed)
        except disnake.Forbidden:
            pass
        
        await user.kick(reason=reason)
        await inter.response.send_message(embed=embed)
    
    @commands.slash_command(name="ban", description="Ban a user from the server")
    @commands.has_permissions(ban_members=True)
    async def ban(self, inter: disnake.ApplicationCommandInteraction, 
                 user: Union[disnake.Member, disnake.User], 
                 reason: str = "No reason provided",
                 delete_messages: int = 0):
        """
        Ban a user from the server
        
        Parameters
        ----------
        user: The user to ban
        reason: Reason for the ban
        delete_messages: Number of days of messages to delete (0-7)
        """
        if isinstance(user, disnake.Member):
            if user.top_role >= inter.author.top_role and inter.author.id != inter.guild.owner_id:
                await inter.response.send_message("You cannot ban someone with a role higher than or equal to yours.", ephemeral=True)
                return
        
        # Validate delete_messages
        if not 0 <= delete_messages <= 7:
            await inter.response.send_message("Message deletion days must be between 0 and 7.", ephemeral=True)
            return
        
        # Create and send ban embed
        embed = disnake.Embed(
            title="🔨 User Banned",
            description=f"{user.mention} has been banned from the server.",
            color=disnake.Color.dark_red()
        )
        embed.add_field(name="Reason", value=reason)
        if delete_messages > 0:
            embed.add_field(name="Message Deletion", value=f"Deleted {delete_messages} days of messages")
        embed.set_footer(text=f"Banned by {inter.author.display_name}")
        
        # DM the user before banning if they're in the server
        if isinstance(user, disnake.Member):
            try:
                user_embed = disnake.Embed(
                    title="🔨 You Have Been Banned",
                    description=f"You have been banned from {inter.guild.name}.",
                    color=disnake.Color.dark_red()
                )
                user_embed.add_field(name="Reason", value=reason)
                
                await user.send(embed=user_embed)
            except disnake.Forbidden:
                pass
        
        await inter.guild.ban(user, reason=reason, delete_message_days=delete_messages)
        await inter.response.send_message(embed=embed)
    
    @commands.slash_command(name="unban", description="Unban a user from the server")
    @commands.has_permissions(ban_members=True)
    async def unban(self, inter: disnake.ApplicationCommandInteraction, 
                   user_id: str, 
                   reason: str = "No reason provided"):
        """
        Unban a user from the server
        
        Parameters
        ----------
        user_id: The ID of the user to unban
        reason: Reason for the unban
        """
        try:
            user_id = int(user_id)
        except ValueError:
            await inter.response.send_message("Invalid user ID. Please provide a valid user ID.", ephemeral=True)
            return
        
        try:
            # Fetch the ban entry
            ban_entry = await inter.guild.fetch_ban(disnake.Object(id=user_id))
            user = ban_entry.user
            
            # Unban the user
            await inter.guild.unban(user, reason=reason)
            
            # Create and send unban embed
            embed = disnake.Embed(
                title="🔓 User Unbanned",
                description=f"{user.mention} has been unbanned from the server.",
                color=disnake.Color.green()
            )
            embed.add_field(name="Reason", value=reason)
            embed.set_footer(text=f"Unbanned by {inter.author.display_name}")
            
            await inter.response.send_message(embed=embed)
            
        except disnake.NotFound:
            await inter.response.send_message("This user is not banned.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)
    
    @commands.slash_command(name="purge", description="Delete a specified number of messages")
    @commands.has_permissions(manage_messages=True)
    async def purge(self, inter: disnake.ApplicationCommandInteraction, 
                   amount: int, 
                   user: Optional[disnake.User] = None):
        """
        Delete a specified number of messages
        
        Parameters
        ----------
        amount: Number of messages to delete (1-100)
        user: Only delete messages from this user (optional)
        """
        if not 1 <= amount <= 100:
            await inter.response.send_message("You can only delete between 1 and 100 messages at a time.", ephemeral=True)
            return
        
        await inter.response.defer(ephemeral=True)
        
        if user:
            def check(message):
                return message.author.id == user.id
                
            deleted = await inter.channel.purge(limit=amount, check=check)
            await inter.followup.send(f"Deleted {len(deleted)} messages from {user.mention}.", ephemeral=True)
        else:
            deleted = await inter.channel.purge(limit=amount)
            await inter.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)


def setup(bot):
    bot.add_cog(Moderations(bot))
