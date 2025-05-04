# cogs/transaction_commands.py
import disnake
from disnake.ext import commands
import json
import asyncio
from datetime import datetime
import sys
import os
import requests

# Add the dev directory to the path for importing license key generator
sys.path.append('dev')
from lisenceKey import generate_license_key

# Import common utilities from main
from main import load_json, save_json, get_item_by_attribute, USERS_PATH, PRODUCT_PATH, load_json_from_web

class TransactionCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # Handle buy button clicks
    @commands.Cog.listener("on_button_click")
    async def handle_buy_button(self, inter: disnake.MessageInteraction):
        if not inter.component.custom_id.startswith("buy:"):
            return
        
        # Extract product name from button custom_id
        product_name = inter.component.custom_id.split(":", 1)[1]
        
        # Load product data
        products = load_json_from_web(PRODUCT_PATH)
        if product_name not in products:
            await inter.response.send_message(
                "This product is no longer available.", 
                ephemeral=True
            )
            return
        
        product_data = products[product_name]
        price = product_data.get("price", 0)
        formatted_price = f"{price:,} VND"
        
        # Confirm interaction
        await inter.response.send_message(
            f"Processing your order for **{product_name}**...", 
            ephemeral=True
        )
        
        # If the product is free (price = 0), process it immediately without creating a ticket
        if price == 0:
            # Load user data
            users = load_json(USERS_PATH)
            user_id = str(inter.author.id)
            
            # Generate license key
            license_key = generate_license_key(user_id, product_name)
            
            # Update user data in database
            if user_id not in users:
                users[user_id] = {
                    "total-payment": 0,
                    "ownership": {}
                }
            
            users[user_id]["ownership"][product_name] = license_key
            
            # Save updated user data
            save_json(USERS_PATH, users)
            
            # Send product file to user via DM
            try:
                product_file_path = product_data.get("filename")
                if not product_file_path:
                    await inter.edit_original_message(
                        content="Error: Product file path is not defined in the database."
                    )
                    return
                
                # Create DM channel with user
                dm_channel = await inter.author.create_dm()
                
                # Create license info message
                license_embed = disnake.Embed(
                    title=f"Purchased Product: {product_name}",
                    description="Thank you for your download! Here is your license information:",
                    color=disnake.Color.green()
                )
                license_embed.add_field(name="License Key", value=f"`{license_key}`")
                license_embed.add_field(name="Product", value=product_name)
                license_embed.set_footer(text="Keep this license key safe as it confirms your ownership.")
                
                # Send license info and product file
                await dm_channel.send(embed=license_embed)
                
                # Check if the file exists and send it
                full_product_path = f"database/products/{product_file_path}"
                if os.path.exists(full_product_path):
                    await dm_channel.send(file=disnake.File(full_product_path))
                    await inter.edit_original_message(
                        content=f"✅ Your free product **{product_name}** has been delivered to your DMs!"
                    )
                else:
                    await inter.edit_original_message(
                        content=f"Warning: Product file not found. Please contact staff for assistance."
                    )
                
            except Exception as e:
                await inter.edit_original_message(
                    content=f"❌ Error delivering product: {str(e)}"
                )
            
            return
        
        # Create private channel for this transaction
        try:
            # Find or create transaction category
            guild = inter.guild
            transaction_category = None
            for category in guild.categories:
                if category.name == "Transactions":
                    transaction_category = category
                    break
                    
            if not transaction_category:
                transaction_category = await guild.create_category(
                    name="Transactions",
                    reason="Created to handle product transactions"
                )
            
            # Create private channel
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            channel_name = f"order-{inter.author.id}-{timestamp}"
            
            overwrites = {
                guild.default_role: disnake.PermissionOverwrite(read_messages=False),
                inter.author: disnake.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: disnake.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            
            # Grant access for staff role
            staff_role = None
            for role in guild.roles:
                if role.name == "Staff":
                    staff_role = role
                    break
                    
            if staff_role:
                overwrites[staff_role] = disnake.PermissionOverwrite(read_messages=True, send_messages=True)
            
            # Create transaction channel
            transaction_channel = await guild.create_text_channel(
                name=channel_name,
                category=transaction_category,
                overwrites=overwrites,
                topic=f"Transaction for {product_name} by {inter.author.name}"
            )
            
            # Create cancel button
            cancel_button = disnake.ui.Button(
                style=disnake.ButtonStyle.danger,
                label="Cancel Order",
                custom_id="cancel_order"
            )
            
            # Send initial message in transaction channel
            transaction_embed = disnake.Embed(
                title=f"Order: {product_name}",
                description=f"Thank you for your purchase request, {inter.author.mention}!",
                color=disnake.Color.teal()
            )
            transaction_embed.add_field(name="Price", value=formatted_price)
            transaction_embed.add_field(name="Status", value="⏳ Waiting for staff")
            transaction_embed.set_footer(text="A staff member will assist you shortly.")
            
            await transaction_channel.send(
                embed=transaction_embed,
                components=disnake.ui.ActionRow(cancel_button)
            )
            
            # Notify the user
            await inter.edit_original_message(
                content=f"Your order has been created! Please go to {transaction_channel.mention} to complete your purchase."
            )
            
        except Exception as e:
            await inter.edit_original_message(
                content=f"❌ Error creating transaction channel: {str(e)}"
            )

    # Handle cancel order button
    @commands.Cog.listener("on_button_click")
    async def handle_cancel_order(self, inter: disnake.MessageInteraction):
        if inter.component.custom_id != "cancel_order":
            return
        
        # Check if this is a transaction channel
        if not inter.channel.name.startswith("order-"):
            await inter.response.send_message("This command can only be used in transaction channels.", ephemeral=True)
            return
        
        # Check if user is the order creator
        parts = inter.channel.name.split("-")
        if len(parts) < 2:
            await inter.response.send_message("Could not determine user ID from channel name.", ephemeral=True)
            return
        
        try:
            user_id = int(parts[1])
            if user_id != inter.author.id:
                await inter.response.send_message("Only the order creator can cancel the order.", ephemeral=True)
                return
        except:
            await inter.response.send_message("Could not determine user ID from channel name.", ephemeral=True)
            return
        
        # Create confirmation view for cancellation
        class CancelConfirmView(disnake.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.confirmed = False
            
            @disnake.ui.button(label="Confirm Cancellation", style=disnake.ButtonStyle.danger)
            async def confirm_button(self, button: disnake.ui.Button, button_inter: disnake.MessageInteraction):
                self.confirmed = True
                self.stop()
                
                # Send cancellation message
                cancel_embed = disnake.Embed(
                    title="Order Cancelled",
                    description=f"This order has been cancelled by {button_inter.author.mention}.",
                    color=disnake.Color.red()
                )
                cancel_embed.set_footer(text=f"Cancelled by user on {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
                
                await button_inter.response.edit_message(content=None, embed=cancel_embed, view=None)
                
                # Send notification to notification channel
                try:
                    notification_channel = button_inter.guild.get_channel(1364933402234458162)
                    if notification_channel:
                        notification_embed = disnake.Embed(
                            title="Order Cancelled",
                            description=f"Order in channel {button_inter.channel.mention} has been cancelled by {button_inter.author.mention}.",
                            color=disnake.Color.red()
                        )
                        notification_embed.set_footer(text=f"Cancelled on {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
                        await notification_channel.send(embed=notification_embed)
                except Exception as e:
                    print(f"Error sending cancellation notification: {str(e)}")
                
                # Archive the channel
                await asyncio.sleep(3)  # Wait 3 seconds for user to read notification
                try:
                    await button_inter.channel.edit(name=f"cancelled-{button_inter.channel.name}")
                    await button_inter.followup.send("Channel has been marked as cancelled.", ephemeral=True)
                except Exception as e:
                    await button_inter.followup.send(f"Error marking channel: {str(e)}", ephemeral=True)
            
            @disnake.ui.button(label="Don't Cancel", style=disnake.ButtonStyle.secondary)
            async def cancel_button(self, button: disnake.ui.Button, button_inter: disnake.MessageInteraction):
                self.stop()
                await button_inter.response.edit_message(content="Order cancellation has been aborted.", embed=None, view=None)
            
            async def on_timeout(self):
                await self.message.edit(content="Order cancellation confirmation has expired.", view=None)
        
        # Display confirmation message
        confirmation_embed = disnake.Embed(
            title="Confirm Order Cancellation",
            description="Are you sure you want to cancel this order? This action cannot be undone.",
            color=disnake.Color.yellow()
        )
        
        view = CancelConfirmView()
        await inter.response.send_message(embed=confirmation_embed, view=view, ephemeral=True)
        view.message = await inter.original_message()

    # Transaction command group
    @commands.slash_command(
        name="transaction",
        description="Manage transaction status"
    )
    async def transaction(self, inter: disnake.ApplicationCommandInteraction):
        # This is just a parent command and won't do anything on its own
        pass

    @transaction.sub_command(
        name="sold",
        description="Mark a transaction as completed"
    )
    async def transaction_sold(self, inter: disnake.ApplicationCommandInteraction):
        # Check if this is a transaction channel
        if not inter.channel.name.startswith("order-"):
            await inter.response.send_message("This command can only be used in transaction channels.", ephemeral=True)
            return
        
        # Check if user has Staff role
        staff_role = get_item_by_attribute(inter.guild.roles, name="Staff")
        if staff_role not in inter.author.roles:
            await inter.response.send_message("Only staff can complete transactions.", ephemeral=True)
            return
        
        # Load products
        products = load_json_from_web(PRODUCT_PATH)
        if not products:
            await inter.response.send_message("Could not load product data.", ephemeral=True)
            return
        
        # Create product selection dropdown
        class ProductSelectView(disnake.ui.View):
            def __init__(self, bot):
                super().__init__(timeout=300)
                self.bot = bot
                
                # Create the select menu with product options
                options = [
                    disnake.SelectOption(label=product_name, description=f"Price: {product_data.get('price', 0):,} VND")
                    for product_name, product_data in products.items()
                ]
                
                select = disnake.ui.Select(
                    placeholder="Select the purchased product",
                    min_values=1,
                    max_values=1,
                    options=options,
                    custom_id="product_select"
                )
                
                self.add_item(select)
                
            async def on_timeout(self):
                await self.message.edit(content="Product selection has expired. Please try again.", view=None)
        
        # Send ephemeral message with product selection
        product_embed = disnake.Embed(
            title="Complete Transaction",
            description="Please select the product that was purchased:",
            color=disnake.Color.blue()
        )
        
        view = ProductSelectView(self.bot)
        await inter.response.send_message(embed=product_embed, view=view, ephemeral=True)
        view.message = await inter.original_message()

    @transaction.sub_command(
        name="archive",
        description="Archive current order channel"
    )
    async def transaction_archive(self, inter: disnake.ApplicationCommandInteraction):
        # Check if this is a transaction channel
        if not inter.channel.name.startswith("order-"):
            await inter.response.send_message("This command can only be used in transaction channels.", ephemeral=True)
            return
        
        # Check if user has Staff role
        staff_role = get_item_by_attribute(inter.guild.roles, name="Staff")
        if staff_role not in inter.author.roles:
            await inter.response.send_message("Only staff can archive transaction channels.", ephemeral=True)
            return
        
        await inter.response.defer(ephemeral=True)
        
        try:
            # Send message before archiving
            archive_embed = disnake.Embed(
                title="Channel Archived",
                description="This transaction channel has been archived by staff.",
                color=disnake.Color.dark_gray()
            )
            archive_embed.set_footer(text=f"Archived by {inter.author.name}")
            
            await inter.channel.send(embed=archive_embed)
            
            # Archive channel
            await inter.channel.edit(name=f"✓-{inter.channel.name}")
            await inter.followup.send("Channel has been successfully archived.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"Error when archiving channel: {str(e)}", ephemeral=True)

    # Handle product selection dropdown
    @commands.Cog.listener("on_dropdown")
    async def handle_product_select(self, inter: disnake.MessageInteraction):
        if not inter.component.custom_id == "product_select":
            return
        
        # Get selected product
        selected_product = inter.values[0]
        
        # Load product data
        products = load_json_from_web(PRODUCT_PATH)
        if selected_product not in products:
            await inter.response.send_message("The selected product no longer exists in the database.", ephemeral=True)
            return
        
        product_data = products[selected_product]
        expected_price = product_data.get("price", 0)
        
        # Create confirmation view
        class ConfirmationView(disnake.ui.View):
            def __init__(self, bot):
                super().__init__(timeout=300)
                self.confirmed = False
                self.bot = bot
            
            @disnake.ui.button(label="Confirm", style=disnake.ButtonStyle.success)
            async def confirm_button(self, button: disnake.ui.Button, button_inter: disnake.MessageInteraction):
                self.confirmed = True
                self.stop()
                await self.handle_confirmation(button_inter, selected_product)
            
            @disnake.ui.button(label="Select Different Product", style=disnake.ButtonStyle.secondary)
            async def rechoose_button(self, button: disnake.ui.Button, button_inter: disnake.MessageInteraction):
                # Show product selection again
                await self.show_product_selection(button_inter)
            
            async def on_timeout(self):
                await self.message.edit(content="Confirmation has expired. Please try again.", view=None)
                
            async def show_product_selection(self, inter: disnake.MessageInteraction):
                # Create product selection dropdown again
                options = [
                    disnake.SelectOption(label=product_name, description=f"Price: {product_data.get('price', 0):,} VND")
                    for product_name, product_data in products.items()
                ]
                
                select = disnake.ui.Select(
                    placeholder="Select the purchased product",
                    min_values=1,
                    max_values=1,
                    options=options,
                    custom_id="product_select"
                )
                
                new_view = disnake.ui.View(timeout=300)
                new_view.add_item(select)
                
                # Show selection again
                product_embed = disnake.Embed(
                    title="Complete Transaction",
                    description="Please select the product that was purchased:",
                    color=disnake.Color.blue()
                )
                
                await inter.response.edit_message(embed=product_embed, view=new_view)
                
            async def handle_confirmation(self, inter: disnake.MessageInteraction, product: str):
                # Extract user ID from channel name
                parts = inter.channel.name.split("-")
                if len(parts) < 2:
                    await inter.response.send_message("Could not determine user ID from channel name.", ephemeral=True)
                    return
                
                try:
                    user_id = parts[1]
                    user = await self.bot.fetch_user(int(user_id))
                except:
                    await inter.response.send_message("Could not find user for this transaction.", ephemeral=True)
                    return
                
                # Load product and user data
                products = load_json_from_web(PRODUCT_PATH)
                users = load_json(USERS_PATH)
                
                product_data = products[product]
                expected_price = product_data.get("price", 0)
                
                # If price is 0, process immediately without payment modal
                if expected_price == 0:
                    await inter.response.defer()
                    
                    # Generate license key
                    license_key = generate_license_key(user_id, product)
                    
                    # Update user data in database
                    if user_id not in users:
                        users[user_id] = {
                            "total-payment": 0,
                            "ownership": {}
                        }
                    
                    users[user_id]["ownership"][product] = license_key
                    
                    # Save updated user data
                    save_json(USERS_PATH, users)
                    
                    # Send product file to user via DM
                    try:
                        product_file_path = product_data.get("filename")
                        if not product_file_path:
                            await inter.followup.send("Error: Product file path is not defined in the database.", ephemeral=True)
                        else:
                            # Create DM channel with user
                            dm_channel = await user.create_dm()
                            
                            # Create license info message
                            license_embed = disnake.Embed(
                                title=f"Purchased Product: {product}",
                                description="Thank you for your download! Here is your license information:",
                                color=disnake.Color.green()
                            )
                            license_embed.add_field(name="License Key", value=f"`{license_key}`")
                            license_embed.add_field(name="Product", value=product)
                            license_embed.set_footer(text="Keep this license key safe as it confirms your ownership.")
                            
                            # Send license info and product file
                            await dm_channel.send(embed=license_embed)
                            
                            # Check if the file exists and send it
                            full_product_path = f"database/products/{product_file_path}"
                            if os.path.exists(full_product_path):
                                await dm_channel.send(file=disnake.File(full_product_path))
                            else:
                                await inter.followup.send(f"Warning: Product file not found at path: {full_product_path}", ephemeral=True)
                            
                            # Send confirmation in the transaction channel
                            completion_embed = disnake.Embed(
                                title="Transaction Complete",
                                description=f"✅ Product **{product}** has been delivered to {user.mention}",
                                color=disnake.Color.green()
                            )
                            completion_embed.add_field(name="License Key", value=f"`{license_key}`")
                            completion_embed.add_field(name="Payment Amount", value="Free")
                            completion_embed.set_footer(text=f"Transaction completed by {inter.author.name}")
                            
                            await inter.channel.send(embed=completion_embed)
                            
                            # Close channel after a delay
                            await inter.channel.send("This transaction channel will be archived in 5 minutes.")
                            await asyncio.sleep(300)  # Wait 5 minutes
                            
                            # Archive channel
                            try:
                                await inter.channel.edit(name=f"✓-{inter.channel.name}")
                            except:
                                # If archiving fails, try deleting
                                await inter.channel.delete(reason="Transaction completed")
                            
                    except Exception as e:
                        await inter.followup.send(f"Error completing transaction: {str(e)}", ephemeral=True)
                else:
                    # Create payment modal for paid products
                    class PaymentModal(disnake.ui.Modal):
                        def __init__(self):
                            components = [
                                disnake.ui.TextInput(
                                    label="Payment Amount (VND)",
                                    placeholder="Enter the amount the customer paid",
                                    custom_id="payment_amount",
                                    style=disnake.TextInputStyle.short,
                                    required=True,
                                    value=str(expected_price)  # Pre-fill with expected price
                                )
                            ]
                            super().__init__(
                                title="Complete Transaction",
                                components=components,
                                custom_id="transaction_complete_modal"
                            )
                        
                        async def callback(self, modal_inter: disnake.ModalInteraction):
                            # Get payment amount
                            payment_amount_str = modal_inter.text_values["payment_amount"]
                            
                            # Clean input data and convert to integer
                            try:
                                payment_amount = int(payment_amount_str.replace(",", "").replace(".", "").strip())
                            except ValueError:
                                await modal_inter.response.send_message("Invalid amount. Please enter a number.", ephemeral=True)
                                return
                            
                            # Check if the amount matches
                            if payment_amount != expected_price:
                                await modal_inter.response.send_message(
                                    f"⚠️ The payment amount ({payment_amount:,} VND) does not match the product price ({expected_price:,} VND).\n"
                                    f"Please verify the payment and try again.",
                                    ephemeral=True
                                )
                                return
                            
                            # Amount matches, process the transaction
                            await modal_inter.response.defer()
                            
                            # Generate license key
                            license_key = generate_license_key(user_id, product)
                            
                            # Update user data in database
                            if user_id not in users:
                                users[user_id] = {
                                    "total-payment": 0,
                                    "ownership": {}
                                }
                            
                            users[user_id]["total-payment"] += payment_amount
                            users[user_id]["ownership"][product] = license_key
                            
                            # Save updated user data
                            save_json(USERS_PATH, users)
                            
                            # Send product file to user via DM
                            try:
                                product_file_path = product_data.get("filename")
                                if not product_file_path:
                                    await modal_inter.followup.send("Error: Product file path is not defined in the database.", ephemeral=True)
                                else:
                                    # Create DM channel with user
                                    dm_channel = await user.create_dm()
                                    
                                    # Create license info message
                                    license_embed = disnake.Embed(
                                        title=f"Purchased Product: {product}",
                                        description="Thank you for your purchase! Here is your license information:",
                                        color=disnake.Color.green()
                                    )
                                    license_embed.add_field(name="License Key", value=f"`{license_key}`")
                                    license_embed.add_field(name="Product", value=product)
                                    license_embed.set_footer(text="Keep this license key safe as it confirms your purchase.")
                                    
                                    # Send license info and product file
                                    await dm_channel.send(embed=license_embed)
                                    
                                    # Check if the file exists and send it
                                    full_product_path = f"database/products/{product_file_path}"
                                    if os.path.exists(full_product_path):
                                        await dm_channel.send(file=disnake.File(full_product_path))
                                    else:
                                        await modal_inter.followup.send(f"Warning: Product file not found at path: {full_product_path}", ephemeral=True)
                                    
                                    # Send confirmation in the transaction channel
                                    completion_embed = disnake.Embed(
                                        title="Transaction Complete",
                                        description=f"✅ Product **{product}** has been delivered to {user.mention}",
                                        color=disnake.Color.green()
                                    )
                                    completion_embed.add_field(name="License Key", value=f"`{license_key}`")
                                    completion_embed.add_field(name="Payment Amount", value=f"{payment_amount:,} VND")
                                    completion_embed.set_footer(text=f"Transaction completed by {modal_inter.author.name}")
                                    
                                    await modal_inter.channel.send(embed=completion_embed)
                                    
                                    # Close channel after a delay
                                    await modal_inter.channel.send("This transaction channel will be archived in 5 minutes.")
                                    await asyncio.sleep(300)  # Wait 5 minutes
                                    
                                    # Archive channel (or delete it based on your preference)
                                    try:
                                        await modal_inter.channel.edit(name=f"✓-{modal_inter.channel.name}")
                                    except:
                                        # If archiving fails, try deleting
                                        await modal_inter.channel.delete(reason="Transaction completed")
                                    
                            except Exception as e:
                                await modal_inter.followup.send(f"Error completing transaction: {str(e)}", ephemeral=True)
                    
                    # Show payment modal
                    await inter.response.send_modal(PaymentModal())
        
        # Show confirmation message
        confirmation_embed = disnake.Embed(
            title="Confirm Transaction",
            description=f"Please confirm the transaction for:\n\n**Product:** {selected_product}\n**Price:** {expected_price:,} VND",
            color=disnake.Color.gold()
        )
        
        view = ConfirmationView()
        view.bot = self.bot
        await inter.response.edit_message(embed=confirmation_embed, view=view)
        view.message = await inter.original_message()

def setup(bot):
    bot.add_cog(TransactionCommands(bot))