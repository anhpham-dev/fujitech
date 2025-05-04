# cogs/admin_commands.py
import disnake
from disnake.ext import commands
import json
import asyncio
from datetime import datetime
import sys

# Add the dev directory to the path for importing license key generator
sys.path.append('dev')

# Import common utilities from main
from main import save_json, ADMIN_ROLE_ID, MEMBERSHIP_ROLES, DEFAULT_CHANNELS_PATH, CATEGORY_PATH, PRODUCT_PATH, load_json_from_web

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Check if user has admin role
    def has_admin_role():
        async def predicate(inter):
            admin_role = inter.guild.get_role(ADMIN_ROLE_ID)
            if admin_role in inter.author.roles:
                return True
            await inter.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return False
        return commands.check(predicate)

    # Admin commands group
    @commands.slash_command(name="fuji", description="Fuji Studio admin tools")
    @has_admin_role()
    async def fuji(self, inter: disnake.ApplicationCommandInteraction):
        # This is a parent command and doesn't do anything on its own
        pass

    @fuji.sub_command(name="set-membership", description="Set membership level for a user")
    async def set_membership(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member = commands.Param(description="User to set membership for"),
        membership: str = commands.Param(
            description="Membership level",
            choices=list(MEMBERSHIP_ROLES.keys())
        )
    ):
        await inter.response.defer(ephemeral=True)
        
        try:
            # Get role for selected membership
            role_id = MEMBERSHIP_ROLES[membership]
            role = inter.guild.get_role(role_id)
            
            if not role:
                await inter.edit_original_message(content=f"❌ Could not find role for membership {membership}.")
                return
            
            # Remove any existing membership roles
            for role_name, role_id in MEMBERSHIP_ROLES.items():
                existing_role = inter.guild.get_role(role_id)
                if existing_role and existing_role in user.roles:
                    await user.remove_roles(existing_role)
            
            # Add new membership role
            await user.add_roles(role)
            
            await inter.edit_original_message(
                content=f"✅ Successfully set {user.mention}'s membership to **{membership}**."
            )
        except Exception as e:
            await inter.edit_original_message(
                content=f"❌ Error setting membership: {str(e)}"
            )

    @fuji.sub_command(name="post-default", description="Post default content to channels")
    async def post_default(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer(ephemeral=True)
        
        # Load default channels data
        default_channels = load_json_from_web(DEFAULT_CHANNELS_PATH)
        
        if not default_channels:
            await inter.edit_original_message(content="❌ Could not load default channels data.")
            return
        
        # Track stats for reporting
        stats = {
            "total_channels": 0,
            "posts_created": 0,
            "errors": 0
        }
        
        # Track channels that have been purged
        purged_channels = set()
        
        # Process each default channel
        for channel_key, channel_data in default_channels.items():
            try:
                channel_id = channel_data.get("channelId")
                if not channel_id:
                    await inter.followup.send(f"⚠️ No channel ID found for: {channel_key}", ephemeral=True)
                    stats["errors"] += 1
                    continue
                    
                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    await inter.followup.send(f"⚠️ Could not find channel: {channel_key}", ephemeral=True)
                    stats["errors"] += 1
                    continue
                
                # Only purge the channel if we haven't already
                if channel_id not in purged_channels:
                    await channel.purge(limit=100)
                    purged_channels.add(channel_id)
                    stats["total_channels"] += 1
                
                # Check if this is a multi-part channel (like roles-1, roles-2)
                channel_base = channel_key.split('-')[0] if '-' in channel_key else channel_key
                channel_parts = [k for k in default_channels.keys() if k.startswith(f"{channel_base}-")]
                
                # If this is a part of a multi-part channel, only process it once
                if channel_parts and channel_key != channel_parts[0]:
                    continue
                    
                # Post content for this channel
                if channel_parts:
                    # Handle multi-part channel (e.g.: roles-1, roles-2)
                    for part_key in sorted(channel_parts):
                        part_data = default_channels[part_key]
                        
                        # Post banner image if any
                        if part_data.get("bannerUrl"):
                            banner_embed = disnake.Embed(color=disnake.Color.teal())
                            banner_embed.set_image(url=part_data["bannerUrl"])
                            await channel.send(embed=banner_embed)
                            stats["posts_created"] += 1
                        
                        # Post content if any
                        if part_data.get("content"):
                            content_embed = disnake.Embed(
                                description=part_data["content"],
                                color=disnake.Color.blue()
                            )
                            await channel.send(embed=content_embed)
                            stats["posts_created"] += 1
                else:
                    # Handle single-part channel
                    # Post banner image if any
                    if channel_data.get("bannerUrl"):
                        banner_embed = disnake.Embed(color=disnake.Color.teal())
                        banner_embed.set_image(url=channel_data["bannerUrl"])
                        await channel.send(embed=banner_embed)
                        stats["posts_created"] += 1
                    
                    # Post content if any
                    if channel_data.get("content"):
                        content_embed = disnake.Embed(
                            description=channel_data["content"],
                            color=disnake.Color.blue()
                        )
                        await channel.send(embed=content_embed)
                        stats["posts_created"] += 1
                    
            except Exception as e:
                await inter.followup.send(f"❌ Error processing channel {channel_key}: {str(e)}", ephemeral=True)
                stats["errors"] += 1

        # Send final report
        report = disnake.Embed(
            title="Default Content Posted",
            description=f"✅ Posted content to {stats['total_channels']} channels with {stats['posts_created']} posts created",
            color=disnake.Color.green()
        )
        
        if stats["errors"] > 0:
            report.add_field(name="Errors", value=f"{stats['errors']} errors occurred. Check logs for details.")
        
        await inter.edit_original_message(embed=report)

    @fuji.sub_command(name="post-sells", description="Refresh product listing in store channels")
    async def post_sells(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer(ephemeral=True)
        
        # Load category and product data
        categories = load_json_from_web(CATEGORY_PATH)
        products = load_json_from_web(PRODUCT_PATH)
        
        if not categories or not products:
            await inter.edit_original_message(content="❌ Could not load category or product data.")
            return
        
        # Track stats for reporting
        stats = {
            "total_channels": 0,
            "products_posted": 0,
            "errors": 0
        }
        
        # Process each category
        for category_name, channel_id in categories.items():
            try:
                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    await inter.followup.send(f"⚠️ Could not find channel for category: {category_name}", ephemeral=True)
                    stats["errors"] += 1
                    continue
                
                # Purge channel
                await channel.purge(limit=100)
                stats["total_channels"] += 1
                
                # Post category title
                header_embed = disnake.Embed(
                    title=f"🛒 {category_name.upper()} PRODUCTS",
                    description="Browse our products below. Click the Buy button to purchase.",
                    color=disnake.Color.teal()
                )
                await channel.send(embed=header_embed)
                
                # Post each product in this category
                category_products = [p for p_name, p in products.items() if p.get("category", "").lower() == category_name.lower()]
                
                if not category_products:
                    empty_embed = disnake.Embed(
                        description="There are currently no products in this category.",
                        color=disnake.Color.light_grey()
                    )
                    await channel.send(embed=empty_embed)
                    continue
                
                for product_name, product_data in products.items():
                    if product_data.get("category", "").lower() != category_name.lower():
                        continue
                    
                    # Create product embed
                    product_embed = disnake.Embed(
                        title=product_name,
                        description=product_data.get("description", "No description"),
                        color=disnake.Color.blue()
                    )
                    
                    # Format price with commas
                    price = product_data.get("price", 0)
                    formatted_price = f"{price:,} VND"
                    
                    product_embed.add_field(name="Price", value=formatted_price)
                    
                    if product_data.get("images"):
                        product_embed.set_image(url=product_data["images"])
                    
                    # Create buy button
                    components = disnake.ui.ActionRow()
                    components.add_button(
                        style=disnake.ButtonStyle.success,
                        label=f"Buy for {formatted_price}",
                        custom_id=f"buy:{product_name}"
                    )
                    
                    await channel.send(embed=product_embed, components=[components])
                    stats["products_posted"] += 1
                    
            except Exception as e:
                await inter.followup.send(f"❌ Error processing category {category_name}: {str(e)}", ephemeral=True)
                stats["errors"] += 1
        
        # Send final report
        report = disnake.Embed(
            title="Product Refresh Complete",
            description=f"✅ Posted {stats['products_posted']} products across {stats['total_channels']} channels",
            color=disnake.Color.green()
        )
        
        if stats["errors"] > 0:
            report.add_field(name="Errors", value=f"{stats['errors']} errors occurred. Check logs for details.")
        
        await inter.edit_original_message(embed=report)

def setup(bot):
    bot.add_cog(AdminCommands(bot))