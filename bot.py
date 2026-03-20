import discord
from discord.ext import commands, tasks
from datetime import datetime
import json
import os
import sys

# Configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Fichier de sauvegarde
DATA_FILE = 'makeup_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

data = load_data()

def get_current_month():
    return datetime.now().strftime("%Y-%m")

def calculate_points(count):
    if count == 0:
        return 0
    return 1 + (count - 1) // 3

# Salon à surveiller
MAKEUP_CHANNEL_NAME = "makeups"

# ===== VÉRIFICATION D'IMAGE =====
def message_has_image(message):
    """Vérifie si un message contient une image"""
    # Vérifier les pièces jointes
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith('image/'):
            return True
    
    # Vérifier les liens d'images
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4']
    content_lower = message.content.lower()
    for ext in image_extensions:
        if ext in content_lower:
            return True
    
    # Vérifier les liens Discord CDN
    if 'cdn.discordapp.com/attachments' in content_lower:
        return True
    
    return False

# ===== ÉVÉNEMENTS =====
@bot.event
async def on_ready():
    print(f"\n{'='*50}")
    print(f"✅ BOT CONNECTÉ !")
    print(f"📊 Nom: {bot.user.name}")
    print(f"🌍 Serveurs: {len(bot.guilds)}")
    print(f"📝 Salon surveillé: #{MAKEUP_CHANNEL_NAME}")
    print(f"🖼️ Mode images uniquement: ACTIVÉ")
    print(f"{'='*50}\n")
    check_new_month.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Vérifier si le message est dans le salon makeups
    if message.channel.name == MAKEUP_CHANNEL_NAME:
        
        # Vérifier si le message contient une image
        if not message_has_image(message):
            # Supprimer le message
            await message.delete()
            # Envoyer un message privé à l'utilisateur
            try:
                await message.author.send(f"❌ **Salon réservé aux photos !**\n\nLe salon #{MAKEUP_CHANNEL_NAME} est uniquement pour poster des photos de makeup. Votre message a été supprimé.\n\n📸 Postez votre photo (JPEG, PNG, GIF, etc.) pour gagner des points LXP !")
            except:
                pass  # Si l'utilisateur a bloqué les MP
            return  # Ne pas compter ce message

        # Si c'est une image, compter le makeup
        user_id = str(message.author.id)
        current_month = get_current_month()

        # Initialisation
        if user_id not in data:
            data[user_id] = {"count": 0, "month": current_month}
        if data[user_id]["month"] != current_month:
            data[user_id] = {"count": 0, "month": current_month}
            save_data(data)

        # Incrémentation
        data[user_id]["count"] += 1
        new_count = data[user_id]["count"]
        old_points = calculate_points(new_count - 1)
        new_points = calculate_points(new_count)
        save_data(data)

        # Message de gain de point uniquement
        if new_points > old_points:
            embed = discord.Embed(
                title="⭐ NOUVEAU POINT LXP ! ⭐",
                description=f"{message.author.mention} vient de gagner **{new_points} point(s)** !",
                color=discord.Color.gold()
            )
            embed.add_field(name="📸 Makeups postés", value=f"{new_count}", inline=True)
            embed.add_field(name="⭐ Total points", value=f"{new_points}", inline=True)
            embed.set_footer(text="Continuez comme ça ! 🎨")
            await message.channel.send(embed=embed)

    await bot.process_commands(message)

@tasks.loop(hours=24)
async def check_new_month():
    current_month = get_current_month()
    changed = False
    for uid, info in data.items():
        if info["month"] != current_month:
            info["count"] = 0
            info["month"] = current_month
            changed = True
    if changed:
        save_data(data)
        print(f"📅 Nouveau mois détecté : {current_month}")

# ===== COMMANDES =====
@bot.command()
async def points(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author
    uid = str(member.id)
    current_month = get_current_month()
    
    if uid in data and data[uid]["month"] == current_month:
        count = data[uid]["count"]
        points = calculate_points(count)
        embed = discord.Embed(
            title=f"📊 Points LXP de {member.display_name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="⭐ Points", value=f"**{points}**", inline=True)
        embed.add_field(name="📸 Makeups", value=f"{count}", inline=True)
        
        # Prochain point
        remaining = 3 - ((count - 1) % 3) if count > 0 else 1
        if remaining < 3:
            embed.add_field(name="🎯 Prochain point", value=f"{remaining} makeup(s)", inline=True)
        
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"📭 {member.display_name} n'a pas encore posté de makeup ce mois-ci.")

@bot.command()
async def leaderboard(ctx):
    current_month = get_current_month()
    users_points = []
    
    for uid, info in data.items():
        if info["month"] == current_month:
            points = calculate_points(info["count"])
            if points > 0:
                users_points.append((uid, points, info["count"]))
    
    users_points.sort(key=lambda x: x[1], reverse=True)
    
    embed = discord.Embed(title="🏆 CLASSEMENT LXP DU MOIS", color=discord.Color.gold())
    description = ""
    for i, (uid, pts, cnt) in enumerate(users_points[:10], 1):
        try:
            user = await bot.fetch_user(int(uid))
            if user:
                medal = ""
                if i == 1:
                    medal = "🥇 "
                elif i == 2:
                    medal = "🥈 "
                elif i == 3:
                    medal = "🥉 "
                description += f"{medal}**{i}.** {user.display_name} : **{pts}** pts ({cnt} makeups)\n"
        except:
            description += f"**{i}.** Utilisateur inconnu : **{pts}** pts\n"
    
    embed.description = description or "📭 Aucun point ce mois-ci"
    embed.set_footer(text=f"Mois de {get_current_month()}")
    await ctx.send(embed=embed)

@bot.command()
async def help_points(ctx):
    embed = discord.Embed(
        title="🎨 AIDE DU BOT",
        description="Système de points pour les makeups",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="📸 Comment gagner des points ?",
        value=f"Postez une **photo de makeup** dans #{MAKEUP_CHANNEL_NAME}\n"
              "• 1er makeup du mois → **1 point**\n"
              "• Puis **1 point** tous les **3 makeups**",
        inline=False
    )
    embed.add_field(
        name="💬 Commandes",
        value="`!points` - Voir vos points\n"
              "`!points @membre` - Voir les points d'un membre\n"
              "`!leaderboard` - Voir le classement\n"
              "`!help_points` - Aide",
        inline=False
    )
    await ctx.send(embed=embed)
# ===== COMMANDES ADMIN =====
@bot.command()
@commands.has_permissions(administrator=True)
async def reset_xp(ctx, member: discord.Member = None):
    """Réinitialise les points LXP (admin uniquement)"""
    
    confirm_msg = await ctx.send("⚠️ **ATTENTION !** ⚠️\n\nCette action va réinitialiser TOUS les points LXP.\n\nConfirmez-vous ? Répondez par **oui** ou **non** dans les 30 secondes.")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["oui", "non"]
    
    try:
        response = await bot.wait_for('message', timeout=30.0, check=check)
        
        if response.content.lower() == "non":
            await ctx.send("❌ Réinitialisation annulée.")
            return
        
        if member:
            uid = str(member.id)
            if uid in data:
                current_month = get_current_month()
                data[uid] = {"count": 0, "month": current_month}
                save_data(data)
                await ctx.send(f"✅ Points de {member.display_name} réinitialisés !")
            else:
                await ctx.send(f"❌ {member.display_name} n'a aucun point enregistré.")
        else:
            current_month = get_current_month()
            for uid in data:
                data[uid] = {"count": 0, "month": current_month}
            save_data(data)
            await ctx.send("✅ **Points LXP de TOUS les membres réinitialisés !**")
            
            embed = discord.Embed(
                title="🔄 RÉINITIALISATION",
                description="Les points LXP ont été réinitialisés !",
                color=discord.Color.orange()
            )
            embed.add_field(name="📅 Date", value=datetime.now().strftime("%d/%m/%Y"), inline=True)
            await ctx.send(embed=embed)
            
    except TimeoutError:
        await ctx.send("⏰ Temps écoulé, réinitialisation annulée.")

@bot.command()
@commands.has_permissions(administrator=True)
async def reset_member_xp(ctx, member: discord.Member):
    """Réinitialise les points d'un membre spécifique (admin uniquement)"""
    uid = str(member.id)
    if uid in data:
        current_month = get_current_month()
        data[uid] = {"count": 0, "month": current_month}
        save_data(data)
        await ctx.send(f"✅ Points de {member.display_name} réinitialisés !")
    else:
        await ctx.send(f"❌ {member.display_name} n'a aucun point enregistré.")

@bot.command()
@commands.has_permissions(administrator=True)
async def set_xp(ctx, member: discord.Member, count: int):
    """Définit manuellement le nombre de makeups d'un membre (admin uniquement)"""
    if count < 0:
        await ctx.send("❌ Le nombre de makeups ne peut pas être négatif.")
        return
    
    uid = str(member.id)
    current_month = get_current_month()
    
    if uid not in data:
        data[uid] = {"count": 0, "month": current_month}
    
    data[uid]["count"] = count
    data[uid]["month"] = current_month
    save_data(data)
    
    points = calculate_points(count)
    await ctx.send(f"✅ {member.display_name} a maintenant **{count}** makeups ce mois-ci ({points} points LXP).")

# ===== COMMANDES UTILISATEURS =====
@bot.command()
async def points(ctx, member: discord.Member = None):
    """Affiche les points LXP d'un membre"""
    if member is None:
        member = ctx.author
    uid = str(member.id)
    current_month = get_current_month()
    
    if uid in data and data[uid]["month"] == current_month:
        count = data[uid]["count"]
        points = calculate_points(count)
        embed = discord.Embed(
            title=f"📊 Points LXP de {member.display_name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="⭐ Points", value=f"**{points}**", inline=True)
        embed.add_field(name="📸 Makeups", value=f"{count}", inline=True)
        
        if count > 0:
            remaining = 3 - ((count - 1) % 3)
            if remaining < 3:
                embed.add_field(name="🎯 Prochain point", value=f"{remaining} makeup(s)", inline=True)
        
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"📭 {member.display_name} n'a pas encore posté de makeup ce mois-ci.")

@bot.command()
async def leaderboard(ctx):
    """Classement des points LXP du mois"""
    current_month = get_current_month()
    users_points = []
    
    for uid, info in data.items():
        if info["month"] == current_month:
            points = calculate_points(info["count"])
            if points > 0:
                users_points.append((uid, points, info["count"]))
    
    users_points.sort(key=lambda x: x[1], reverse=True)
    
    embed = discord.Embed(title="🏆 CLASSEMENT LXP DU MOIS", color=discord.Color.gold())
    description = ""
    for i, (uid, pts, cnt) in enumerate(users_points[:10], 1):
        try:
            user = await bot.fetch_user(int(uid))
            if user:
                medal = "🥇 " if i == 1 else "🥈 " if i == 2 else "🥉 " if i == 3 else ""
                description += f"{medal}**{i}.** {user.display_name} : **{pts}** pts ({cnt} makeups)\n"
        except:
            description += f"**{i}.** Utilisateur inconnu : **{pts}** pts\n"
    
    embed.description = description or "📭 Aucun point ce mois-ci"
    embed.set_footer(text=f"Mois de {get_current_month()}")
    await ctx.send(embed=embed)

@bot.command()
async def stats(ctx):
    """Affiche les statistiques du mois"""
    current_month = get_current_month()
    total_makeups = 0
    active_members = 0
    total_points = 0
    
    for uid, info in data.items():
        if info["month"] == current_month:
            if info["count"] > 0:
                active_members += 1
                total_makeups += info["count"]
                total_points += calculate_points(info["count"])
    
    embed = discord.Embed(title="📊 STATISTIQUES DU MOIS", color=discord.Color.green())
    embed.add_field(name="📸 Total makeups", value=f"{total_makeups}", inline=True)
    embed.add_field(name="⭐ Total points", value=f"{total_points}", inline=True)
    embed.add_field(name="👥 Membres actifs", value=f"{active_members}", inline=True)
    embed.add_field(name="📅 Mois", value=f"{current_month}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command()
async def help_points(ctx):
    """Affiche l'aide du bot"""
    embed = discord.Embed(
        title="🎨 AIDE DU BOT MAKEUP POINTS",
        description="Système de points pour votre association !",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="📸 COMMENT GAGNER DES POINTS ?",
        value=f"Postez une **photo de makeup** dans #{MAKEUP_CHANNEL_NAME}\n"
              "• 1er makeup du mois → **1 point**\n"
              "• Puis **1 point** tous les **3 makeups**\n"
              "• Les compteurs se réinitialisent chaque **mois**",
        inline=False
    )
    embed.add_field(
        name="💬 COMMANDES",
        value="`!points` - Voir vos points\n"
              "`!points @membre` - Voir les points d'un membre\n"
              "`!leaderboard` - Voir le classement\n"
              "`!stats` - Statistiques du mois\n"
              "`!help_points` - Afficher cette aide\n\n"
              "**Commandes admin :**\n"
              "`!reset_xp` - Réinitialiser tous les points\n"
              "`!reset_xp @membre` - Réinitialiser un membre\n"
              "`!set_xp @membre nombre` - Définir le nombre de makeups",
        inline=False
    )
    embed.set_footer(text="Bonne chance et faites de beaux makeups ! ✨")
    await ctx.send(embed=embed)

# ===== LANCEMENT =====
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    
    if not TOKEN:
        print("❌ Token manquant !")
        sys.exit(1)
    
    bot.run(TOKEN)
