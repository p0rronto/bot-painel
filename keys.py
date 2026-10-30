import json
import os
import secrets
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands

TOKEN_BOT_KEYS = ""
CANAL_LOGS_KEYS_ID = 
CARGO_PERMITIDO_ID =
ARQUIVO_KEYS = "keys.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


def carregar_dados():
    if not os.path.exists(ARQUIVO_KEYS):
        dados_iniciais = {"keys": {}, "usuarios": {}}
        salvar_dados(dados_iniciais)
        return dados_iniciais

    try:
        with open(ARQUIVO_KEYS, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        dados_iniciais = {"keys": {}, "usuarios": {}}
        salvar_dados(dados_iniciais)
        return dados_iniciais


def salvar_dados(dados):
    with open(ARQUIVO_KEYS, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4)


async def registrar_log_key(client, embed):
    try:
        canal = client.get_channel(
            CANAL_LOGS_KEYS_ID
        ) or await client.fetch_channel(CANAL_LOGS_KEYS_ID)
        await canal.send(embed=embed)
    except Exception as e:
        print(f"[ERRO LOG KEY]: {e}")


# ============================================================
# EVENTO ON_READY
# ============================================================
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"[BOT KEYS] Conectado como {bot.user}")
        print(
            f"[BOT KEYS] {len(synced)} comando(s) de barra sincronizado(s) com sucesso!"
        )
    except Exception as e:
        print(f"[ERRO AO SINCRONIZAR COMANDOS]: {e}")


# ============================================================
# COMANDO /GERARKEY
# ============================================================
@bot.tree.command(
    name="gerarkey", description="Gera uma nova key de acesso (Cargo Específico)"
)
@app_commands.choices(
    duracao=[
        app_commands.Choice(name="1 Dia", value="1d"),
        app_commands.Choice(name="7 Dias", value="7d"),
        app_commands.Choice(name="30 Dias", value="30d"),
        app_commands.Choice(name="90 Dias", value="90d"),
        app_commands.Choice(name="Lifetime (Vitalício)", value="lifetime"),
    ]
)
async def gerarkey(
    interaction: discord.Interaction, duracao: app_commands.Choice[str]
):
    cargo_permitido = interaction.guild.get_role(CARGO_PERMITIDO_ID)
    if not cargo_permitido or cargo_permitido not in interaction.user.roles:
        return await interaction.response.send_message(
            "❌ Você não tem o cargo necessário para gerar keys.",
            ephemeral=True,
        )

    # Gera o formato: FYNOT-XXXX-YYYY
    nova_key = f"FYNOT-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"

    dados = carregar_dados()

    # SALVA A KEY APENAS NA LISTA "keys" (NENHUM USUÁRIO RECEBE O ACESSO AINDA)
    dados["keys"][nova_key] = {
        "tipo": duracao.value,
        "criada_por": interaction.user.id,
        "criada_em": datetime.utcnow().isoformat(),
    }
    salvar_dados(dados)

    await interaction.response.send_message(
        f"🔑 **Key Gerada com Sucesso!**\n`{nova_key}`\n**Duração:** {duracao.name}\n\n*Ela só liberará o painel para quem resgatá-la com `/resgatarkey` no bot principal.*",
        ephemeral=True,
    )

    embed = discord.Embed(
        title="🔑 Log: Key Gerada", color=discord.Color.green()
    )
    embed.add_field(
        name="Gerado por", value=interaction.user.mention, inline=True
    )
    embed.add_field(name="Duração", value=duracao.name, inline=True)
    embed.add_field(name="Key", value=f"`{nova_key}`", inline=False)
    await registrar_log_key(bot, embed)


# ============================================================
# COMANDO /DELETARKEY
# ============================================================
@bot.tree.command(
    name="deletarkey",
    description="Exclui uma key gerada (esteja ela resgatada ou não)",
)
async def deletarkey(interaction: discord.Interaction, key: str):
    cargo_permitido = interaction.guild.get_role(CARGO_PERMITIDO_ID)
    if not cargo_permitido or cargo_permitido not in interaction.user.roles:
        return await interaction.response.send_message(
            "❌ Você não tem o cargo necessário para deletar keys.",
            ephemeral=True,
        )

    key = key.strip()
    dados = carregar_dados()

    encontrada = False
    status_remocao = ""

    # 1. Tenta remover da lista de keys NÃO resgatadas
    if key in dados.get("keys", {}):
        info_key = dados["keys"].pop(key)
        status_remocao = "Pendente (Não resgatada)"
        encontrada = True

    # 2. Se não estava em "keys", procura na lista de "usuarios" que já resgataram
    else:
        usuario_encontrado_id = None
        for user_id, user_data in dados.get("usuarios", {}).items():
            # Caso tenhas guardado o código da key no perfil do utilizador ou se a busca for pelo ID/Key
            if user_data.get("key_resgatada") == key or key == user_id:
                usuario_encontrado_id = user_id
                break

        # Se for para deletar o acesso ativo de um utilizador diretamente pelo ID ou key
        if usuario_encontrado_id:
            del dados["usuarios"][usuario_encontrado_id]
            status_remocao = f"Ativa (Revogado o acesso do ID <@{usuario_encontrado_id}>)"
            encontrada = True

    if not encontrada:
        return await interaction.response.send_message(
            "❌ Key ou Acesso não encontrado no sistema.",
            ephemeral=True,
        )

    salvar_dados(dados)

    await interaction.response.send_message(
        f"🗑️ **Key/Acesso Removido com Sucesso!**\n"
        f"🔑 **Key:** `{key}`\n"
        f"📌 **Status Anterior:** {status_remocao}",
        ephemeral=True,
    )

    # Log de Remoção
    embed = discord.Embed(
        title="🗑️ Log: Key/Acesso Deletado", color=discord.Color.red()
    )
    embed.add_field(
        name="Deletada por", value=interaction.user.mention, inline=True
    )
    embed.add_field(name="Status", value=status_remocao, inline=True)
    embed.add_field(name="Identificador", value=f"`{key}`", inline=False)
    await registrar_log_key(bot, embed)


bot.run(TOKEN_BOT_KEYS)
