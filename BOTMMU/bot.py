import discord
from discord.ext import commands, tasks
from datetime import datetime
import json
import os
import sys

# ===== CONFIGURATION =====
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Fichier de sauvegarde
DATA_FILE = 'makeup_data.json'

# ===== CONFIGURATION DES RÉCOMPENSES =====
# Définissez ici les paliers de points et les rôles correspondants
REWARDS = {
    1: {
        "role": "💄 Makeup Apprentice",
        "message": "Bienvenue dans l'aventure makeup ! Continue comme ça ! 🌟"
    },
    5: {
        "role": "✨ Makeup Enthusiast",
        "message": "Tu deviens un(e) vrai(e) passionné(e) de makeup ! 🎨"
    },
    10: {
        "role": "🎨 Makeup Artist",
        "message": "Artiste confirmé(e) ! Tes makeups sont magnifiques ! 🖌️"
    },
    15: {
        "role": "⭐ Makeup Star",
        "message": "Star du makeup ! Tu brilles par ton talent ! ✨"
    },
    20: {
        "role": "👑 Makeup Legend",
        "message": "LÉGENDE ! Tu es une inspiration pour toute l'association ! 👏"
    }
}

# Salon pour les annonces (mettez l'ID du salon, laissez None pour désactiver)
ANNOUNCE_CHANNEL_ID = None  # Exemple: 123456789012345678

# ===== FONCTIONS DE BASE =====
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

# ===== FONCTION DE GESTION DES RÉCOMPENSES =====
async def check_and_give_rewards(member, new_points, channel=None):
    """Vérifie et donne les récompenses basées sur les points"""
    roles_given = []
    rewards_unlocked = []
    
    for points_required, reward_info in REWARDS.items():
        if new_points >= points_required:
            role = discord.utils.get(member.guild.roles, name=reward_info["role"])
            if role and role not in member.roles:
                try:
                    await member.add_roles(role)
                    roles_given.append(role)
                    rewards_unlocked.append({
                        "points": points_required,
                        "role": role,
                        "message": reward_info["message"]
                    })
                    print(f"🏆 {member.name} a obtenu le rôle {role.name} !")
                except discord.Forbidden:
                    print(f"❌ Permission manquante pour donner le rôle {role.name} à {member.name}")
                except Exception as e:
                    print(f"❌ Erreur: {e}")
    
    # Annoncer les nouvelles récompenses
    if rewards_unlocked and ANNOUNCE_CHANNEL_ID:
        announce_channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
        if announce_channel:
            for reward in rewards_unlocked:
                embed = discord.Embed(
                    title="🎉 NOUVELLE RÉCOMPENSE DÉBLOQUÉE ! 🎉",
                    description=f"{member.mention} a atteint **{reward['points']} points** !",
                    color=discord.Color.green()
                )
                embed.add_field(name="🏅 Rôle obtenu", value=reward["role"].mention, inline=False)
                embed.add_field(name="💬 Message", value=reward["message"], inline=False)
                embed.set_footer(text="Continue à partager tes créations !")
                await announce_channel.send(embed=embed)
    
    return roles_given

# ===== ÉVÉNEMENTS =====
@bot.event
async def on_ready():
    print(f"\n{'='*50}")
    print(f"✅ BOT CONNECTÉ AVEC SUCCÈS !")
    print(f"{'='*50}")
    print(f"📊 Nom du bot : {bot.user.name}")
    print(f"🆔 ID du bot : {bot.user.id}")
    print(f"🌍 Connecté à {len(bot.guilds)} serveur(s)")
    
    for guild in bot.guilds:
        print(f"  └─ {guild.name}")
        # Vérifier les rôles existants
        print(f"     Rôles de récompense configurés :")
        for points, reward in REWARDS.items():
            role = discord.utils.get(guild.roles, name=reward["role"])
            if role:
                print(f"       ✅ {reward['role']} ({points} points)")
            else:
                print(f"       ❌ {reward['role']} ({points} points) - Rôle manquant !")
    
    print(f"\n💡 Commandes disponibles :")
    print(f"  !points - Voir vos points")
    print(f"  !leaderboard - Voir le classement")
    print(f"  !rewards - Voir les récompenses disponibles")
    print(f"  !help_points - Aide")
    print(f"{'='*50}\n")
    
    check_new_month.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Trouver le salon makeups (peut être différent selon le serveur)
    makeups_channel = None
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name == "makeups":
                makeups_channel = channel
                break
    
    if makeups_channel and message.channel.id == makeups_channel.id:
        user_id = str(message.author.id)
        current_month = get_current_month()

        # Initialiser ou réinitialiser pour le nouveau mois
        if user_id not in data:
            data[user_id] = {"count": 0, "month": current_month, "points_history": []}
        if data[user_id]["month"] != current_month:
            # Sauvegarder l'historique du mois précédent
            if "points_history" not in data[user_id]:
                data[user_id]["points_history"] = []
            data[user_id]["points_history"].append({
                "month": data[user_id]["month"],
                "count": data[user_id]["count"],
                "points": calculate_points(data[user_id]["count"])
            })
            data[user_id]["count"] = 0
            data[user_id]["month"] = current_month
            save_data(data)

        # Incrémenter le compteur
        data[user_id]["count"] += 1
        new_count = data[user_id]["count"]
        old_points = calculate_points(new_count - 1)
        new_points = calculate_points(new_count)
        save_data(data)

        # Vérifier les récompenses
        if new_points > old_points:
            roles_given = await check_and_give_rewards(message.author, new_points, message.channel)
            
            embed = discord.Embed(
                title="✨ NOUVEAU POINT LXP ! ✨",
                description=f"{message.author.mention} vient de gagner **{new_points} point(s)** !",
                color=discord.Color.gold()
            )
            embed.add_field(name="📸 Makeups postés", value=f"{new_count}", inline=True)
            embed.add_field(name="⭐ Total points", value=f"{new_points}", inline=True)
            
            if roles_given:
                roles_mention = " ".join([role.mention for role in roles_given])
                embed.add_field(name="🎁 Récompenses débloquées", value=roles_mention, inline=False)
            
            embed.set_footer(text="Continue comme ça ! 🎨")
            await message.channel.send(embed=embed)
        else:
            remaining = 3 - ((new_count - 1) % 3)
            await message.channel.send(f"✅ **{message.author.display_name}** - Makeup #{new_count} enregistré ! Prochain point dans **{remaining}** makeup(s).")

    await bot.process_commands(message)

@tasks.loop(hours=24)
async def check_new_month():
    current_month = get_current_month()
    changed = False
    for uid, info in data.items():
        if info["month"] != current_month:
            # Sauvegarder l'historique
            if "points_history" not in info:
                info["points_history"] = []
            info["points_history"].append({
                "month": info["month"],
                "count": info["count"],
                "points": calculate_points(info["count"])
            })
            info["count"] = 0
            info["month"] = current_month
            changed = True
    if changed:
        save_data(data)
        print(f"📅 Nouveau mois détecté : {current_month} - Compteurs réinitialisés")

# ===== COMMANDES =====
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
        embed.add_field(name="⭐ Points LXP", value=f"**{points}**", inline=True)
        embed.add_field(name="📸 Makeups postés", value=f"{count}", inline=True)
        
        # Prochain palier
        next_reward_points = None
        for req_points in sorted(REWARDS.keys()):
            if req_points > points:
                next_reward_points = req_points
                break
        
        if next_reward_points:
            points_needed = next_reward_points - points
            embed.add_field(name="🎯 Prochaine récompense", value=f"{points_needed} point(s) pour {REWARDS[next_reward_points]['role']}", inline=False)
        
        embed.set_footer(text=f"Mois de {current_month}")
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
            count = info["count"]
            points = calculate_points(count)
            if points > 0:
                users_points.append((uid, points, count))
    
    users_points.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(
        title="🏆 CLASSEMENT LXP DU MOIS 🏆",
        color=discord.Color.gold()
    )
    
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
    
    if not description:
        description = "📭 Aucun point ce mois-ci. Soyez le premier à poster un makeup !"
    
    embed.description = description
    embed.set_footer(text=f"Mois de {current_month}")
    await ctx.send(embed=embed)

@bot.command()
async def rewards(ctx):
    """Affiche les récompenses disponibles"""
    embed = discord.Embed(
        title="🎁 RÉCOMPENSES DISPONIBLES",
        description="Gagnez des points LXP pour débloquer des rôles exclusifs !",
        color=discord.Color.purple()
    )
    
    for points, reward in sorted(REWARDS.items()):
        embed.add_field(
            name=f"{reward['role']}",
            value=f"🏆 {points} points requis\n💬 {reward['message']}",
            inline=False
        )
    
    embed.set_footer(text="Postez vos makeups dans #makeups pour gagner des points !")
    await ctx.send(embed=embed)

@bot.command()
async def stats(ctx):
    """Affiche les statistiques du mois"""
    current_month = get_current_month()
    total_makeups = 0
    active_members = 0
    
    for uid, info in data.items():
        if info["month"] == current_month:
            if info["count"] > 0:
                active_members += 1
                total_makeups += info["count"]
    
    embed = discord.Embed(
        title="📊 STATISTIQUES DU MOIS",
        color=discord.Color.green()
    )
    embed.add_field(name="📸 Total makeups", value=f"{total_makeups}", inline=True)
    embed.add_field(name="👥 Membres actifs", value=f"{active_members}", inline=True)
    embed.add_field(name="📅 Mois", value=f"{current_month}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def reset_month(ctx):
    """Réinitialise manuellement le mois (admin uniquement)"""
    current_month = get_current_month()
    for uid in data:
        if "points_history" not in data[uid]:
            data[uid]["points_history"] = []
        data[uid]["points_history"].append({
            "month": data[uid]["month"],
            "count": data[uid]["count"],
            "points": calculate_points(data[uid]["count"])
        })
        data[uid]["count"] = 0
        data[uid]["month"] = current_month
    save_data(data)
    await ctx.send("🔄 Les compteurs ont été réinitialisés pour le nouveau mois !")
    print(f"🔄 Réinitialisation manuelle effectuée par {ctx.author.name}")

@bot.command()
@commands.has_permissions(administrator=True)
async def set_announce_channel(ctx, channel: discord.TextChannel = None):
    """Définit le salon d'annonces (admin uniquement)"""
    global ANNOUNCE_CHANNEL_ID
    if channel:
        ANNOUNCE_CHANNEL_ID = channel.id
        await ctx.send(f"✅ Salon d'annonces configuré : {channel.mention}")
    else:
        ANNOUNCE_CHANNEL_ID = None
        await ctx.send(f"✅ Salon d'annonces désactivé")

@bot.command()
async def help_points(ctx):
    """Affiche l'aide du bot"""
    embed = discord.Embed(
        title="🎨 AIDE DU BOT MAKEUP POINTS",
        description="Système de points et récompenses pour votre association !",
        color=discord.Color.purple()
    )
    embed.add_field(
        name="📝 COMMENT GAGNER DES POINTS ?",
        value="Postez vos photos de makeup dans **#makeups**\n"
              "• **1er** makeup du mois → **1 point**\n"
              "• Puis **1 point** tous les **3 makeups**\n"
              "• Les compteurs se réinitialisent chaque **mois**",
        inline=False
    )
    embed.add_field(
        name="🎁 RÉCOMPENSES",
        value="Débloquez des rôles exclusifs en accumulant des points !\n"
              "Utilisez `!rewards` pour voir tous les paliers",
        inline=False
    )
    embed.add_field(
        name="💬 COMMANDES",
        value="`!points` - Voir vos points\n"
              "`!points @membre` - Voir les points d'un membre\n"
              "`!leaderboard` - Voir le classement\n"
              "`!rewards` - Voir les récompenses\n"
              "`!stats` - Statistiques du mois\n"
              "`!help_points` - Afficher cette aide",
        inline=False
    )
    embed.set_footer(text="Bonne chance et faites de beaux makeups ! ✨")
    await ctx.send(embed=embed)

# ===== LANCEMENT =====
if __name__ == "__main__":
    TOKEN = "MTQ4NDUyMTAxOTQwNTM3MzUwMA.GJ_o-X.4mNUJX_IOnmPoEeL2D7wrtzwaqgC7itLHpgu8"  # Remplacez par votre token
    
    if TOKEN == "MTQ4NDUyMTAxOTQwNTM3MzUwMA.GJ_o-X.4mNUJX_IOnmPoEeL2D7wrtzwaqgC7itLHpgu8":
        print("\n❌ ERREUR: Token Discord non configuré !\n")
        sys.exit(1)
    
    try:
        print("\n🚀 Démarrage du bot...")
        bot.run(TOKEN)
    except Exception as e:
        print(f"\n❌ ERREUR: {e}\n")