import disnake
from disnake.ext import commands, tasks
import asyncio
import datetime
import random
import json
import os

# Configuration - replace with your actual admin role ID
ADMIN_ROLE_ID = 123456789012345678  # Replace with your admin role ID

# Check if user has admin role
def has_admin_role():
    async def predicate(inter):
        admin_role = inter.guild.get_role(ADMIN_ROLE_ID)
        if admin_role in inter.author.roles:
            return True
        await inter.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return False
    return commands.check(predicate)

class GiveawayModal(disnake.ui.Modal):
    def __init__(self, cog):
        self.cog = cog
        components = [
            disnake.ui.TextInput(
                label="Prize",
                placeholder="What are you giving away?",
                custom_id="prize",
                style=disnake.TextInputStyle.short,
                max_length=100,
            ),
            disnake.ui.TextInput(
                label="Winners",
                placeholder="Number of winners (1-10)",
                custom_id="winners",
                style=disnake.TextInputStyle.short,
                max_length=2,
                value="1",
            ),
            disnake.ui.TextInput(
                label="Duration",
                placeholder="Duration in minutes",
                custom_id="duration",
                style=disnake.TextInputStyle.short,
                max_length=10,
                value="60",
            ),
            disnake.ui.TextInput(
                label="Description (Optional)",
                placeholder="Additional details about the giveaway",
                custom_id="description",
                style=disnake.TextInputStyle.paragraph,
                max_length=1000,
                required=False,
            ),
            disnake.ui.TextInput(
                label="Channel ID (Optional)",
                placeholder="Leave blank for current channel",
                custom_id="channel_id",
                style=disnake.TextInputStyle.short,
                max_length=20,
                required=False,
            ),
        ]
        super().__init__(title="Create a Giveaway", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        # Get values from the form
        prize = inter.text_values["prize"]
        
        # Validate winners
        try:
            winners_count = int(inter.text_values["winners"])
            if winners_count < 1 or winners_count > 10:
                return await inter.response.send_message("Number of winners must be between 1 and 10.", ephemeral=True)
        except ValueError:
            return await inter.response.send_message("Invalid number of winners. Please enter a number between 1 and 10.", ephemeral=True)
        
        # Validate duration
        try:
            duration_minutes = int(inter.text_values["duration"])
            if duration_minutes < 1:
                return await inter.response.send_message("Duration must be at least 1 minute.", ephemeral=True)
        except ValueError:
            return await inter.response.send_message("Invalid duration. Please enter a valid number of minutes.", ephemeral=True)
        
        description = inter.text_values["description"]
        
        # Get channel
        channel_id = inter.text_values["channel_id"]
        if channel_id:
            try:
                channel = inter.guild.get_channel(int(channel_id))
                if not channel:
                    return await inter.response.send_message(f"Channel with ID {channel_id} not found.", ephemeral=True)
            except ValueError:
                return await inter.response.send_message("Invalid channel ID format.", ephemeral=True)
        else:
            channel = inter.channel
        
        # Calculate end time
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
        
        # Create the giveaway
        await inter.response.send_message(f"Creating giveaway in {channel.mention}...", ephemeral=True)
        await self.cog.create_giveaway(channel, prize, winners_count, end_time, description, inter.author)

class GiveawayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.giveaways = []
        self.data_file = "database/giveaways.json"
        self.load_giveaways()
        self.check_giveaways.start()
    
    def cog_unload(self):
        self.check_giveaways.cancel()
        self.save_giveaways()
    
    def load_giveaways(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                    
                for giveaway_data in data:
                    end_time_str = giveaway_data["end_time"]
                    end_time = datetime.datetime.fromisoformat(end_time_str)
                    
                    # Skip already ended giveaways
                    if end_time < datetime.datetime.now():
                        continue
                    
                    self.giveaways.append({
                        "channel_id": giveaway_data["channel_id"],
                        "message_id": giveaway_data["message_id"],
                        "prize": giveaway_data["prize"],
                        "winners_count": giveaway_data["winners_count"],
                        "end_time": end_time,
                        "participants": giveaway_data["participants"],
                        "host_id": giveaway_data["host_id"],
                        "description": giveaway_data.get("description", "")
                    })
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"Error loading giveaways: {e}")
    
    def save_giveaways(self):
        try:
            data = []
            for giveaway in self.giveaways:
                data.append({
                    "channel_id": giveaway["channel_id"],
                    "message_id": giveaway["message_id"],
                    "prize": giveaway["prize"],
                    "winners_count": giveaway["winners_count"],
                    "end_time": giveaway["end_time"].isoformat(),
                    "participants": giveaway["participants"],
                    "host_id": giveaway["host_id"],
                    "description": giveaway.get("description", "")
                })
            
            with open(self.data_file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving giveaways: {e}")
    
    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        now = datetime.datetime.now()
        ended_giveaways = []
        
        for giveaway in self.giveaways:
            if giveaway["end_time"] <= now:
                ended_giveaways.append(giveaway)
        
        for giveaway in ended_giveaways:
            await self.end_giveaway(giveaway)
            self.giveaways.remove(giveaway)
        
        if ended_giveaways:
            self.save_giveaways()
    
    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()
    
    async def create_giveaway(self, channel, prize, winners_count, end_time, description, host):
        # Create giveaway embed
        embed = self.create_giveaway_embed(prize, winners_count, end_time, description, host, [])
        
        # Create giveaway buttons
        components = disnake.ui.ActionRow(
            disnake.ui.Button(
                style=disnake.ButtonStyle.primary,
                emoji="🎉",
                custom_id="giveaway_enter",
                label="Enter Giveaway"
            ),
            disnake.ui.Button(
                style=disnake.ButtonStyle.secondary,
                emoji="ℹ️",
                custom_id="giveaway_info",
                label="Giveaway Info"
            )
        )
        
        # Send the giveaway message
        message = await channel.send(embed=embed, components=[components])
        
        # Store giveaway data
        giveaway_data = {
            "channel_id": channel.id,
            "message_id": message.id,
            "prize": prize,
            "winners_count": winners_count,
            "end_time": end_time,
            "participants": [],
            "host_id": host.id,
            "description": description
        }
        
        self.giveaways.append(giveaway_data)
        self.save_giveaways()
    
    def create_giveaway_embed(self, prize, winners_count, end_time, description, host, participants):
        embed = disnake.Embed(
            title=f"🎉 GIVEAWAY: {prize}",
            color=disnake.Color.blue()
        )
        
        # Add description if available
        if description:
            embed.description = description
        
        # Add giveaway details
        time_left = end_time - datetime.datetime.now()
        hours, remainder = divmod(time_left.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        embed.add_field(
            name="Time Remaining:",
            value=f"{int(hours)}h {int(minutes)}m {int(seconds)}s",
            inline=True
        )
        
        embed.add_field(
            name="Winners:",
            value=f"{winners_count}",
            inline=True
        )
        
        embed.add_field(
            name="Entries:",
            value=f"{len(participants)}",
            inline=True
        )
        
        # Add host and end time information
        embed.add_field(
            name="Host:",
            value=f"<@{host.id}>" if hasattr(host, "id") else f"<@{host}>",
            inline=True
        )
        
        embed.add_field(
            name="Ends At:",
            value=f"<t:{int(end_time.timestamp())}:F>",
            inline=True
        )
        
        embed.set_footer(text="Click the 🎉 button to enter!")
        
        return embed
    
    async def end_giveaway(self, giveaway):
        try:
            channel = self.bot.get_channel(giveaway["channel_id"])
            if not channel:
                return
            
            try:
                message = await channel.fetch_message(giveaway["message_id"])
            except disnake.NotFound:
                return
            
            participants = giveaway["participants"]
            winners_count = giveaway["winners_count"]
            
            # Draw winners
            winners = []
            if participants:
                if len(participants) <= winners_count:
                    winners = participants
                else:
                    winners = random.sample(participants, winners_count)
            
            # Create winner announcement embed
            embed = disnake.Embed(
                title=f"🎉 GIVEAWAY ENDED: {giveaway['prize']}",
                color=disnake.Color.green()
            )
            
            if giveaway.get("description"):
                embed.description = giveaway["description"]
            
            if winners:
                winners_mention = ", ".join([f"<@{winner}>" for winner in winners])
                embed.add_field(name=f"Winner{'s' if len(winners) > 1 else ''}:", value=winners_mention)
                
                # Create congratulation message for winners
                congrats_message = f"🎊 Congratulations {winners_mention}! You won **{giveaway['prize']}**!"
            else:
                embed.add_field(name="Winner:", value="No valid participants entered the giveaway.")
                congrats_message = f"No winners were drawn for the **{giveaway['prize']}** giveaway."
            
            embed.add_field(name="Entries:", value=str(len(participants)), inline=True)
            embed.add_field(name="Host:", value=f"<@{giveaway['host_id']}>", inline=True)
            
            # Update the original message
            try:
                await message.edit(embed=embed, components=[])
                await channel.send(congrats_message)
            except disnake.HTTPException:
                pass
            
        except Exception as e:
            print(f"Error ending giveaway: {e}")
    
    @commands.Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id == "giveaway_enter":
            await self.handle_giveaway_enter(inter)
        elif inter.component.custom_id == "giveaway_info":
            await self.handle_giveaway_info(inter)
    
    async def handle_giveaway_enter(self, inter: disnake.MessageInteraction):
        for giveaway in self.giveaways:
            if giveaway["message_id"] == inter.message.id:
                user_id = inter.author.id
                
                if user_id in giveaway["participants"]:
                    # User already entered, remove them
                    giveaway["participants"].remove(user_id)
                    await inter.response.send_message("You have been removed from the giveaway.", ephemeral=True)
                else:
                    # Add user to participants
                    giveaway["participants"].append(user_id)
                    await inter.response.send_message("You have entered the giveaway! Good luck!", ephemeral=True)
                
                # Update the giveaway embed
                embed = self.create_giveaway_embed(
                    giveaway["prize"],
                    giveaway["winners_count"],
                    giveaway["end_time"],
                    giveaway.get("description", ""),
                    giveaway["host_id"],
                    giveaway["participants"]
                )
                
                await inter.message.edit(embed=embed)
                self.save_giveaways()
                return
        
        await inter.response.send_message("This giveaway is no longer active.", ephemeral=True)
    
    async def handle_giveaway_info(self, inter: disnake.MessageInteraction):
        for giveaway in self.giveaways:
            if giveaway["message_id"] == inter.message.id:
                # Check if the user has entered
                user_entered = inter.author.id in giveaway["participants"]
                
                # Create info embed
                embed = disnake.Embed(
                    title=f"Giveaway Info: {giveaway['prize']}",
                    color=disnake.Color.blue()
                )
                
                # Add description if available
                if giveaway.get("description"):
                    embed.description = giveaway["description"]
                
                # Add status field
                embed.add_field(
                    name="Your Status:",
                    value="✅ You have entered this giveaway" if user_entered else "❌ You have not entered this giveaway",
                    inline=False
                )
                
                # Add other information
                embed.add_field(
                    name="Total Entries:",
                    value=str(len(giveaway["participants"])),
                    inline=True
                )
                
                embed.add_field(
                    name="Winners:",
                    value=str(giveaway["winners_count"]),
                    inline=True
                )
                
                time_left = giveaway["end_time"] - datetime.datetime.now()
                hours, remainder = divmod(time_left.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                
                embed.add_field(
                    name="Time Remaining:",
                    value=f"{int(hours)}h {int(minutes)}m {int(seconds)}s",
                    inline=True
                )
                
                embed.add_field(
                    name="Host:",
                    value=f"<@{giveaway['host_id']}>",
                    inline=True
                )
                
                embed.add_field(
                    name="Ends At:",
                    value=f"<t:{int(giveaway['end_time'].timestamp())}:F>",
                    inline=True
                )
                
                await inter.response.send_message(embed=embed, ephemeral=True)
                return
        
        await inter.response.send_message("This giveaway is no longer active.", ephemeral=True)
    
    @commands.slash_command(
        name="giveaway", 
        description="Giveaway management commands"
    )
    async def giveaway(self, inter):
        # This is a group command - subcommands will handle the functionality
        pass
    
    @giveaway.sub_command(
        name="create", 
        description="Create a new giveaway (Admin only)"
    )
    @has_admin_role()
    async def giveaway_create(self, inter):
        # Show the giveaway creation form
        modal = GiveawayModal(self)
        await inter.response.send_modal(modal)
    
    @giveaway.sub_command(
        name="list", 
        description="List all active giveaways"
    )
    async def giveaway_list(self, inter):
        if not self.giveaways:
            return await inter.response.send_message("There are no active giveaways at the moment.", ephemeral=True)
        
        embed = disnake.Embed(
            title="Active Giveaways",
            color=disnake.Color.blue(),
            description=f"There are currently {len(self.giveaways)} active giveaways."
        )
        
        for i, giveaway in enumerate(self.giveaways, 1):
            time_left = giveaway["end_time"] - datetime.datetime.now()
            hours, remainder = divmod(time_left.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            channel = self.bot.get_channel(giveaway["channel_id"])
            channel_mention = channel.mention if channel else f"#deleted-channel ({giveaway['channel_id']})"
            
            embed.add_field(
                name=f"{i}. {giveaway['prize']}",
                value=(
                    f"Channel: {channel_mention}\n"
                    f"Winners: {giveaway['winners_count']}\n"
                    f"Entries: {len(giveaway['participants'])}\n"
                    f"Time Left: {int(hours)}h {int(minutes)}m {int(seconds)}s\n"
                    f"[Jump to Giveaway](https://discord.com/channels/{inter.guild.id}/{giveaway['channel_id']}/{giveaway['message_id']})"
                ),
                inline=False
            )
        
        await inter.response.send_message(embed=embed, ephemeral=True)
    
    @giveaway.sub_command(
        name="end", 
        description="End a giveaway early (Admin only)"
    )
    @has_admin_role()
    async def giveaway_end(
        self, 
        inter, 
        message_id: str = commands.Param(description="The message ID of the giveaway to end")
    ):
        try:
            message_id = int(message_id)
        except ValueError:
            return await inter.response.send_message("Invalid message ID format.", ephemeral=True)
        
        for giveaway in self.giveaways:
            if giveaway["message_id"] == message_id:
                await inter.response.send_message("Ending the giveaway...", ephemeral=True)
                await self.end_giveaway(giveaway)
                self.giveaways.remove(giveaway)
                self.save_giveaways()
                return
        
        await inter.response.send_message("Giveaway not found. Make sure you entered the correct message ID.", ephemeral=True)
    
    @giveaway.sub_command(
        name="reroll", 
        description="Reroll a giveaway that has ended (Admin only)"
    )
    @has_admin_role()
    async def giveaway_reroll(
        self, 
        inter, 
        message_id: str = commands.Param(description="The message ID of the ended giveaway"),
        winners_count: int = commands.Param(description="Number of winners to reroll", default=1)
    ):
        try:
            message_id = int(message_id)
        except ValueError:
            return await inter.response.send_message("Invalid message ID format.", ephemeral=True)
        
        # Load all giveaways from the file, including ended ones
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    all_giveaways = json.load(f)
                
                for giveaway_data in all_giveaways:
                    if giveaway_data["message_id"] == message_id:
                        # Found the giveaway
                        channel = self.bot.get_channel(giveaway_data["channel_id"])
                        if not channel:
                            return await inter.response.send_message("Channel not found.", ephemeral=True)
                        
                        participants = giveaway_data["participants"]
                        if not participants:
                            return await inter.response.send_message("No one entered that giveaway.", ephemeral=True)
                        
                        # Limit winners count
                        if winners_count > len(participants):
                            winners_count = len(participants)
                        
                        # Draw new winners
                        new_winners = random.sample(participants, winners_count)
                        winners_mention = ", ".join([f"<@{winner}>" for winner in new_winners])
                        
                        await inter.response.send_message(f"Rerolling winners for **{giveaway_data['prize']}**...", ephemeral=True)
                        
                        # Send new winners announcement
                        await channel.send(
                            f"🎊 **GIVEAWAY REROLL!** 🎊\n\n"
                            f"New winner{'s' if winners_count > 1 else ''} for **{giveaway_data['prize']}**: {winners_mention}\n"
                            f"Congratulations!"
                        )
                        
                        return
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error loading giveaways for reroll: {e}")
        
        await inter.response.send_message("Giveaway not found. Make sure you entered the correct message ID.", ephemeral=True)

def setup(bot):
    bot.add_cog(GiveawayCog(bot))