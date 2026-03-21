import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
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
REPORT_CHANNEL_NAME = "botlxp"   

# ===== VÉRIFICATION D'IMAGE =====
def message_has_image(message):
    """Vérifie si un message contient une image"""
    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith('image/'):
            return True
    
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4']
    content_lower = message.content.lower()
    for ext in image_extensions:
        if ext in content_lower:
            return True
    
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
    
    if message.channel.name == MAKEUP_CHANNEL_NAME:
        
        if not message_has_image(message):
            await message.delete()
            try:
                await message.author.send(f"❌ **Salon réservé aux photos !**\n\nLe salon #{MAKEUP_CHANNEL_NAME} est uniquement pour poster des photos de makeup. Votre message a été supprimé.\n\n📸 Postez votre photo (JPEG, PNG, GIF, etc.) pour gagner des points LXP !")
            except:
                pass
            return

        user_id = str(message.author.id)
        current_month = get_current_month()

        if user_id not in data:
            data[user_id] = {"count": 0, "month": current_month}
        if data[user_id]["month"] != current_month:
            data[user_id] = {"count": 0, "month": current_month}
            save_data(data)

        data[user_id]["count"] += 1
        new_count = data[user_id]["count"]
        old_points = calculate_points(new_count - 1)
        new_points = calculate_points(new_count)
        save_data(data)

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
    """Vérifie chaque jour si le mois a changé et envoie un bilan"""
    current_month = get_current_month()
    previous_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    
    # Détecter si on vient de passer au nouveau mois
    # On vérifie si des données existent encore pour l'ancien mois
    has_old_data = any(info.get("month") == previous_month for info in data.values())
    
    if has_old_data:
        # On est le 1er du mois et il y a des données de l'ancien mois → envoyer le bilan
        await send_monthly_report(previous_month)
    
    # Réinitialiser les compteurs pour le nouveau mois
    changed = False
    for uid, info in data.items():
        if info["month"] != current_month:
            info["count"] = 0
            info["month"] = current_month
            changed = True
    if changed:
        save_data(data)
        print(f"📅 Nouveau mois détecté : {current_month} - Compteurs réinitialisés")

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
    best_member_name = None
    best_member_points = 0
    best_member_count = 0
    
    for uid, info in data.items():
        if info.get("month") == current_month:
            count = info.get("count", 0)
            if count > 0:
                active_members += 1
                total_makeups += count
                points = calculate_points(count)
                total_points += points
                
                if points > best_member_points:
                    best_member_points = points
                    best_member_count = count
                    try:
                        user = await bot.fetch_user(int(uid))
                        best_member_name = user.display_name if user else "Inconnu"
                    except:
                        best_member_name = "Inconnu"
    
    embed = discord.Embed(
        title="📊 STATISTIQUES DU MOIS",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    
    embed.add_field(name="📸 Total makeups", value=f"**{total_makeups}**", inline=True)
    embed.add_field(name="⭐ Total points", value=f"**{total_points}**", inline=True)
    embed.add_field(name="👥 Membres actifs", value=f"**{active_members}**", inline=True)
    
    if best_member_name and best_member_points > 0:
        embed.add_field(
            name="🏆 Meilleur membre du mois",
            value=f"{best_member_name}\n**{best_member_points}** points ({best_member_count} makeups)",
            inline=False
        )
    
    if active_members > 0:
        avg_makeups = round(total_makeups / active_members, 1)
        embed.add_field(name="📊 Moyenne par membre", value=f"{avg_makeups} makeups", inline=True)
    
    embed.add_field(name="📅 Mois", value=f"**{current_month}**", inline=True)
    embed.set_footer(text="Continuez à poster vos makeups ! 🎨")
    
    await ctx.send(embed=embed)
@bot.command()
async def participants(ctx):
    """Affiche la liste de tous les participants du mois avec leurs points"""
    current_month = get_current_month()
    users_list = []
    
    # Récupérer tous les participants
    for uid, info in data.items():
        if info.get("month") == current_month:
            count = info.get("count", 0)
            if count > 0:
                points = calculate_points(count)
                users_list.append((uid, count, points))
    
    # Trier par points (du plus haut au plus bas)
    users_list.sort(key=lambda x: x[2], reverse=True)
    
    if not users_list:
        await ctx.send("📭 **Aucun participant ce mois-ci.**\n\nPostez des makeups dans #makeups pour apparaître dans le tableau !")
        return
    
    # Créer le tableau
    embed = discord.Embed(
        title="📋 TABLEAU DES PARTICIPANTS",
        description=f"**Mois : {current_month}**\n\nVoici tous les membres qui ont participé ce mois-ci :",
        color=discord.Color.blue()
    )
    
    # Construire le tableau texte
    table = "```\n"
    table += "┌─────┬────────────────────────┬──────────┬────────┐\n"
    table += "│ N°  │ Participant            │ Makeups │ Points │\n"
    table += "├─────┼────────────────────────┼──────────┼────────┤\n"
    
    for i, (uid, count, points) in enumerate(users_list, 1):
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name if user else f"ID:{uid[:8]}"
        except:
            name = f"ID:{uid[:8]}"
        
        # Tronquer le nom s'il est trop long
        if len(name) > 22:
            name = name[:19] + "..."
        
        # Formater les lignes
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        table += f"│ {medal} {i:2} │ {name:<22} │ {count:8} │ {points:6} │\n"
    
    table += "└─────┴────────────────────────┴──────────┴────────┘\n"
    table += f"\n📊 Total : {len(users_list)} participant(s) | {sum(p[1] for p in users_list)} makeups"
    table += "```"
    
    embed.description += table
    
    # Ajouter une petite légende
    embed.set_footer(text="🏅 Top 3 médaillés | Les points sont calculés : 1er = 1pt, puis 1pt tous les 3 makeups")
    
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
              "`!reset_member_xp @membre` - Réinitialiser un membre\n"
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
