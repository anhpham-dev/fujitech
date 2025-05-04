import disnake
from disnake.ext import commands
import asyncio
import json
import datetime
import os
from typing import Optional, Union
from main import ADMIN_ROLE_ID, MEMBERSHIP_ROLES, save_json, load_json

class TicketDropdown(disnake.ui.StringSelect):
    def __init__(self):
        options = [
            disnake.SelectOption(label="Tư vấn hàng", description="Nhận tư vấn về sản phẩm", emoji="💬"),
            disnake.SelectOption(label="Báo cáo vấn đề", description="Báo cáo sự cố hoặc lỗi", emoji="🐛"),
            disnake.SelectOption(label="Mua hàng", description="Hỗ trợ quá trình mua hàng", emoji="🛒")
        ]
        super().__init__(
            placeholder="Chọn loại vấn đề của bạn...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category"
        )
    
    async def callback(self, inter: disnake.MessageInteraction):
        await inter.response.send_modal(
            title=f"Tạo ticket - {self.values[0]}",
            custom_id=f"ticket_modal:{self.values[0]}",
            components=[
                disnake.ui.TextInput(
                    label="Mô tả chi tiết vấn đề của bạn",
                    placeholder="Vui lòng mô tả chi tiết vấn đề để chúng tôi có thể hỗ trợ tốt hơn",
                    custom_id="issue_description",
                    style=disnake.TextInputStyle.paragraph,
                    max_length=1000
                )
            ]
        )

class TicketView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

class TicketSystem(commands.Cog):
    """Ticket system for support"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tickets_data = {}
        self.ticket_channel_id = 1364944971714527384
        self.tickets_file = "database/tickets.json"
        self.products_file = "database/product.json"
        self.ticket_logs_channel_id = 1368178718757093406
        self.load_tickets()
    
    def load_tickets(self):
        """Load tickets data from file"""
        self.tickets_data = load_json(self.tickets_file) or {}
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.tickets_file), exist_ok=True)
    
    def save_tickets(self):
        """Save tickets data to file"""
        save_json(self.tickets_file, self.tickets_data)
    
    def load_products(self):
        """Load products data from file"""
        try:
            return load_json(self.products_file) or {}
        except:
            return {}
    
    def has_admin_role():
        async def predicate(inter):
            admin_role = inter.guild.get_role(ADMIN_ROLE_ID)
            if admin_role in inter.author.roles:
                return True
            await inter.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return False
        return commands.check(predicate)
    
    def has_membership_role(self, member):
        """Check if member has any membership role"""
        for role_name, role_id in MEMBERSHIP_ROLES.items():
            if member.guild.get_role(role_id) in member.roles:
                return True
        return False
    
    @commands.slash_command(name="setup-ticket", description="Setup the ticket system")
    @has_admin_role()
    async def setup_ticket(self, inter: disnake.ApplicationCommandInteraction):
        """Setup the ticket system by creating the ticket creation message"""
        channel = self.bot.get_channel(self.ticket_channel_id)
        if not channel:
            await inter.response.send_message("Ticket channel not found. Please check the channel ID.", ephemeral=True)
            return
        
        embed = disnake.Embed(
            title="🎫 Hệ thống hỗ trợ Fuji Studio",
            description="Vui lòng chọn loại vấn đề của bạn từ menu bên dưới để tạo ticket hỗ trợ.",
            color=disnake.Color.blue()
        )
        embed.add_field(
            name="Hướng dẫn",
            value="1. Chọn loại vấn đề từ menu dropdown\n2. Điền thông tin chi tiết về vấn đề của bạn\n3. Đội ngũ hỗ trợ sẽ liên hệ với bạn sớm nhất có thể",
            inline=False
        )
        embed.set_footer(text="Fuji Studio Support System")
        
        await channel.send(embed=embed, view=TicketView())
        await inter.response.send_message("Ticket system has been set up successfully!", ephemeral=True)
    
    @commands.Cog.listener()
    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        """Handle ticket creation modal submissions"""
        if not inter.custom_id.startswith("ticket_modal:"):
            return
        
        category = inter.custom_id.split(":")[1]
        issue_description = inter.text_values["issue_description"]
        
        guild_id = str(inter.guild.id)
        user_id = str(inter.author.id)
        
        # Initialize guild data if not exists
        if guild_id not in self.tickets_data:
            self.tickets_data[guild_id] = {"tickets": {}, "counter": 0}
        
        # Check if user already has an open ticket
        for ticket_id, ticket in self.tickets_data[guild_id]["tickets"].items():
            if ticket["user_id"] == user_id and ticket["status"] == "open":
                await inter.response.send_message(
                    f"Bạn đã có một ticket đang mở. Vui lòng sử dụng ticket hiện có.",
                    ephemeral=True
                )
                return
        
        # Create new ticket
        ticket_number = self.tickets_data[guild_id]["counter"] + 1
        self.tickets_data[guild_id]["counter"] = ticket_number
        
        # Create ticket channel
        ticket_channel = await inter.guild.create_text_channel(
            name=f"ticket-{ticket_number}-{inter.author.name}",
            category=self.bot.get_channel(self.ticket_channel_id).category,
            topic=f"Support ticket for {inter.author.display_name} | Category: {category} | Issue: {issue_description[:50]}..."
        )
        
        # Set permissions
        await ticket_channel.set_permissions(inter.guild.default_role, read_messages=False)
        await ticket_channel.set_permissions(inter.author, read_messages=True, send_messages=True)
        
        # Admin role permissions
        admin_role = inter.guild.get_role(ADMIN_ROLE_ID)
        if admin_role:
            await ticket_channel.set_permissions(admin_role, read_messages=True, send_messages=True)
        
        # Store ticket data
        ticket_data = {
            "ticket_id": str(ticket_number),
            "channel_id": str(ticket_channel.id),
            "user_id": user_id,
            "category": category,
            "issue": issue_description,
            "status": "open",
            "created_at": datetime.datetime.now().isoformat(),
            "messages": []
        }
        
        self.tickets_data[guild_id]["tickets"][str(ticket_number)] = ticket_data
        self.save_tickets()
        
        # Create welcome embed
        embed = disnake.Embed(
            title=f"Ticket #{ticket_number} - {category}",
            description=f"Cảm ơn bạn đã tạo ticket, {inter.author.mention}. Đội ngũ hỗ trợ sẽ giúp đỡ bạn sớm nhất có thể.",
            color=disnake.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="Vấn đề", value=issue_description, inline=False)
        embed.set_footer(text=f"Ticket được tạo bởi {inter.author.display_name}")
        
        # Create close button
        close_button = disnake.ui.Button(
            style=disnake.ButtonStyle.danger,
            label="Đóng Ticket",
            custom_id=f"close_ticket:{ticket_number}"
        )
        
        components = disnake.ui.ActionRow(close_button)
        
        await ticket_channel.send(embed=embed, components=components)
        
        # Send confirmation to user
        await inter.response.send_message(
            f"Ticket đã được tạo thành công! Vui lòng kiểm tra {ticket_channel.mention}",
            ephemeral=True
        )
        
        # Send message that they need to wait for staff
        await ticket_channel.send(
            embed=disnake.Embed(
                title="Đang chờ hỗ trợ",
                description="Nhân viên hỗ trợ sẽ phản hồi ticket của bạn sớm nhất có thể. Cảm ơn bạn đã kiên nhẫn chờ đợi.",
                color=disnake.Color.orange()
            )
        )
    
    async def create_ticket_transcript(self, channel, ticket_data):
        """Create HTML transcript of ticket conversation"""
        messages = []
        async for message in channel.history(limit=500, oldest_first=True):
            if message.author.bot and not message.embeds:
                continue
                
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
            
            if message.embeds:
                for embed in message.embeds:
                    content = f"<div class='embed'><div class='embed-title'>{embed.title or ''}</div>"
                    if embed.description:
                        content += f"<div class='embed-description'>{embed.description}</div>"
                    for field in embed.fields:
                        content += f"<div class='embed-field'><div class='field-name'>{field.name}</div><div class='field-value'>{field.value}</div></div>"
                    content += "</div>"
                    
                    messages.append({
                        "author": message.author.display_name,
                        "avatar": str(message.author.display_avatar.url),
                        "content": content,
                        "timestamp": timestamp
                    })
            else:
                messages.append({
                    "author": message.author.display_name,
                    "avatar": str(message.author.display_avatar.url),
                    "content": message.content,
                    "timestamp": timestamp
                })
        
        # Create HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Ticket #{ticket_data['ticket_id']} - {ticket_data['category']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background-color: white; border-radius: 5px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 20px; }}
        .message {{ display: flex; margin-bottom: 15px; }}
        .avatar {{ width: 40px; height: 40px; border-radius: 50%; margin-right: 10px; }}
        .message-content {{ flex: 1; }}
        .message-header {{ display: flex; align-items: center; margin-bottom: 5px; }}
        .author-name {{ font-weight: bold; margin-right: 10px; }}
        .timestamp {{ color: #999; font-size: 0.8em; }}
        .message-text {{ background-color: #f9f9f9; padding: 10px; border-radius: 5px; }}
        .embed {{ background-color: #f0f0f0; border-left: 4px solid #7289da; padding: 10px; margin-top: 5px; }}
        .embed-title {{ font-weight: bold; margin-bottom: 5px; }}
        .embed-description {{ margin-bottom: 10px; }}
        .embed-field {{ margin-top: 5px; }}
        .field-name {{ font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Ticket #{ticket_data['ticket_id']} - {ticket_data['category']}</h2>
            <p><strong>Issue:</strong> {ticket_data['issue']}</p>
            <p><strong>Created:</strong> {datetime.datetime.fromisoformat(ticket_data['created_at']).strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Closed:</strong> {datetime.datetime.fromisoformat(ticket_data['closed_at']).strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        <div class="messages">
"""
        
        for msg in messages:
            html += f"""
            <div class="message">
                <img class="avatar" src="{msg['avatar']}" alt="{msg['author']}">
                <div class="message-content">
                    <div class="message-header">
                        <div class="author-name">{msg['author']}</div>
                        <div class="timestamp">{msg['timestamp']}</div>
                    </div>
                    <div class="message-text">{msg['content']}</div>
                </div>
            </div>
"""
        
        html += """
        </div>
    </div>
</body>
</html>
"""
        return html
    
    @commands.Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        """Handle button interactions for tickets"""
        if not inter.component.custom_id.startswith("close_ticket:"):
            return
        
        ticket_number = inter.component.custom_id.split(":")[1]
        guild_id = str(inter.guild.id)
        
        # Verify ticket exists
        if (guild_id not in self.tickets_data or 
            ticket_number not in self.tickets_data[guild_id]["tickets"]):
            await inter.response.send_message("Ticket này không còn tồn tại.", ephemeral=True)
            return
        
        ticket = self.tickets_data[guild_id]["tickets"][ticket_number]
        
        # Check if user is ticket creator or has admin role
        is_admin = inter.guild.get_role(ADMIN_ROLE_ID) in inter.author.roles
        is_ticket_creator = str(inter.author.id) == ticket["user_id"]
        
        if not (is_admin or is_ticket_creator):
            await inter.response.send_message("Bạn không có quyền đóng ticket này.", ephemeral=True)
            return
        
        # Close the ticket
        ticket["status"] = "closed"
        ticket["closed_at"] = datetime.datetime.now().isoformat()
        ticket["closed_by"] = str(inter.author.id)
        self.save_tickets()
        
        # Send confirmation message
        await inter.response.send_message(f"Ticket #{ticket_number} đã được đóng bởi {inter.author.mention}.")
        
        # Create transcript
        transcript_embed = disnake.Embed(
            title=f"Ticket #{ticket_number} - Transcript",
            description=f"Ticket đã đóng bởi {inter.author.mention}",
            color=disnake.Color.red(),
            timestamp=datetime.datetime.now()
        )
        transcript_embed.add_field(name="Vấn đề", value=ticket["issue"], inline=False)
        
        # Create HTML transcript
        html_transcript = await self.create_ticket_transcript(inter.channel, ticket)
        
        # Save transcript to file
        transcript_filename = f"ticket_{guild_id}_{ticket_number}.html"
        with open(transcript_filename, "w", encoding="utf-8") as f:
            f.write(html_transcript)
        
        # Send transcript to logs channel
        logs_channel = self.bot.get_channel(self.ticket_logs_channel_id)
        if logs_channel:
            user = inter.guild.get_member(int(ticket["user_id"]))
            user_mention = user.mention if user else f"User ID: {ticket['user_id']}"
            
            log_embed = disnake.Embed(
                title=f"Ticket #{ticket_number} - {ticket['category']}",
                description=f"Ticket đã được đóng bởi {inter.author.mention}",
                color=disnake.Color.red(),
                timestamp=datetime.datetime.now()
            )
            log_embed.add_field(name="Người tạo", value=user_mention, inline=True)
            log_embed.add_field(name="Vấn đề", value=ticket["issue"][:1024], inline=False)
            
            await logs_channel.send(embed=log_embed, file=disnake.File(transcript_filename))
        
        # Delete the temporary file
        try:
            os.remove(transcript_filename)
        except Exception as e:
            print(f"Error removing transcript file: {e}")
        
        # Notify user that channel will be deleted
        await inter.channel.send("Kênh này sẽ bị xóa sau 5 giây.")
        await asyncio.sleep(5)  # Wait 5 seconds
        
        # Delete the channel
        try:
            await inter.channel.delete(reason=f"Ticket #{ticket_number} closed by {inter.author}")
        except Exception as e:
            print(f"Error deleting channel: {e}")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for messages in ticket channels"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if message is in a ticket channel
        if not message.guild or not message.channel.name.startswith("ticket-"):
            return
        
        # Find ticket data
        guild_id = str(message.guild.id)
        if guild_id not in self.tickets_data:
            return
        
        ticket_number = None
        for t_num, ticket in self.tickets_data[guild_id]["tickets"].items():
            if str(message.channel.id) == ticket["channel_id"] and ticket["status"] == "open":
                ticket_number = t_num
                break
        
        if not ticket_number:
            return
        
        # Store message in ticket history
        ticket = self.tickets_data[guild_id]["tickets"][ticket_number]
        ticket["messages"].append({
            "author_id": str(message.author.id),
            "author_name": message.author.display_name,
            "content": message.content,
            "timestamp": datetime.datetime.now().isoformat()
        })
        self.save_tickets()
    
    @commands.slash_command(name="tickets", description="View all active tickets")
    @has_admin_role()
    async def view_tickets(self, inter: disnake.ApplicationCommandInteraction):
        """View all active tickets (Admin only)"""
        guild_id = str(inter.guild.id)
        
        if guild_id not in self.tickets_data or not self.tickets_data[guild_id]["tickets"]:
            await inter.response.send_message("Không có ticket nào trong server này.", ephemeral=True)
            return
        
        # Create embed with active tickets
        embed = disnake.Embed(
            title="Ticket đang hoạt động",
            description="Danh sách tất cả các ticket hỗ trợ đang mở",
            color=disnake.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        active_tickets = 0
        for ticket_id, ticket in self.tickets_data[guild_id]["tickets"].items():
            if ticket["status"] == "open":
                active_tickets += 1
                user = inter.guild.get_member(int(ticket["user_id"]))
                user_mention = user.mention if user else f"User ID: {ticket['user_id']}"
                
                channel = inter.guild.get_channel(int(ticket["channel_id"]))
                channel_mention = channel.mention if channel else "Không tìm thấy kênh"
                
                category = ticket.get("category", "Hỗ trợ chung")
                
                embed.add_field(
                    name=f"Ticket #{ticket_id} - {category}",
                    value=f"Người dùng: {user_mention}\nKênh: {channel_mention}\nVấn đề: {ticket['issue'][:100]}...",
                    inline=False
                )
        
        if active_tickets == 0:
            embed.description = "Hiện tại không có ticket nào đang hoạt động."
        
        await inter.response.send_message(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(TicketSystem(bot))
