import discord
from discord.ext import commands, tasks
import json
import os
import asyncio
import random
import string
import datetime
import aiohttp

# ─────────────────────────────────────────
#  CONFIG — MODIFIE CES VALEURS
# ─────────────────────────────────────────
TOKEN = os.environ.get("TOKEN", "TON_TOKEN_ICI")
PREFIX = "!"
OWNER_ID = 1220240949574107170

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# ─────────────────────────────────────────
#  SETUP
# ─────────────────────────────────────────
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

join_tracker = {}

# ─────────────────────────────────────────
#  DATA
# ─────────────────────────────────────────
def load(file):
    path = f"{DATA_DIR}/{file}.json"
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def save(file, data):
    with open(f"{DATA_DIR}/{file}.json", "w") as f:
        json.dump(data, f, indent=2)

# ─────────────────────────────────────────
#  SYSTÈME DE LICENCE
# ─────────────────────────────────────────
def generate_key():
    parts = [''.join(random.choices(string.ascii_uppercase + string.digits, k=5)) for _ in range(4)]
    return '-'.join(parts)

def is_licensed(guild_id):
    licenses = load("licenses")
    entry = licenses.get(str(guild_id))
    return entry is not None and entry.get("active", False)

def get_guild_owner_id(guild_id):
    licenses = load("licenses")
    return licenses.get(str(guild_id), {}).get("owner_id")

def is_guild_owner(ctx):
    return ctx.author.id == get_guild_owner_id(ctx.guild.id) or ctx.author.id == OWNER_ID

async def check_license(ctx):
    if ctx.author.id == OWNER_ID:
        return True
    if not is_licensed(ctx.guild.id):
        embed = discord.Embed(
            title="🔒 Bot non activé",
            description=(
                "Ce bot n'est pas encore activé sur ce serveur.\n\n"
                "**Comment obtenir une licence ?**\n"
                "Contacte le développeur pour acheter une clé.\n\n"
                "**Déjà une clé ?**\n"
                f"`{PREFIX}activer XXXX-XXXX-XXXX-XXXX`"
            ),
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return False
    return True

# ─────────────────────────────────────────
#  EVENTS DE BASE
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ {bot.user} connecté !")
    print(f"📊 {len(bot.guilds)} serveur(s)")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}aide | Bot Premium"))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 Tu n'as pas la permission de faire ça.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membre introuvable.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Argument invalide.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Erreur : {error}")

# ─────────────────────────────────────────
#  COMMANDES OWNER ULTIME
# ─────────────────────────────────────────

@bot.command(name="genkey")
async def genkey(ctx, membre: discord.Member = None):
    """Génère une clé de licence et l'envoie en MP. (Owner ultime)"""
    if ctx.author.id != OWNER_ID:
        return await ctx.send("🚫 Accès refusé.")

    key = generate_key()
    keys = load("pending_keys")
    keys[key] = {
        "created_at": datetime.datetime.utcnow().isoformat(),
        "used": False,
        "created_for": str(membre.id) if membre else None
    }
    save("pending_keys", keys)

    embed_key = discord.Embed(
        title="🔑 Votre clé de licence — Bot Premium",
        color=discord.Color.gold()
    )
    embed_key.add_field(name="🗝️ Clé d'activation", value=f"```{key}```", inline=False)
    embed_key.add_field(
        name="📋 Comment activer ?",
        value=f"Sur votre serveur Discord, tapez :\n```{PREFIX}activer {key}```",
        inline=False
    )
    embed_key.add_field(
        name="⚠️ Important",
        value="• Ne partagez pas cette clé\n• Usage unique\n• Liée à votre serveur",
        inline=False
    )
    embed_key.set_footer(text="Merci pour votre achat !")

    if membre:
        try:
            await membre.send(embed=embed_key)
            await ctx.send(f"✅ Clé `{key}` générée et envoyée en MP à {membre.mention} !")
        except discord.Forbidden:
            await ctx.send(f"✅ Clé générée : `{key}`\n⚠️ Impossible d'envoyer en MP à {membre.mention} (MPs fermés).")
    else:
        await ctx.send(embed=embed_key)


@bot.command(name="revokekey")
async def revokekey(ctx, guild_id: int):
    """Révoque la licence d'un serveur. (Owner ultime)"""
    if ctx.author.id != OWNER_ID:
        return await ctx.send("🚫 Accès refusé.")
    licenses = load("licenses")
    if str(guild_id) not in licenses:
        return await ctx.send("❌ Aucune licence trouvée.")
    licenses[str(guild_id)]["active"] = False
    save("licenses", licenses)
    await ctx.send(f"✅ Licence révoquée pour `{guild_id}`.")


@bot.command(name="listlicenses")
async def listlicenses(ctx):
    """Liste toutes les licences. (Owner ultime)"""
    if ctx.author.id != OWNER_ID:
        return await ctx.send("🚫 Accès refusé.")
    licenses = load("licenses")
    if not licenses:
        return await ctx.send("📭 Aucune licence.")
    embed = discord.Embed(title="📋 Licences", color=discord.Color.blurple())
    desc = ""
    for gid, info in licenses.items():
        guild = bot.get_guild(int(gid))
        nom = guild.name if guild else f"Serveur {gid}"
        status = "✅" if info.get("active") else "❌"
        desc += f"{status} **{nom}** — Owner : <@{info.get('owner_id')}>\n"
    embed.description = desc
    await ctx.send(embed=embed)


# ─────────────────────────────────────────
#  ACTIVATION
# ─────────────────────────────────────────

@bot.command(name="activer")
@commands.has_permissions(administrator=True)
async def activer(ctx, key: str):
    """Active le bot avec une clé de licence."""
    keys = load("pending_keys")
    licenses = load("licenses")

    # Vérifie la clé
    if key not in keys:
        return await ctx.send("❌ Clé invalide. Vérifie ta clé et réessaie.")
    if keys[key].get("used"):
        return await ctx.send("❌ Cette clé a déjà été utilisée.")
    if is_licensed(ctx.guild.id):
        return await ctx.send("✅ Ce serveur est déjà activé !")

    # Active
    keys[key]["used"] = True
    keys[key]["used_by"] = str(ctx.author.id)
    keys[key]["used_at"] = datetime.datetime.utcnow().isoformat()
    save("pending_keys", keys)

    licenses[str(ctx.guild.id)] = {
        "active": True,
        "owner_id": ctx.author.id,
        "activated_at": datetime.datetime.utcnow().isoformat(),
        "key": key,
        "guild_name": ctx.guild.name
    }
    save("licenses", licenses)

    embed = discord.Embed(
        title="✅ Bot activé avec succès !",
        description=(
            f"**{ctx.guild.name}** est maintenant premium ! 🎉\n\n"
            f"Tape `{PREFIX}aide` pour voir toutes les commandes.\n\n"
            f"Tu es l'**owner** de ce bot sur ce serveur.\n"
            f"Tu peux personnaliser le bot avec `{PREFIX}setname`, `{PREFIX}setavatar`, etc."
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Activé par {ctx.author.display_name}")
    await ctx.send(embed=embed)

    # Notifie l'owner ultime
    try:
        owner = await bot.fetch_user(OWNER_ID)
        notif = discord.Embed(
            title="🔑 Nouvelle activation !",
            color=discord.Color.green()
        )
        notif.add_field(name="Serveur", value=f"{ctx.guild.name} (`{ctx.guild.id}`)", inline=False)
        notif.add_field(name="Activé par", value=f"{ctx.author} (`{ctx.author.id}`)", inline=False)
        notif.add_field(name="Clé utilisée", value=f"`{key}`", inline=False)
        await owner.send(embed=notif)
    except:
        pass


# ─────────────────────────────────────────
#  PERSONNALISATION DU BOT (owner du serv)
# ─────────────────────────────────────────

@bot.command(name="setname")
async def setname(ctx, *, nom: str):
    """Change le nom du bot. (Owner du serveur uniquement)"""
    if not await check_license(ctx): return
    if not is_guild_owner(ctx):
        return await ctx.send("🚫 Seul l'owner de la licence peut faire ça.")
    try:
        await bot.user.edit(username=nom)
        await ctx.send(f"✅ Nom du bot changé en **{nom}** !")
    except discord.HTTPException as e:
        await ctx.send(f"❌ Erreur : {e}\n⚠️ Discord limite les changements de nom à 2 fois par heure.")


@bot.command(name="setavatar")
async def setavatar(ctx, url: str = None):
    """Change l'avatar du bot. (Owner du serveur uniquement)\nUsage : !setavatar <url> ou envoie une image en pièce jointe"""
    if not await check_license(ctx): return
    if not is_guild_owner(ctx):
        return await ctx.send("🚫 Seul l'owner de la licence peut faire ça.")

    # Récupère l'image depuis l'URL ou la pièce jointe
    image_url = url
    if not image_url and ctx.message.attachments:
        image_url = ctx.message.attachments[0].url

    if not image_url:
        return await ctx.send("❌ Envoie une URL d'image ou une pièce jointe.")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    return await ctx.send("❌ Impossible de récupérer l'image.")
                image_data = await resp.read()
        await bot.user.edit(avatar=image_data)
        await ctx.send("✅ Avatar du bot mis à jour !")
    except discord.HTTPException as e:
        await ctx.send(f"❌ Erreur : {e}")


@bot.command(name="setstatus")
async def setstatus(ctx, type_status: str, *, texte: str):
    """Change le statut du bot. (Owner du serveur)\nTypes : joue, regarde, ecoute, stream"""
    if not await check_license(ctx): return
    if not is_guild_owner(ctx):
        return await ctx.send("🚫 Seul l'owner de la licence peut faire ça.")

    types = {
        "joue": discord.ActivityType.playing,
        "regarde": discord.ActivityType.watching,
        "ecoute": discord.ActivityType.listening,
        "stream": discord.ActivityType.streaming
    }
    if type_status.lower() not in types:
        return await ctx.send("❌ Types disponibles : `joue`, `regarde`, `ecoute`, `stream`")

    activity = discord.Activity(type=types[type_status.lower()], name=texte)
    await bot.change_presence(activity=activity)
    await ctx.send(f"✅ Statut mis à jour : **{type_status} {texte}**")


@bot.command(name="setbanniere")
async def setbanniere(ctx, url: str = None):
    """Définit un GIF/image comme bannière du profil bot. (Owner)\nUsage : !setbanniere <url gif/image>"""
    if not await check_license(ctx): return
    if not is_guild_owner(ctx):
        return await ctx.send("🚫 Seul l'owner de la licence peut faire ça.")

    image_url = url
    if not image_url and ctx.message.attachments:
        image_url = ctx.message.attachments[0].url
    if not image_url:
        return await ctx.send("❌ Envoie une URL de GIF/image ou une pièce jointe.")

    # Sauvegarde la bannière dans la config
    config = load("config")
    guild_id = str(ctx.guild.id)
    if guild_id not in config: config[guild_id] = {}
    config[guild_id]["banniere_url"] = image_url
    save("config", config)

    embed = discord.Embed(
        title="🖼️ Bannière mise à jour !",
        description="La bannière a été enregistrée.\n\n⚠️ Note : Discord ne permet pas de changer la bannière du bot via l'API. Elle sera affichée dans les embeds du bot sur ce serveur.",
        color=discord.Color.blurple()
    )
    embed.set_image(url=image_url)
    await ctx.send(embed=embed)


@bot.command(name="setprefix")
@commands.has_permissions(administrator=True)
async def setprefix(ctx, nouveau_prefix: str):
    """Change le préfixe du bot sur ce serveur."""
    if not await check_license(ctx): return
    if not is_guild_owner(ctx):
        return await ctx.send("🚫 Seul l'owner de la licence peut faire ça.")
    config = load("config")
    guild_id = str(ctx.guild.id)
    if guild_id not in config: config[guild_id] = {}
    config[guild_id]["prefix"] = nouveau_prefix
    save("config", config)
    await ctx.send(f"✅ Préfixe changé en **{nouveau_prefix}**")


# ─────────────────────────────────────────
#  AIDE
# ─────────────────────────────────────────

@bot.command(name="aide")
async def aide(ctx):
    if not await check_license(ctx): return
    config = load("config")
    banniere = config.get(str(ctx.guild.id), {}).get("banniere_url")

    embed = discord.Embed(
        title="📖 Aide — Bot Premium",
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.utcnow()
    )
    if banniere:
        embed.set_image(url=banniere)

    embed.add_field(name="🔨 Modération", value="`!kick` `!ban` `!unban` `!mute` `!unmute` `!warn` `!warnings` `!clearwarns` `!clear` `!lockdown` `!unlock`", inline=False)
    embed.add_field(name="⭐ Niveaux XP", value="`!rank` `!rank @user` `!topxp` `!setlevelrole`", inline=False)
    embed.add_field(name="🎟️ Tickets", value="`!setticket` `!closeticket`", inline=False)
    embed.add_field(name="🛡️ Sécurité", value="`!antiraid on/off` `!antispam on/off`", inline=False)
    embed.add_field(name="📋 Logs", value="`!setlogs #salon`", inline=False)
    embed.add_field(name="👋 Bienvenue", value="`!setwelcome #salon [message]` `!setbye #salon`", inline=False)
    embed.add_field(name="🎉 Giveaway", value="`!gcreate <minutes> <lot>` `!gend <msg_id>` `!greroll <msg_id>`", inline=False)
    embed.add_field(name="🎨 Personnalisation", value="`!setname` `!setavatar` `!setstatus` `!setbanniere` `!setprefix`", inline=False)
    embed.add_field(name="ℹ️ Infos", value="`!userinfo` `!serverinfo` `!ping`", inline=False)
    embed.set_footer(text=f"Prefix : {PREFIX} | Bot Premium")
    await ctx.send(embed=embed)


@bot.command(name="ping")
async def ping(ctx):
    if not await check_license(ctx): return
    await ctx.send(f"🏓 Pong ! `{round(bot.latency * 1000)}ms`")


@bot.command(name="userinfo")
async def userinfo(ctx, membre: discord.Member = None):
    if not await check_license(ctx): return
    membre = membre or ctx.author
    roles = [r.mention for r in membre.roles if r.name != "@everyone"]
    embed = discord.Embed(title=f"👤 {membre.display_name}", color=membre.color or discord.Color.blurple())
    embed.set_thumbnail(url=membre.display_avatar.url)
    embed.add_field(name="🆔 ID", value=membre.id, inline=True)
    embed.add_field(name="📅 Rejoint", value=membre.joined_at.strftime("%d/%m/%Y") if membre.joined_at else "?", inline=True)
    embed.add_field(name="🎂 Créé", value=membre.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name=f"🎭 Rôles ({len(roles)})", value=", ".join(roles) if roles else "Aucun", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="serverinfo")
async def serverinfo(ctx):
    if not await check_license(ctx): return
    g = ctx.guild
    embed = discord.Embed(title=f"🌐 {g.name}", color=discord.Color.blurple())
    if g.icon: embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="👑 Owner", value=g.owner.mention, inline=True)
    embed.add_field(name="👥 Membres", value=g.member_count, inline=True)
    embed.add_field(name="💬 Salons", value=len(g.channels), inline=True)
    embed.add_field(name="🎭 Rôles", value=len(g.roles), inline=True)
    embed.add_field(name="📅 Créé", value=g.created_at.strftime("%d/%m/%Y"), inline=True)
    await ctx.send(embed=embed)


# ─────────────────────────────────────────
#  MODÉRATION
# ─────────────────────────────────────────

async def log_action(guild, message):
    config = load("config")
    logs_id = config.get(str(guild.id), {}).get("logs_channel")
    if logs_id:
        ch = guild.get_channel(int(logs_id))
        if ch:
            embed = discord.Embed(description=message, color=discord.Color.orange(), timestamp=datetime.datetime.utcnow())
            await ch.send(embed=embed)

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, membre: discord.Member, *, raison="Aucune raison"):
    if not await check_license(ctx): return
    await membre.kick(reason=raison)
    await ctx.send(f"👢 **{membre}** kické. Raison : {raison}")
    await log_action(ctx.guild, f"👢 **Kick** | {membre} par {ctx.author} | {raison}")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, membre: discord.Member, *, raison="Aucune raison"):
    if not await check_license(ctx): return
    await membre.ban(reason=raison)
    await ctx.send(f"🔨 **{membre}** banni. Raison : {raison}")
    await log_action(ctx.guild, f"🔨 **Ban** | {membre} par {ctx.author} | {raison}")

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user: str):
    if not await check_license(ctx): return
    banned = [b async for b in ctx.guild.bans()]
    for b in banned:
        if str(b.user) == user or str(b.user.id) == user:
            await ctx.guild.unban(b.user)
            return await ctx.send(f"✅ **{b.user}** débanni.")
    await ctx.send("❌ Introuvable dans les bans.")

@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute(ctx, membre: discord.Member, duree: int = 10, *, raison="Aucune raison"):
    if not await check_license(ctx): return
    until = discord.utils.utcnow() + datetime.timedelta(minutes=duree)
    await membre.timeout(until, reason=raison)
    await ctx.send(f"🔇 **{membre}** mute {duree}min. Raison : {raison}")
    await log_action(ctx.guild, f"🔇 **Mute** | {membre} par {ctx.author} | {duree}min | {raison}")

@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, membre: discord.Member):
    if not await check_license(ctx): return
    await membre.timeout(None)
    await ctx.send(f"🔊 **{membre}** unmute.")

@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn(ctx, membre: discord.Member, *, raison="Aucune raison"):
    if not await check_license(ctx): return
    warns = load("warns")
    gid, uid = str(ctx.guild.id), str(membre.id)
    if gid not in warns: warns[gid] = {}
    if uid not in warns[gid]: warns[gid][uid] = []
    warns[gid][uid].append({"raison": raison, "par": str(ctx.author), "date": datetime.datetime.utcnow().isoformat()})
    save("warns", warns)
    total = len(warns[gid][uid])
    await ctx.send(f"⚠️ **{membre}** averti. (`{total}` warn(s)) | {raison}")
    await log_action(ctx.guild, f"⚠️ **Warn** | {membre} par {ctx.author} | {raison} | Total : {total}")

@bot.command(name="warnings")
async def warnings(ctx, membre: discord.Member = None):
    if not await check_license(ctx): return
    membre = membre or ctx.author
    warns = load("warns").get(str(ctx.guild.id), {}).get(str(membre.id), [])
    if not warns: return await ctx.send(f"✅ **{membre}** n'a aucun warn.")
    embed = discord.Embed(title=f"⚠️ Warns de {membre.display_name}", color=discord.Color.orange())
    for i, w in enumerate(warns, 1):
        embed.add_field(name=f"Warn #{i}", value=f"{w['raison']} — par {w['par']}", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="clearwarns")
@commands.has_permissions(manage_messages=True)
async def clearwarns(ctx, membre: discord.Member):
    if not await check_license(ctx): return
    warns = load("warns")
    gid = str(ctx.guild.id)
    if gid in warns: warns[gid][str(membre.id)] = []
    save("warns", warns)
    await ctx.send(f"✅ Warns de **{membre}** effacés.")

@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, n: int = 5):
    if not await check_license(ctx): return
    await ctx.channel.purge(limit=n + 1)
    m = await ctx.send(f"🗑️ **{n}** message(s) supprimé(s).")
    await m.delete(delay=3)

@bot.command(name="lockdown")
@commands.has_permissions(manage_channels=True)
async def lockdown(ctx):
    if not await check_license(ctx): return
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 Salon verrouillé !")

@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    if not await check_license(ctx): return
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 Salon déverrouillé !")

@bot.command(name="setlogs")
@commands.has_permissions(administrator=True)
async def setlogs(ctx, channel: discord.TextChannel):
    if not await check_license(ctx): return
    config = load("config")
    gid = str(ctx.guild.id)
    if gid not in config: config[gid] = {}
    config[gid]["logs_channel"] = str(channel.id)
    save("config", config)
    await ctx.send(f"✅ Logs → {channel.mention}")


# ─────────────────────────────────────────
#  LOGS AUTOMATIQUES
# ─────────────────────────────────────────

@bot.event
async def on_message_delete(message):
    if message.author.bot: return
    if not is_licensed(message.guild.id): return
    await log_action(message.guild, f"🗑️ **Message supprimé** de **{message.author}** dans {message.channel.mention} :\n`{message.content[:500]}`")

@bot.event
async def on_message_edit(before, after):
    if before.author.bot: return
    if not before.guild: return
    if not is_licensed(before.guild.id): return
    if before.content == after.content: return
    await log_action(before.guild, f"✏️ **Message modifié** par **{before.author}** dans {before.channel.mention}\nAvant : `{before.content[:200]}`\nAprès : `{after.content[:200]}`")

@bot.event
async def on_member_ban(guild, user):
    if not is_licensed(guild.id): return
    await log_action(guild, f"🔨 **{user}** a été banni.")

@bot.event
async def on_member_unban(guild, user):
    if not is_licensed(guild.id): return
    await log_action(guild, f"✅ **{user}** a été débanni.")


# ─────────────────────────────────────────
#  BIENVENUE / AU REVOIR
# ─────────────────────────────────────────

@bot.command(name="setwelcome")
@commands.has_permissions(administrator=True)
async def setwelcome(ctx, channel: discord.TextChannel, *, message: str = None):
    if not await check_license(ctx): return
    config = load("config")
    gid = str(ctx.guild.id)
    if gid not in config: config[gid] = {}
    config[gid]["welcome_channel"] = str(channel.id)
    if message: config[gid]["welcome_message"] = message
    save("config", config)
    await ctx.send(f"✅ Bienvenue → {channel.mention}\nVariables dispo : `{{user}}` `{{server}}`")

@bot.command(name="setbye")
@commands.has_permissions(administrator=True)
async def setbye(ctx, channel: discord.TextChannel):
    if not await check_license(ctx): return
    config = load("config")
    gid = str(ctx.guild.id)
    if gid not in config: config[gid] = {}
    config[gid]["bye_channel"] = str(channel.id)
    save("config", config)
    await ctx.send(f"✅ Au revoir → {channel.mention}")

@bot.event
async def on_member_join(member):
    if not is_licensed(member.guild.id): return
    config = load("config")
    gc = config.get(str(member.guild.id), {})

    # Anti-raid
    if gc.get("antiraid"):
        gid = member.guild.id
        now = datetime.datetime.utcnow()
        if gid not in join_tracker: join_tracker[gid] = []
        join_tracker[gid] = [t for t in join_tracker[gid] if (now - t).seconds < 10]
        join_tracker[gid].append(now)
        if len(join_tracker[gid]) >= 5:
            await member.kick(reason="Anti-raid automatique")
            await log_action(member.guild, f"🛡️ **Anti-raid** : {member} kické automatiquement.")
            return

    # Bienvenue
    wc_id = gc.get("welcome_channel")
    if wc_id:
        ch = member.guild.get_channel(int(wc_id))
        if ch:
            msg = gc.get("welcome_message", f"Bienvenue sur **{member.guild.name}**, {{user}} ! 🎉")
            banniere = gc.get("banniere_url")
            embed = discord.Embed(
                title="👋 Nouveau membre !",
                description=msg.replace("{user}", member.mention).replace("{server}", member.guild.name),
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Membre #{member.guild.member_count}")
            if banniere: embed.set_image(url=banniere)
            await ch.send(embed=embed)

@bot.event
async def on_member_remove(member):
    if not is_licensed(member.guild.id): return
    config = load("config")
    gc = config.get(str(member.guild.id), {})
    bye_id = gc.get("bye_channel")
    if bye_id:
        ch = member.guild.get_channel(int(bye_id))
        if ch:
            embed = discord.Embed(
                description=f"👋 **{member.display_name}** a quitté le serveur.",
                color=discord.Color.red()
            )
            await ch.send(embed=embed)
    await log_action(member.guild, f"👋 **{member}** a quitté le serveur.")


# ─────────────────────────────────────────
#  NIVEAUX XP
# ─────────────────────────────────────────

def xp_needed(level):
    return 100 * (level ** 2) + 50 * level + 100

@bot.event
async def on_message(message):
    if message.author.bot: return
    if not message.guild: return

    if is_licensed(message.guild.id):
        xp_data = load("xp")
        gid, uid = str(message.guild.id), str(message.author.id)
        if gid not in xp_data: xp_data[gid] = {}
        if uid not in xp_data[gid]: xp_data[gid][uid] = {"xp": 0, "level": 1}

        xp_data[gid][uid]["xp"] += random.randint(5, 15)
        lvl = xp_data[gid][uid]["level"]

        if xp_data[gid][uid]["xp"] >= xp_needed(lvl):
            xp_data[gid][uid]["level"] += 1
            xp_data[gid][uid]["xp"] = 0
            new_lvl = xp_data[gid][uid]["level"]
            save("xp", xp_data)

            embed = discord.Embed(
                title="⬆️ Level Up !",
                description=f"GG {message.author.mention} ! Niveau **{new_lvl}** ! 🎉",
                color=discord.Color.gold()
            )
            await message.channel.send(embed=embed)

            config = load("config")
            level_roles = config.get(gid, {}).get("level_roles", {})
            if str(new_lvl) in level_roles:
                role = message.guild.get_role(int(level_roles[str(new_lvl)]))
                if role:
                    await message.author.add_roles(role)
                    await message.channel.send(f"🎭 {message.author.mention} a obtenu le rôle **{role.name}** !")
        else:
            save("xp", xp_data)

    await bot.process_commands(message)

@bot.command(name="rank")
async def rank(ctx, membre: discord.Member = None):
    if not await check_license(ctx): return
    membre = membre or ctx.author
    data = load("xp").get(str(ctx.guild.id), {}).get(str(membre.id), {"xp": 0, "level": 1})
    lvl, xp = data["level"], data["xp"]
    needed = xp_needed(lvl)
    bar = "█" * int((xp / needed) * 20) + "░" * (20 - int((xp / needed) * 20))
    embed = discord.Embed(title=f"⭐ Rang de {membre.display_name}", color=membre.color or discord.Color.blurple())
    embed.set_thumbnail(url=membre.display_avatar.url)
    embed.add_field(name="🏆 Niveau", value=str(lvl), inline=True)
    embed.add_field(name="⭐ XP", value=f"{xp}/{needed}", inline=True)
    embed.add_field(name="📊 Progression", value=f"`{bar}`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="topxp")
async def topxp(ctx):
    if not await check_license(ctx): return
    xp_data = load("xp").get(str(ctx.guild.id), {})
    if not xp_data: return await ctx.send("📭 Aucune donnée.")
    top = sorted(xp_data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
    medailles = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
    embed = discord.Embed(title="🏆 Top XP", color=discord.Color.gold())
    desc = ""
    for i, (uid, d) in enumerate(top):
        m = ctx.guild.get_member(int(uid))
        nom = m.display_name if m else "Inconnu"
        desc += f"{medailles[i]} **{nom}** — Niveau `{d['level']}` | XP `{d['xp']}`\n"
    embed.description = desc
    await ctx.send(embed=embed)

@bot.command(name="setlevelrole")
@commands.has_permissions(administrator=True)
async def setlevelrole(ctx, level: int, role: discord.Role):
    if not await check_license(ctx): return
    config = load("config")
    gid = str(ctx.guild.id)
    if gid not in config: config[gid] = {}
    if "level_roles" not in config[gid]: config[gid]["level_roles"] = {}
    config[gid]["level_roles"][str(level)] = str(role.id)
    save("config", config)
    await ctx.send(f"✅ Niveau **{level}** → rôle **{role.name}**")


# ─────────────────────────────────────────
#  TICKETS
# ─────────────────────────────────────────

@bot.command(name="setticket")
@commands.has_permissions(administrator=True)
async def setticket(ctx, category: discord.CategoryChannel = None):
    if not await check_license(ctx): return
    config = load("config")
    gid = str(ctx.guild.id)
    if gid not in config: config[gid] = {}
    if category: config[gid]["ticket_category"] = str(category.id)

    embed = discord.Embed(
        title="🎟️ Support",
        description="Clique sur 🎟️ pour ouvrir un ticket !",
        color=discord.Color.blurple()
    )
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎟️")
    config[gid]["ticket_message"] = str(msg.id)
    save("config", config)
    try: await ctx.message.delete()
    except: pass

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot: return
    if str(reaction.emoji) != "🎟️": return
    config = load("config")
    gc = config.get(str(reaction.message.guild.id), {})
    if str(reaction.message.id) != gc.get("ticket_message"): return

    guild = reaction.message.guild
    existing = discord.utils.get(guild.text_channels, name=f"ticket-{user.name.lower().replace(' ', '-')}")
    if existing:
        try: await user.send(f"❌ Tu as déjà un ticket ouvert : {existing.mention}")
        except: pass
        await reaction.remove(user)
        return

    cat_id = gc.get("ticket_category")
    cat = guild.get_channel(int(cat_id)) if cat_id else None
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    ch = await guild.create_text_channel(f"ticket-{user.name.lower().replace(' ', '-')}", overwrites=overwrites, category=cat)
    embed = discord.Embed(
        title="🎟️ Ticket ouvert",
        description=f"Bonjour {user.mention} !\nDécris ton problème, l'équipe va te répondre.\n\n`!closeticket` pour fermer.",
        color=discord.Color.green()
    )
    await ch.send(embed=embed)
    await reaction.remove(user)

@bot.command(name="closeticket")
async def closeticket(ctx):
    if not await check_license(ctx): return
    if not ctx.channel.name.startswith("ticket-"):
        return await ctx.send("❌ Ce n'est pas un salon ticket !")
    await ctx.send("🔒 Fermeture dans 5 secondes...")
    await asyncio.sleep(5)
    await ctx.channel.delete()


# ─────────────────────────────────────────
#  ANTI-RAID / ANTI-SPAM
# ─────────────────────────────────────────

@bot.command(name="antiraid")
@commands.has_permissions(administrator=True)
async def antiraid(ctx, mode: str):
    if not await check_license(ctx): return
    config = load("config")
    gid = str(ctx.guild.id)
    if gid not in config: config[gid] = {}
    config[gid]["antiraid"] = mode.lower() == "on"
    save("config", config)
    await ctx.send(f"🛡️ Anti-raid **{'activé ✅' if mode.lower() == 'on' else 'désactivé ❌'}**")

@bot.command(name="antispam")
@commands.has_permissions(administrator=True)
async def antispam(ctx, mode: str):
    if not await check_license(ctx): return
    config = load("config")
    gid = str(ctx.guild.id)
    if gid not in config: config[gid] = {}
    config[gid]["antispam"] = mode.lower() == "on"
    save("config", config)
    await ctx.send(f"🛡️ Anti-spam **{'activé ✅' if mode.lower() == 'on' else 'désactivé ❌'}**")


# ─────────────────────────────────────────
#  GIVEAWAY
# ─────────────────────────────────────────

@bot.command(name="gcreate")
@commands.has_permissions(manage_messages=True)
async def gcreate(ctx, duree: int, *, lot: str):
    """Lance un giveaway. Usage : !gcreate <minutes> <lot>"""
    if not await check_license(ctx): return
    fin = datetime.datetime.utcnow() + datetime.timedelta(minutes=duree)
    embed = discord.Embed(
        title=f"🎉 GIVEAWAY",
        description=(
            f"🏆 **{lot}**\n\n"
            f"Réagis avec 🎉 pour participer !\n"
            f"⏰ Durée : **{duree} minute(s)**\n"
            f"👤 Organisé par : {ctx.author.mention}"
        ),
        color=discord.Color.gold(),
        timestamp=fin
    )
    embed.set_footer(text="Fin le")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")

    giveaways = load("giveaways")
    giveaways[str(msg.id)] = {
        "channel_id": str(ctx.channel.id),
        "lot": lot,
        "actif": True
    }
    save("giveaways", giveaways)

    await asyncio.sleep(duree * 60)

    giveaways = load("giveaways")
    if not giveaways.get(str(msg.id), {}).get("actif"): return
    await _end_giveaway(msg.id, ctx.channel, lot)

async def _end_giveaway(msg_id, channel, lot):
    try:
        msg = await channel.fetch_message(msg_id)
        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        users = [u async for u in reaction.users() if not u.bot]
        if not users:
            await channel.send("😢 Aucun participant au giveaway !")
        else:
            gagnant = random.choice(users)
            embed = discord.Embed(
                title="🎉 Giveaway terminé !",
                description=f"🏆 Gagnant : {gagnant.mention}\n🎁 Lot : **{lot}**\n\nFélicitations ! 🎊",
                color=discord.Color.green()
            )
            await channel.send(embed=embed)
        giveaways = load("giveaways")
        giveaways[str(msg_id)]["actif"] = False
        save("giveaways", giveaways)
    except Exception as e:
        print(f"Erreur giveaway : {e}")

@bot.command(name="gend")
@commands.has_permissions(manage_messages=True)
async def gend(ctx, msg_id: int):
    if not await check_license(ctx): return
    giveaways = load("giveaways")
    if str(msg_id) not in giveaways: return await ctx.send("❌ Giveaway introuvable.")
    lot = giveaways[str(msg_id)]["lot"]
    giveaways[str(msg_id)]["actif"] = False
    save("giveaways", giveaways)
    await _end_giveaway(msg_id, ctx.channel, lot)

@bot.command(name="greroll")
@commands.has_permissions(manage_messages=True)
async def greroll(ctx, msg_id: int):
    if not await check_license(ctx): return
    try:
        msg = await ctx.channel.fetch_message(msg_id)
        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        users = [u async for u in reaction.users() if not u.bot]
        if not users: return await ctx.send("❌ Aucun participant.")
        gagnant = random.choice(users)
        await ctx.send(f"🎉 Nouveau gagnant : {gagnant.mention} !")
    except:
        await ctx.send("❌ Message introuvable.")


# ─────────────────────────────────────────
#  LANCEMENT
# ─────────────────────────────────────────
bot.run(TOKEN)
