import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import json
import os
import sys

# --- Configuration ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

# --- Fichiers ---
DATA_FILE = 'makeup_data.json'
SCHEDULED_FILE = 'scheduled.json'
CHALLENGES_FILE = 'challenges.json'

# --- Données des makeups ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

data = load_data()

# --- Données des annonces programmées ---
def load_scheduled():
    if os.path.exists(SCHEDULED_FILE):
        with open(SCHEDULED_FILE, 'r') as f:
            return json.load(f)
    return []

def save_scheduled(data):
    with open(SCHEDULED_FILE, 'w') as f:
        json.dump(data, f, indent=4)

scheduled_data = load_scheduled()

# --- Données des défis ---
def load_challenges():
    if os.path.exists(CHALLENGES_FILE):
        with open(CHALLENGES_FILE, 'r') as f:
            return json.load(f)
    return []

def save_challenges(challenges):
    with open(CHALLENGES_FILE, 'w') as f:
        json.dump(challenges, f, indent=4)

challenges = load_challenges()

# --- Fonctions utilitaires ---
def get_current_month():
    return datetime.now().strftime("%Y-%m")

def calculate_points(count):
    if count == 0:
        return 0
    return 1 + (count - 1) // 3

def get_active_challenge():
    """Retourne le défi actif en fonction de la date du jour"""
    today = datetime.now().date()
    for ch in challenges:
        start = datetime.strptime(ch["start_date"], "%Y-%m-%d").date()
        end = datetime.strptime(ch["end_date"], "%Y-%m-%d").date()
        if start <= today <= end:
            return ch
    return None

# --- Constantes des salons ---
MAKEUP_CHANNEL_NAME = "makeups"
REPORT_CHANNEL_NAME = "botlxp"
ANNOUNCE_CHANNEL_ID = 1380938525599338506  # Remplace par l'ID de ton salon #annonces

# --- Vérification d'image ---
def message_has_image(message):
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

# --- Événements ---
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
    check_scheduled_messages.start()
    check_challenge_expiry.start()

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

        # Initialisation avec bonus
        if user_id not in data:
            data[user_id] = {"count": 0, "month": current_month, "bonus_points": 0}
        if data[user_id]["month"] != current_month:
            data[user_id] = {"count": 0, "month": current_month, "bonus_points": 0}
            save_data(data)

        data[user_id]["count"] += 1
        new_count = data[user_id]["count"]
        old_points = calculate_points(new_count - 1) + data[user_id].get("bonus_points", 0)
        new_points = calculate_points(new_count) + data[user_id].get("bonus_points", 0)
        save_data(data)

        # Réactions automatiques
        await message.add_reaction("❤️")
        await message.add_reaction("🔥")
        await message.add_reaction("🎨")

        # Bonus de défi
        active_challenge = get_active_challenge()
        if active_challenge:
            theme = active_challenge["theme"].lower()
            if theme in message.content.lower():
                # Vérifier que le bonus n'a pas déjà été donné pour ce défi ce mois-ci (optionnel)
                bonus_key = f"bonus_challenge_{active_challenge['id']}"
                if bonus_key not in data[user_id]:
                    data[user_id][bonus_key] = 0
                if data[user_id][bonus_key] == 0:  # Une seule fois par défi
                    data[user_id]["bonus_points"] += active_challenge["bonus"]
                    data[user_id][bonus_key] = 1
                    save_data(data)
                    await message.channel.send(
                        f"{message.author.mention} a participé au défi **{active_challenge['theme']}** ! +{active_challenge['bonus']} point bonus 🎉"
                    )

        # Message de gain de point
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

# --- Rapport mensuel ---
async def send_monthly_report(month):
    participants = []
    for uid, info in data.items():
        if info.get("month") == month and info.get("count", 0) > 0:
            count = info["count"]
            points = calculate_points(count) + info.get("bonus_points", 0)
            participants.append((uid, count, points))

    if not participants:
        return

    participants.sort(key=lambda x: x[2], reverse=True)

    report_channel = None
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name == REPORT_CHANNEL_NAME:
                report_channel = channel
                break
        if report_channel:
            break

    if not report_channel:
        print(f"❌ Salon '{REPORT_CHANNEL_NAME}' introuvable pour le bilan mensuel.")
        return

    total_makeups = sum(p[1] for p in participants)
    total_points = sum(p[2] for p in participants)

    embed = discord.Embed(
        title=f"📊 BILAN MENSUEL - {month}",
        description=f"Voici le récapitulatif du mois de **{month}** !",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="📈 RÉSUMÉ",
        value=f"**👥 Participants :** {len(participants)}\n"
              f"**📸 Makeups :** {total_makeups}\n"
              f"**⭐ Points :** {total_points}",
        inline=False
    )

    ranking = ""
    for i, (uid, count, points) in enumerate(participants[:25], 1):
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name if user else f"ID:{uid[:8]}"
        except:
            name = f"ID:{uid[:8]}"
        medal = "🥇 " if i == 1 else "🥈 " if i == 2 else "🥉 " if i == 3 else ""
        ranking += f"{medal}**{i}.** {name} – **{points}** pt(s) ({count} makeup(s))\n"
    if len(participants) > 25:
        ranking += f"\n*... et {len(participants) - 25} autres participants*"

    embed.add_field(name="🏆 CLASSEMENT", value=ranking or "Aucun participant", inline=False)
    await report_channel.send(embed=embed)
    print(f"📊 Bilan mensuel envoyé dans #{REPORT_CHANNEL_NAME}")

@tasks.loop(hours=24)
async def check_new_month():
    current_month = get_current_month()
    previous_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    has_old_data = any(info.get("month") == previous_month for info in data.values())
    if has_old_data:
        await send_monthly_report(previous_month)

    changed = False
    for uid, info in data.items():
        if info["month"] != current_month:
            info["count"] = 0
            info["month"] = current_month
            info["bonus_points"] = 0
            # Nettoyer les anciens marqueurs de défis
            for key in list(info.keys()):
                if key.startswith("bonus_challenge_"):
                    del info[key]
            changed = True
    if changed:
        save_data(data)
        print(f"📅 Nouveau mois détecté : {current_month} - Compteurs réinitialisés")

# --- Annonces programmées ---
@tasks.loop(minutes=1)
async def check_scheduled_messages():
    now = datetime.now()
    current_weekday = now.weekday()
    current_hour = now.hour
    current_minute = now.minute
    today_str = now.strftime("%Y-%m-%d")

    for schedule in scheduled_data:
        try:
            if (schedule["day"] == current_weekday and
                schedule["hour"] == current_hour and
                schedule["minute"] == current_minute):
                last_sent = schedule.get("last_sent", "")
                if last_sent == today_str:
                    continue
                channel = bot.get_channel(schedule["channel_id"])
                if channel:
                    await channel.send(schedule["message"])
                    schedule["last_sent"] = today_str
                    save_scheduled(scheduled_data)
                    print(f"📢 Annonce programmée envoyée dans #{channel.name}")
        except Exception as e:
            print(f"Erreur dans check_scheduled_messages: {e}")
@tasks.loop(hours=1)
async def check_challenge_expiry():
    """Vérifie toutes les heures si un nouveau défi commence et envoie une annonce."""
    today = datetime.now().date()
    # On parcourt les défis pour trouver ceux qui commencent aujourd'hui
    for ch in challenges:
        start_date = datetime.strptime(ch["start_date"], "%Y-%m-%d").date()
        if start_date == today:
            # Vérifier qu'on n'a pas déjà envoyé l'annonce (optionnel)
            if not ch.get("announced", False):
                channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(
                        title="🎉 NOUVEAU DÉFI !",
                        description=f"**{ch['theme']}**\n{ch['description']}",
                        color=discord.Color.purple(),
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="📅 Dates", value=f"Du {ch['start_date']} au {ch['end_date']}", inline=False)
                    embed.add_field(name="🎁 Bonus", value=f"{ch['bonus']} point supplémentaire par participation !", inline=False)
                    embed.set_footer(text="Participez en postant une photo avec le thème dans #makeups")
                    await channel.send(embed=embed)
                    # Marquer comme annoncé pour ne pas le répéter
                    ch["announced"] = True
                    save_challenges(challenges)

# --- Commandes admin ---
@bot.command()
@commands.has_permissions(administrator=True)
async def reset_xp(ctx, member: discord.Member = None):
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
                data[uid] = {"count": 0, "month": current_month, "bonus_points": 0}
                save_data(data)
                await ctx.send(f"✅ Points de {member.display_name} réinitialisés !")
            else:
                await ctx.send(f"❌ {member.display_name} n'a aucun point enregistré.")
        else:
            current_month = get_current_month()
            for uid in data:
                data[uid] = {"count": 0, "month": current_month, "bonus_points": 0}
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
    uid = str(member.id)
    if uid in data:
        current_month = get_current_month()
        data[uid] = {"count": 0, "month": current_month, "bonus_points": 0}
        save_data(data)
        await ctx.send(f"✅ Points de {member.display_name} réinitialisés !")
    else:
        await ctx.send(f"❌ {member.display_name} n'a aucun point enregistré.")

@bot.command()
@commands.has_permissions(administrator=True)
async def set_xp(ctx, member: discord.Member, count: int):
    if count < 0:
        await ctx.send("❌ Le nombre de makeups ne peut pas être négatif.")
        return
    uid = str(member.id)
    current_month = get_current_month()
    if uid not in data:
        data[uid] = {"count": 0, "month": current_month, "bonus_points": 0}
    data[uid]["count"] = count
    data[uid]["month"] = current_month
    save_data(data)
    points = calculate_points(count) + data[uid].get("bonus_points", 0)
    await ctx.send(f"✅ {member.display_name} a maintenant **{count}** makeups ce mois-ci ({points} points LXP).")

# --- Commandes utilisateurs ---
@bot.command()
async def points(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author
    uid = str(member.id)
    current_month = get_current_month()
    if uid in data and data[uid]["month"] == current_month:
        count = data[uid]["count"]
        base_points = calculate_points(count)
        bonus = data[uid].get("bonus_points", 0)
        total_points = base_points + bonus
        embed = discord.Embed(
            title=f"📊 Points LXP de {member.display_name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="⭐ Points", value=f"**{total_points}**", inline=True)
        embed.add_field(name="📸 Makeups", value=f"{count}", inline=True)
        if bonus > 0:
            embed.add_field(name="✨ Bonus", value=f"{bonus}", inline=True)
        if count > 0:
            remaining = 3 - ((count - 1) % 3)
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
            count = info["count"]
            points = calculate_points(count) + info.get("bonus_points", 0)
            if points > 0:
                users_points.append((uid, points, count))
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
                points = calculate_points(count) + info.get("bonus_points", 0)
                total_points += points
                if points > best_member_points:
                    best_member_points = points
                    best_member_count = count
                    try:
                        user = await bot.fetch_user(int(uid))
                        best_member_name = user.display_name if user else "Inconnu"
                    except:
                        best_member_name = "Inconnu"
    embed = discord.Embed(title="📊 STATISTIQUES DU MOIS", color=discord.Color.green(), timestamp=datetime.now())
    embed.add_field(name="📸 Total makeups", value=f"**{total_makeups}**", inline=True)
    embed.add_field(name="⭐ Total points", value=f"**{total_points}**", inline=True)
    embed.add_field(name="👥 Membres actifs", value=f"**{active_members}**", inline=True)
    if best_member_name and best_member_points > 0:
        embed.add_field(name="🏆 Meilleur membre du mois", value=f"{best_member_name}\n**{best_member_points}** points ({best_member_count} makeups)", inline=False)
    if active_members > 0:
        avg_makeups = round(total_makeups / active_members, 1)
        embed.add_field(name="📊 Moyenne par membre", value=f"{avg_makeups} makeups", inline=True)
    embed.add_field(name="📅 Mois", value=f"**{current_month}**", inline=True)
    embed.set_footer(text="Continuez à poster vos makeups ! 🎨")
    await ctx.send(embed=embed)

@bot.command()
async def participants(ctx):
    current_month = get_current_month()
    users_list = []
    for uid, info in data.items():
        if info.get("month") == current_month:
            count = info.get("count", 0)
            if count > 0:
                points = calculate_points(count) + info.get("bonus_points", 0)
                users_list.append((uid, count, points))
    users_list.sort(key=lambda x: x[2], reverse=True)
    if not users_list:
        await ctx.send("📭 **Aucun participant ce mois-ci.**\n\nPostez des makeups dans #makeups pour apparaître dans le tableau !")
        return
    embed = discord.Embed(title="📋 TABLEAU DES PARTICIPANTS", description=f"**Mois : {current_month}**\n\nVoici tous les membres qui ont participé ce mois-ci :", color=discord.Color.blue())
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
        if len(name) > 22:
            name = name[:19] + "..."
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        table += f"│ {medal} {i:2} │ {name:<22} │ {count:8} │ {points:6} │\n"
    table += "└─────┴────────────────────────┴──────────┴────────┘\n"
    table += f"\n📊 Total : {len(users_list)} participant(s) | {sum(p[1] for p in users_list)} makeups"
    table += "```"
    embed.description += table
    embed.set_footer(text="🏅 Top 3 médaillés | Les points sont calculés : 1er = 1pt, puis 1pt tous les 3 makeups")
    await ctx.send(embed=embed)

@bot.command()
async def help_points(ctx):
    embed = discord.Embed(title="🎨 AIDE DU BOT MMULXP", description="Petit robot crée par Karys, la Présidente ! ", color=discord.Color.purple())
    embed.add_field(
        name="📸 COMMENT GAGNER DES POINTS ?",
        value=f"Postez une **photo de makeup** dans #{MAKEUP_CHANNEL_NAME}\n"
              "• 1er makeup du mois → **1 point**\n"
              "• Puis **1 point** tous les **3 makeups**\n"
              "• Les compteurs se réinitialisent chaque **mois** donc attention aux délais !",
        inline=False
    )
    embed.add_field(
        name="🎯 DÉFIS HEBDOMADAIRES",
        value="Participez aux défis thématiques pour gagner **1 point bonus** par défi !\n"
              "`!defi list` - Voir les défis en cours, à venir et terminés\n\n"
              "**Commandes admin :**\n"
              "`!defi add \"thème\" \"description\" durée` - Créer un nouveau défi\n"
              "`!defi remove <id>` - Supprimer un défi",
        inline=False
    )
    embed.add_field(
        name="💬 COMMANDES",
        value="`!points` - Voir vos points\n"
              "`!points @membre` - Voir les points d'un membre\n"
              "`!leaderboard` - Voir le classement\n"
              "`!stats` - Statistiques du mois\n"
              "`!participants` - Liste de tous les participants\n"
              "`!help_points` - Afficher cette aide\n\n"
              "**Commandes admin :**\n"
              "`!reset_xp` - Réinitialiser tous les points\n"
              "`!reset_member_xp @membre` - Réinitialiser un membre\n"
              "`!set_xp @membre nombre` - Définir le nombre de makeups\n"
              "`!planifier` - Gérer les annonces programmées (add/list/remove)",
        inline=False
    )
    embed.set_footer(text="Bonne chance et faites de beaux makeups ! ✨")
    await ctx.send(embed=embed)

# --- Commandes planification (inchangées) ---
@bot.command()
@commands.has_permissions(administrator=True)
async def planifier(ctx, action, *, args=None):
    global scheduled_data
    if action == "add":
        parts = args.split(' ', 3)
        if len(parts) < 4:
            await ctx.send("❌ Format : !planifier add #salon lundi 18:00 \"Message\"")
            return
        channel_mention = parts[0]
        day_name = parts[1].lower()
        hour_min = parts[2]
        message = parts[3].strip('"')
        if not channel_mention.startswith('<#') or not channel_mention.endswith('>'):
            await ctx.send("❌ Mentionne un salon valide (ex: #annonces)")
            return
        channel_id = int(channel_mention[2:-1])
        days = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6}
        if day_name not in days:
            await ctx.send("❌ Jour invalide. Utilise : lundi, mardi, mercredi, jeudi, vendredi, samedi, dimanche")
            return
        day = days[day_name]
        try:
            hour, minute = map(int, hour_min.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except:
            await ctx.send("❌ Heure invalide. Format : HH:MM (ex: 18:00)")
            return
        new_schedule = {
            "id": len(scheduled_data) + 1,
            "channel_id": channel_id,
            "day": day,
            "hour": hour,
            "minute": minute,
            "message": message,
            "last_sent": ""
        }
        scheduled_data.append(new_schedule)
        save_scheduled(scheduled_data)
        await ctx.send(f"✅ Annonce programmée : tous les {day_name} à {hour:02d}:{minute:02d} dans <#{channel_id}>.")

    elif action == "list":
        if not scheduled_data:
            await ctx.send("📭 Aucune annonce programmée.")
            return
        description = ""
        day_names = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        for s in scheduled_data:
            day_name = day_names[s["day"]]
            description += f"**ID {s['id']}** : {day_name} {s['hour']:02d}:{s['minute']:02d} → <#{s['channel_id']}> : {s['message'][:50]}...\n"
        embed = discord.Embed(title="📅 Annonces programmées", description=description, color=discord.Color.blue())
        await ctx.send(embed=embed)

    elif action == "remove":
        try:
            id_to_remove = int(args)
            new_list = [s for s in scheduled_data if s["id"] != id_to_remove]
            if len(new_list) == len(scheduled_data):
                await ctx.send(f"❌ Aucune annonce avec l'ID {id_to_remove}.")
                return
            scheduled_data = new_list
            save_scheduled(scheduled_data)
            await ctx.send(f"✅ Annonce ID {id_to_remove} supprimée.")
        except:
            await ctx.send("❌ Utilisation : !planifier remove <id>")

    else:
        await ctx.send("❌ Action inconnue. Utilise : add, list, remove")
# --- Commandes défis ---
@bot.command()
@commands.has_permissions(administrator=True)
async def defi(ctx, action, *, args=None):
    global challenges
    if action == "add":
        import re
        parts = re.findall(r'"([^"]*)"', args)
        if len(parts) < 2:
            await ctx.send("❌ Format : !defi add \"thème\" \"description\" durée")
            return
        theme = parts[0]
        description = parts[1]
        remaining = args.replace(f'"{theme}"', "").replace(f'"{description}"', "").strip()
        try:
            duration = int(remaining)
        except:
            await ctx.send("❌ La durée doit être un nombre de jours.")
            return
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=duration)
        new_id = max([c["id"] for c in challenges], default=0) + 1
        new_challenge = {
            "id": new_id,
            "theme": theme,
            "description": description,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "bonus": 1
        }
        challenges.append(new_challenge)
        save_challenges(challenges)
        await ctx.send(f"✅ Défi ajouté : **{theme}** du {start_date} au {end_date}.")

    elif action == "list":
        if not challenges:
            await ctx.send("📭 Aucun défi enregistré.")
            return
        embed = discord.Embed(title="📋 Liste des défis", color=discord.Color.blue())
        today = datetime.now().date()
        for c in challenges:
            start = datetime.strptime(c["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(c["end_date"], "%Y-%m-%d").date()
            status = "🟢 actif" if start <= today <= end else "⏳ à venir" if today < start else "🔒 terminé"
            embed.add_field(
                name=f"N°{c['id']} : {c['theme']}",
                value=f"📅 {c['start_date']} → {c['end_date']}\n"
                      f"📝 {c['description']}\n"
                      f"Bonus : {c['bonus']} point\n"
                      f"{status}",
                inline=False
            )
        await ctx.send(embed=embed)

    elif action == "remove":
        try:
            id_to_remove = int(args)
            new_list = [c for c in challenges if c["id"] != id_to_remove]
            if len(new_list) == len(challenges):
                await ctx.send(f"❌ Aucun défi avec l'ID {id_to_remove}.")
                return
            challenges = new_list
            save_challenges(challenges)
            await ctx.send(f"✅ Défi ID {id_to_remove} supprimé.")
        except:
            await ctx.send("❌ Utilisation : !defi remove <id>")

    else:
        await ctx.send("❌ Action inconnue. Utilise : add, list, remove")
# --- Lancement ---
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("❌ Token manquant !")
        sys.exit(1)
    bot.run(TOKEN)
