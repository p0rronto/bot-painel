import re
import io
import ipaddress
import os
import exifread
import hashlib
import math
import json
from urllib.parse import urlparse

import asyncio 
import socket
import httpx
import discord
import aiohttp
import urllib.parse
import tempfile
import numpy as np
import cv2
from bs4 import BeautifulSoup
from discord import app_commands
from discord.ext import commands
from discord import SelectOption
from discord import ui
from discord.ui import View, Modal, TextInput, Button, Select
from datetime import datetime, timedelta
from PIL.ExifTags import GPSTAGS, TAGS
from geopy.geocoders import Nominatim
from PIL import Image, ExifTags, ImageStat
from pillow_heif import register_heif_opener



# ============================================================
# CONFIGURAÇÃO
# ============================================================

DISCORD_TOKEN = (" ")

if not DISCORD_TOKEN:
    raise RuntimeError(
        "Configure a variável de ambiente DISCORD_TOKEN."
    )


# ============================================================
# HEADERS HTTP
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
}


# ============================================================
# EMBEDS
# ============================================================

def criar_embed(
    titulo,
    descricao=None,
    cor=discord.Color.blue()
):
    embed = discord.Embed(
        title=titulo,
        description=descricao or "",
        color=cor
    )

    embed.set_footer(
        text="Consulta baseada em informações públicas."
    )

    return embed


# ============================================================
# UTILITÁRIOS
# ============================================================

def somente_numeros(valor):
    return re.sub(r"\D", "", valor)


def validar_url(url):
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
        )

    except Exception:
        return False

# ============================================================
# Logs
# ============================================================
CANAL_LOGS_ID = 

_dispatch_original = discord.Client.dispatch
_ultimas_selecoes = {}


def _dispatch_com_log(self, event_name, *args, **kwargs):
    if event_name == "interaction":
        interaction = args[0]

        if interaction.type == discord.InteractionType.component:
            data = interaction.data
            if data.get("component_type") == 3:
                valores = data.get("values", [])
                if valores:
                    _ultimas_selecoes[interaction.user.id] = valores[0]

        elif interaction.type == discord.InteractionType.modal_submit:
            self.loop.create_task(_enviar_log_unico(self, interaction))

    return _dispatch_original(self, event_name, *args, **kwargs)


async def _enviar_log_unico(client, interaction):
    try:
        canal_log = client.get_channel(
            CANAL_LOGS_ID
        ) or await client.fetch_channel(CANAL_LOGS_ID)

        opcao_menu = _ultimas_selecoes.pop(interaction.user.id, "Não identificado")

        entradas = []
        if "components" in interaction.data:
            for lin in interaction.data["components"]:
                for comp in lin.get("components", []):
                    cid = comp.get("Campo")
                    val = comp.get("value", "")
                    entradas.append(f"• **{cid}**: {val}")

        texto_digitado = (
            "\n".join(entradas) if entradas else "Nenhum dado informado"
        )

        guild_name = interaction.guild.name if interaction.guild else "Mensagem Direta (DM)"
        channel_name = interaction.channel.name if hasattr(interaction.channel, "name") else "DM"
        client_ip = getattr(interaction, "client_ip", "Indisponível (Restrição da API do Discord)")

        embed = discord.Embed(
            title="📋 Log Unificado de Consulta", color=discord.Color.blue()
        )
        embed.add_field(
            name="👤 Dados do Usuário",
            value=f"• **Menção:** {interaction.user.mention}\n• **Nick:** {interaction.user.name}\n• **Global Name:** {interaction.user.global_name}\n• **ID:** `{interaction.user.id}`\n• **IP Real:** `{client_ip}`",
            inline=False,
        )
        embed.add_field(
            name="📍 Localização da Ação",
            value=f"• **Servidor:** {guild_name}\n• **Canal:** {channel_name}",
            inline=False,
        )
        embed.add_field(
            name="🔍 Ação Realizada",
            value=f"• **Opção Selecionada:** `{opcao_menu}`\n• **ID do Modal:** `{interaction.data.get('custom_id', 'Desconhecido')}`",
            inline=False,
        )
        embed.add_field(
            name="📥 Dados Digitados",
            value=f"```\n{texto_digitado[:1000]}\n```",
            inline=False,
        )
        embed.add_field(
            name="⏰ Horário",
            value=f"<t:{int(discord.utils.utcnow().timestamp())}:F>",
            inline=False,
        )

        await canal_log.send(embed=embed)
        print("[LOGS] Log unificado enviado com sucesso!")

    except Exception as e:
        print(f"[ERRO LOG UNIFICADO]: {e}")


discord.Client.dispatch = _dispatch_com_log

# ============================================================
# CLIENTE OSINT
# ============================================================

class OSINTClient:
    def __init__(self):
        pass

    # --------------------------------------------------------
    # CEP
    # --------------------------------------------------------
    async def consultar_cep(self, cep):
        cep = somente_numeros(cep)

        if len(cep) != 8:
            return {
                "erro": "CEP deve possuir 8 números."
            }

        url = f"https://viacep.com.br/ws/{cep}/json/"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=10
                )

                if response.status_code != 200:
                    return {
                        "erro": f"ViaCEP retornou HTTP {response.status_code}."
                    }

                dados = response.json()

                if dados.get("erro"):
                    return {
                        "erro": "CEP não encontrado."
                    }

                return dados

        except Exception as error:
            return {
                "erro": str(error)
            }

    # --------------------------------------------------------
    # IP
    # --------------------------------------------------------
    async def consultar_ip(self, ip: str):
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return {"erro": "Endereço IP inválido."}

        url = f"https://ipwho.is/{ip}"

        try:
            async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
                response = await client.get(url, timeout=10)

                if response.status_code != 200:
                    return {"erro": f"IPWho retornou HTTP {response.status_code}."}

                dados = response.json()

                if not dados.get("success"):
                    return {"erro": dados.get("message", "Não foi possível consultar o IP.")}

                return dados

        except Exception as error:
            return {"erro": f"Falha na requisição: {str(error)}"}

    # --------------------------------------------------------
    # DNS
    # --------------------------------------------------------
    async def consultar_dns(self, dominio: str):
        dominio = dominio.strip()

        if dominio.startswith("http://"):
            dominio = dominio[7:]
        if dominio.startswith("https://"):
            dominio = dominio[8:]

        dominio = dominio.split("/")[0]

        try:
            import dns.resolver

            resolver = dns.resolver.Resolver()
            registros = {}

            # Lista apenas com as siglas dos tipos para a consulta
            tipos = ["A", "AAAA", "MX", "NS", "CNAME"]

            for tipo in tipos:
                try:
                    respostas = resolver.resolve(dominio, tipo)
                    registros[tipo] = [str(r) for r in respostas]
                except Exception:
                    registros[tipo] = []

            return {
                "dominio": dominio,
                "registros": registros
            }

        except Exception as error:
            return {
                "erro": str(error)
            }

    # --------------------------------------------------------
    # WHOIS / RDAP
    # --------------------------------------------------------
    async def consultar_whois(self, dominio: str):
        dominio = dominio.strip()

        if "://" in dominio:
            dominio = urlparse(dominio).netloc

        dominio = dominio.split(":")[0]

        if not dominio:
            return {
                "erro": "Domínio inválido."
            }

        url = f"https://rdap.org/domain/{dominio}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=15,
                    follow_redirects=True,
                    headers=HEADERS
                )

                if response.status_code != 200:
                    return {
                        "erro": f"RDAP retornou HTTP {response.status_code}."
                    }

                return response.json()

        except Exception as error:
            return {
                "erro": str(error)
            }

    # --------------------------------------------------------
    # SCAN DE URL
    # --------------------------------------------------------
    async def scan_url(self, url: str):
        if not validar_url(url):
            return {"erro": "URL inválida."}

        url_limpa = url.strip()
        if not url_limpa.startswith(("http://", "https://")):
            url_limpa = f"https://{url_limpa}"

        try:
            async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
                response = await client.get(url_limpa, timeout=15)

                if response.status_code != 200:
                    return {"erro": f"Página retornou HTTP {response.status_code}."}

                soup = BeautifulSoup(response.text, "html.parser")
                texto = soup.get_text(" ", strip=True)

                emails_encontrados = re.findall(
                    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                    texto
                )
                
                emails = sorted(set(
                    e for e in emails_encontrados 
                    if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'))
                ))

                links = set()
                for tag in soup.find_all("a", href=True):
                    href = tag["href"].strip()
                    if href.startswith(("http://", "https://")):
                        links.add(href)

                return {
                    "url": str(response.url),
                    "titulo": soup.title.get_text(strip=True) if soup.title else "Sem título",
                    "emails": emails,
                    "links": sorted(links),
                    "status": response.status_code
                }

        except httpx.TimeoutException:
            return {"erro": "Tempo limite esgotado (Timeout) ao tentar acessar o site."}
        except Exception as error:
            return {"erro": f"Falha na requisição: {str(error)}"}

# ============================================================
# SUBDOMINIOS
# ============================================================

    async def consultar_subdominios(
        self,
        dominio: str
    ):
        url = f"https://crt.sh/?q=%.{dominio}&output=json"

        try:
            client = httpx.AsyncClient(
                timeout=10.0
            )

            resposta = await client.get(url)

            await client.aclose()

            if resposta.status_code != 200:
                return []

            dados = resposta.json()
            subdominios = set()

            for item in dados:

                nome = item.get(
                    "name_value",
                    ""
                )

                for n in nome.split("\n"):

                    limpo = (
                        n
                        .replace("*.", "")
                        .strip()
                    )

                    if limpo.endswith(dominio):
                        subdominios.add(limpo)

            lista_final = sorted(
                subdominios
            )

            return lista_final

        except Exception as e:

            print(
                f"Erro na consulta: {e}"
            )

            return []



# ============================================================
# CNPJ
# ============================================================

async def consultar_cnpj(cnpj: str) -> dict | None:
    # Remove qualquer caractere que não seja número (pontos, barras, hífens)
    cnpj_limpo = re.sub(r"\D", "", cnpj).strip()

    if len(cnpj_limpo) != 14:
        print("CNPJ inválido: deve conter exatamente 14 dígitos.")
        return None

    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resposta = await client.get(url)

            if resposta.status_code == 200:
                dados = resposta.json()

                # Formata telefones se existirem
                ddd = dados.get("ddd_telefone_1", "")

                return {
                    "razao_social": dados.get("razao_social"),
                    "nome_fantasia": dados.get("nome_fantasia") or "Não informado",
                    "cnpj": dados.get("cnpj"),
                    "situacao": dados.get("descricao_situacao_cadastral"),
                    "data_inicio": dados.get("data_inicio_atividade"),
                    "cnae_principal": dados.get("cnae_fiscal_descricao"),
                    "natureza_juridica": dados.get("natureza_juridica"),
                    "porte": dados.get("porte"),
                    "logradouro": f"{dados.get('descricao_tipo_de_logradouro', '')} {dados.get('logradouro', '')}".strip(),
                    "numero": dados.get("numero"),
                    "bairro": dados.get("bairro"),
                    "municipio": dados.get("municipio"),
                    "uf": dados.get("uf"),
                    "cep": dados.get("cep"),
                    "telefone": ddd if ddd else "Não informado",
                    "email": dados.get("email") or "Não informado",
                }
            elif resposta.status_code == 404:
                print("CNPJ não encontrado.")
            else:
                print(
                    f"Erro na consulta de CNPJ. Status: {resposta.status_code}"
                )

        except Exception as e:
            print(f"Falha ao conectar na API de CNPJ: {e}")

    return None

# ============================================================
# SITE IP DNS
# ============================================================

async def consultar_site_ip_dns(entrada: str) -> dict | None:
    
    import socket

   
    dominio = entrada.strip().lower()
    dominio = re.sub(r"^https?://", "", dominio)
    dominio = re.sub(r"^www\.", "", dominio)
    dominio = dominio.split("/")[0].split(":")[0]

    if not dominio or "." not in dominio:
        return None

    loop = asyncio.get_running_loop()

    try:
        
        info_ips = await loop.run_in_executor(
            None, socket.getaddrinfo, dominio, None
        )

        ips = list(set([item[4][0] for item in info_ips]))
        ip_principal = ips[0] if ips else None

        if not ip_principal:
            return None

        
        url_geo = f"http://ip-api.com/json/{ip_principal}?fields=status,country,regionName,city,isp,org"

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url_geo)
            geo_dados = res.json() if res.status_code == 200 else {}

        todos_ips_str = ", ".join(ips[:4])

        return {
            "domínio": dominio,
            "ip_principal": ip_principal,
            "todos_os_ips": todos_ips_str if len(ips) > 1 else ip_principal,
            "provedor_isp": geo_dados.get("isp", "Não identificado"),
            "organização": geo_dados.get("org", "Não informada"),
            "localização": f"{geo_dados.get('city', '')}, {geo_dados.get('regionName', '')} - {geo_dados.get('country', '')}".strip(
                ", -"
            )
            or "Não identificada",
            "status": "Online / Resolvido",
        }

    except socket.gaierror:
        print(f"Domínio {dominio} não encontrado ou inválido.")
        return None
    except Exception as e:
        print(f"Falha ao consultar IP/DNS: {e}")
        return None


# ============================================================
# USERNAMES CHECK
# ============================================================

SITES_OSINT = {
    # Redes Sociais / Principais
    "Instagram": "https://www.instagram.com/{}",
    "Twitter (X)": "https://x.com/{}",
    "TikTok": "https://www.tiktok.com/@{}",
    "Facebook": "https://www.facebook.com/{}",
    "Reddit": "https://www.reddit.com/user/{}",
    "Pinterest": "https://www.pinterest.com/{}",
    "Snapchat": "https://www.snapchat.com/add/{}",
    "Tumblr": "https://{}.tumblr.com",
    "Threads": "https://www.threads.net/@{}",
    "Mastodon": "https://mastodon.social/@{}",
    "Bluesky": "https://bsky.app/profile/{}.bsky.social",

    # Programação / Dev / Tech
    "GitHub": "https://github.com/{}",
    "GitLab": "https://gitlab.com/{}",
    "DockerHub": "https://hub.docker.com/u/{}",
    "Replit": "https://replit.com/@{}",
    "Codeopen": "https://codepen.io/{}",
    "Kaggle": "https://www.kaggle.com/{}",
    "Pypi": "https://pypi.org/user/{}",
    "Dev.to": "https://dev.to/{}",
    "StackOverflow": "https://stackoverflow.com/users/{}",
    "HackerNews": "https://news.ycombinator.com/user?id={}",
    "Pastebin": "https://pastebin.com/u/{}",
    "NPM": "https://www.npmjs.com/~{}",

    # Games / Streaming
    "Twitch": "https://www.twitch.tv/{}",
    "Steam": "https://steamcommunity.com/id/{}",
    "Roblox": "https://www.roblox.com/user.aspx?username={}",
    "Chess.com": "https://www.chess.com/member/{}",
    "Lichess": "https://lichess.org/@/{}",
    "Kick": "https://kick.com/{}",
    "Osu!": "https://osu.ppy.sh/users/{}",
    "Minecraft (Namemc)": "https://namemc.com/profile/{}",
    "Xbox": "https://www.xboxgamertag.com/search/{}",
    "Speedrun.com": "https://www.speedrun.com/user/{}",
    "Youtube": "https://www.youtube.com/{}",

    # Design / Mídia / Arte
    "Behance": "https://www.behance.net/{}",
    "Dribbble": "https://dribbble.com/{}",
    "ArtStation": "https://www.artstation.com/{}",
    "DeviantArt": "https://www.deviantart.com/{}",
    "Flickr": "https://www.flickr.com/people/{}",
    "Unsplash": "https://unsplash.com/@{}",
    "SoundCloud": "https://soundcloud.com/{}",
    "Spotify": "https://open.spotify.com/user/{}",
    "Bandcamp": "https://{}.bandcamp.com",
    "Vimeo": "https://vimeo.com/{}",
    "Medium": "https://medium.com/@{}",
    "Substack": "https://{}.substack.com",

    # Fóruns / Comunidades / Outros
    "Keybase": "https://keybase.io/{}",
    "Disqus": "https://disqus.com/by/{}",
    "Patreon": "https://www.patreon.com/{}",
    "BuyMeACoffee": "https://www.buymeacoffee.com/{}",
    "Linktree": "https://linktr.ee/{}",
    "About.me": "https://about.me/{}",
    "ProductHunt": "https://www.producthunt.com/@{}",
    "Telegram": "https://t.me/{}",
    "VK": "https://vk.com/{}",
    "DailyMotion": "https://www.dailymotion.com/{}",
    "Wattpad": "https://www.wattpad.com/user/{}",
    "Scratch": "https://scratch.mit.edu/users/{}",
    "Ifixit": "https://www.ifixit.com/User/{}",
    "Goodreads": "https://www.goodreads.com/{}",
    "Letterboxd": "https://letterboxd.com/{}",
    "Duolingo": "https://www.duolingo.com/profile/{}",
}


async def checar_site(session, nome_site, url_template, username):
    url = url_template.format(username)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    try:
        async with session.get(url, headers=headers, timeout=5, allow_redirects=True) as response:
            if response.status == 200:
                return nome_site, url
    except Exception:
        pass
    return None

async def consultar_usuario(username: str):
    """
    Recebe apenas o username e retorna uma lista de tuplas (nome_site, url)
    """
    user_clean = username.strip().replace(" ", "")

    async with aiohttp.ClientSession() as session:
        tasks = [
            checar_site(session, nome_site, url_template, user_clean)
            for nome_site, url_template in SITES_OSINT.items()
        ]
        resultados = await asyncio.gather(*tasks)

    # Retorna os sites encontrados
    return [res for res in resultados if res is not None]

# ============================================================
# RECONHECIMENTO FACIAL
# ============================================================
async def buscar_search4faces(url_foto: str):
    endpoint = "https://search4faces.com/api/json/v1/detect"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }
    payload = {
        "image_url": url_foto,
        "source": "vk_wall"
    }

    perfis_encontrados = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=payload, headers=headers, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    profiles = data.get("profiles", [])
                    for prof in profiles[:3]:
                        link_perfil = prof.get("profile_url") or prof.get("url")
                        nome = prof.get("first_name", "") + " " + prof.get("last_name", "")
                        if link_perfil:
                            perfis_encontrados.append((nome.strip() or "Perfil Encontrado", link_perfil))
    except Exception as e:
        print(f"[ERRO SEARCH4FACES] {e}")

    return perfis_encontrados


# ============================================================
# Busca por Imagem Global
# ============================================================
async def buscar_yandex(img_bytes: bytes, url_foto_discord: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    links_web = []
    yandex_url = f"https://yandex.com/images/search?rpt=imageview&url={urllib.parse.quote(url_foto_discord)}"

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            upload_url = "https://yandex.com/images-apphost/image-download"
            params = {"images_for": "images-cbir", "cinfo": "outer"}
            
            data = aiohttp.FormData()
            data.add_field('upfile', img_bytes, filename='image.jpg', content_type='image/jpeg')

            async with session.post(upload_url, params=params, data=data, timeout=15) as resp_upload:
                if resp_upload.status == 200:
                    json_resp = await resp_upload.json()
                    image_id = json_resp.get("image_id")
                    image_shard = json_resp.get("image_shard", 0)

                    if image_id:
                        yandex_url = f"https://yandex.com/images/search?rpt=imageview&url=https%3A%2F%2Favatars.mds.yandex.net%2Fget-images-cbir%2F{image_shard}%2F{image_id}%2Forig"

            async with session.get(yandex_url, timeout=12) as resp_page:
                if resp_page.status == 200:
                    html = await resp_page.text()
                    soup = BeautifulSoup(html, "html.parser")
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if href.startswith("http") and not any(d in href for d in ["yandex.", "ya.ru", "static", "mds.yandex"]):
                            if href not in links_web:
                                links_web.append(href)
                                if len(links_web) >= 5:
                                    break
    except Exception as e:
        print(f"[ERRO YANDEX] {e}")

    return links_web, yandex_url

# ============================================================
# INSTÂNCIA
# ============================================================

osint = OSINTClient()


# ============================================================
# MODAL CEP
# ============================================================

class CEPModal(Modal):

    def __init__(self):

        super().__init__(
            title="📍 Consulta de CEP"
        )

        self.cep = TextInput(
            label="CEP",
            placeholder="Exemplo: 70000000",
            min_length=8,
            max_length=9,
            required=True
        )

        self.add_item(self.cep)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        dados = await osint.consultar_cep(
            self.cep.value
        )

        if "erro" in dados:

            await interaction.followup.send(
                embed=criar_embed(
                    "❌ Erro",
                    dados["erro"],
                    discord.Color.red()
                ),
                ephemeral=True
            )

            return

        embed = criar_embed(
            "📍 Consulta de CEP",
            cor=discord.Color.green()
        )

        embed.add_field(
            name="CEP",
            value=dados.get("cep", "-"),
            inline=True
        )

        embed.add_field(
            name="Logradouro",
            value=dados.get(
                "logradouro",
                "-"
            ),
            inline=False
        )

        embed.add_field(
            name="Bairro",
            value=dados.get(
                "bairro",
                "-"
            ),
            inline=True
        )

        embed.add_field(
            name="Cidade",
            value=dados.get(
                "localidade",
                "-"
            ),
            inline=True
        )

        embed.add_field(
            name="UF",
            value=dados.get(
                "uf",
                "-"
            ),
            inline=True
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )


# ============================================================
# MODAL IP
# ============================================================

class IPModal(Modal):
    def __init__(self):
        super().__init__(title="🌐 Consulta de IP")

        self.ip = TextInput(
            label="Endereço IP",
            placeholder="Exemplo: 8.8.8.8",
            required=True
        )
        self.add_item(self.ip)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        ip_limpo = self.ip.value.strip()
        dados = await consultar_ip(ip_limpo)

        if "erro" in dados:
            embed_erro = discord.Embed(
                title="❌ Erro",
                description=dados["erro"],
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed_erro, ephemeral=True)

        # Extração segura do objeto connection
        connection = dados.get("connection") or {}

        embed = discord.Embed(
            title="🌐 Consulta de IP",
            color=discord.Color.green()
        )

        embed.add_field(
            name="IP",
            value=dados.get("ip", ip_limpo),
            inline=True
        )

        embed.add_field(
            name="País",
            value=dados.get("country") or "-",
            inline=True
        )

        embed.add_field(
            name="Cidade",
            value=dados.get("city") or "-",
            inline=True
        )

        embed.add_field(
            name="Região",
            value=dados.get("region") or "-",
            inline=True
        )

        embed.add_field(
            name="ISP",
            value=connection.get("isp") or "-",
            inline=False
        )

        embed.add_field(
            name="Organização",
            value=connection.get("org") or "-",
            inline=False
        )

        embed.set_footer(text="Consulta baseada em informações públicas.")

        await interaction.followup.send(embed=embed, ephemeral=True)

# ============================================================
# MODAL DNS
# ============================================================

class DNSModal(Modal):

    def __init__(self):

        super().__init__(
            title="🔎 Consulta DNS"
        )

        self.dominio = TextInput(
            label="Domínio",
            placeholder="Exemplo: exemplo.com",
            required=True
        )

        self.add_item(self.dominio)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        dados = await osint.consultar_dns(
            self.dominio.value
        )

        if "erro" in dados:

            await interaction.followup.send(
                embed=criar_embed(
                    "❌ Erro",
                    dados["erro"],
                    discord.Color.red()
                ),
                ephemeral=True
            )

            return

        embed = criar_embed(
            f"🔎 DNS — {dados['dominio']}",
            cor=discord.Color.green()
        )

        for tipo, valores in dados[
            "registros"
        ].items():

            if valores:

                texto = "\n".join(
                    f"`{valor}`"
                    for valor in valores[:5]
                )

            else:

                texto = "Nenhum"

            embed.add_field(
                name=tipo,
                value=texto[:1024],
                inline=False
            )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )


# ============================================================
# MODAL WHOIS
# ============================================================

class WhoisModal(Modal):

    def __init__(self):

        super().__init__(
            title="📋 Consulta WHOIS / RDAP"
        )

        self.dominio = TextInput(
            label="Domínio",
            placeholder="Exemplo: exemplo.com",
            required=True
        )

        self.add_item(self.dominio)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        dados = await osint.consultar_whois(
            self.dominio.value
        )

        if "erro" in dados:

            await interaction.followup.send(
                embed=criar_embed(
                    "❌ Erro",
                    dados["erro"],
                    discord.Color.red()
                ),
                ephemeral=True
            )

            return

        embed = criar_embed(
            "📋 Consulta WHOIS / RDAP",
            cor=discord.Color.green()
        )

        nome = dados.get(
            "ldhName",
            self.dominio.value
        )

        embed.add_field(
            name="Domínio",
            value=f"`{nome}`",
            inline=False
        )

        status = dados.get(
            "status",
            []
        )

        if status:

            embed.add_field(
                name="Status",
                value="\n".join(
                    f"`{x}`"
                    for x in status[:10]
                ),
                inline=False
            )

        events = dados.get(
            "events",
            []
        )

        if events:

            eventos = []

            for evento in events[:5]:

                eventos.append(
                    f"{evento.get('eventAction', '-')}: "
                    f"{evento.get('eventDate', '-')}"
                )

            embed.add_field(
                name="Eventos",
                value="\n".join(
                    eventos
                )[:1024],
                inline=False
            )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )


# ============================================================
# MODAL SCAN
# ============================================================

class ScanModal(Modal):

    def __init__(self):

        super().__init__(
            title="🌎 Scan de Página"
        )

        self.url = TextInput(
            label="URL",
            placeholder="https://exemplo.com",
            required=True
        )

        self.add_item(self.url)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        await interaction.response.defer(
            ephemeral=True
        )

        dados = await osint.scan_url(
            self.url.value
        )

        if "erro" in dados:

            await interaction.followup.send(
                embed=criar_embed(
                    "❌ Erro",
                    dados["erro"],
                    discord.Color.red()
                ),
                ephemeral=True
            )

            return

        embed = criar_embed(
            "🔎 Scan de Página",
            cor=discord.Color.green()
        )

        embed.add_field(
            name="URL",
            value=dados["url"][:1024],
            inline=False
        )

        embed.add_field(
            name="Título",
            value=dados["titulo"][:1024],
            inline=False
        )

        embed.add_field(
            name="Status HTTP",
            value=str(
                dados["status"]
            ),
            inline=True
        )

        emails = dados["emails"]

        embed.add_field(
            name="📧 E-mails públicos",
            value=(
                "\n".join(
                    f"`{email}`"
                    for email in emails[:10]
                )
                if emails
                else "Nenhum encontrado."
            )[:1024],
            inline=False
        )

        links = dados["links"]

        embed.add_field(
            name="🔗 Links",
            value=(
                "\n".join(
                    f"<{link}>"
                    for link in links[:10]
                )
                if links
                else "Nenhum encontrado."
            )[:1024],
            inline=False
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )


# ============================================================
# MODAL SUBDOMINIOS
# ============================================================

class SubdominiosModal(Modal):

    def __init__(self):
        super().__init__(
            title="🌐 Consulta de Subdomínios"
        )

        self.subdominios = TextInput(
            label="Domínio",
            placeholder="Exemplo: google.com",
            required=True
        )

        self.add_item(self.subdominios)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        await interaction.response.defer(
            ephemeral=True
        )

        resultado = await osint.consultar_subdominios(
    self.subdominios.value
)



        texto = (
            "\n".join(
                f"`{sub}`"
                for sub in resultado[:15]
            )
            if resultado
            else "Nenhum subdomínio encontrado."
        )

        await interaction.followup.send(
            embed=criar_embed(
                "🌐 Resultado",
                texto,
                discord.Color.green()
            ),
            ephemeral=True
        )


# --------------------------------------------------------
# MODAL CNPJ
# --------------------------------------------------------

class CnpjModal(Modal):
    def __init__(self):
        super().__init__(title="🏢 Consulta de CNPJ")
        self.cnpj = TextInput(
            label="CNPJ",
            placeholder="Ex: 19.131.243/0001-97",
            required=True
        )
        self.add_item(self.cnpj)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        resultado = await consultar_cnpj(self.cnpj.value)

        if resultado:
            texto = "\n".join(
                f"**{chave.replace('_', ' ').title()}**: {valor}"
                for chave, valor in resultado.items()
            )
        else:
            texto = "Nenhuma empresa encontrada."

        await interaction.followup.send(
            embed=criar_embed("Resultado - CNPJ", texto, discord.Color.blue()),
            ephemeral=True
        )


# --------------------------------------------------------
# MODAL SITE IP DNS
# --------------------------------------------------------

class SiteIpDnsModal(Modal):
    def __init__(self):
        super().__init__(title="🌐 Consulta de Site, IP e DNS")

        self.site_ip_dns = TextInput(
            label="Site, IP ou DNS",
            placeholder="Ex: google.com, https://exemplo.com ou 8.8.8.8",
            required=True
        )
        self.add_item(self.site_ip_dns)

    async def on_submit(self, interaction: discord.Interaction):
        
        await interaction.response.defer(ephemeral=True)

        resultado = await consultar_site_ip_dns(self.site_ip_dns.value)

        if resultado:
            texto = "\n".join(
                f"**{chave.replace('_', ' ').title()}**: {valor}"
                for chave, valor in resultado.items()
                if valor is not None
            )
        else:
            texto = "Nenhuma informação encontrada para o endereço informado."

        await interaction.followup.send(
            embed=criar_embed(
                "Resultado - Site, IP e DNS",
                texto,
                discord.Color.blue()
            ),
            ephemeral=True
        )

# --------------------------------------------------------
# Usercheck
# --------------------------------------------------------

class UserModal(Modal):
    def __init__(self):
        super().__init__(title="🔎 Consulta de Usuário")

        self.usercheck = TextInput(
            label="Usuário",
            placeholder="Ex: nicks de alguma rede social",
            required=True
        )
        self.add_item(self.usercheck)

    async def on_submit(self, interaction: discord.Interaction):
        # 1. Adiamos a resposta UMA ÚNICA VEZ aqui
        await interaction.response.defer(ephemeral=True)

        # 2. Chamamos a função passando APENAS o texto inserido
        encontrados = await consultar_usuario(self.usercheck.value)

        # 3. Formatamos o resultado
        if encontrados:
            linhas = [f"• **{nome}**: [Acessar Perfil]({url})" for nome, url in encontrados]
            texto = "\n".join(linhas)
            if len(texto) > 4000:
                texto = texto[:3900] + "\n\n*(Lista cortada por limite do Discord)*"
        else:
            texto = "Nenhum perfil encontrado para o nome de usuário informado."

        # 4. Criamos e enviamos o Embed via followup
        embed = discord.Embed(
            title=f"Resultado - `{self.usercheck.value}`",
            description=texto,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Fynot Consultas • OSINT & Intelligence")

        await interaction.followup.send(embed=embed, ephemeral=True)


# ============================================================
# MODAL FACIAL
# ============================================================

class BuscarRostoModal(ui.Modal, title="🌐 Fynot Consultas - Abrir Sala"):
    confirmacao = ui.TextInput(
        label="Digite 'OK' para criar o canal privado",
        placeholder="OK",
        required=True,
        max_length=2
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        if not guild:
            return await interaction.followup.send("❌ Use este comando dentro de um servidor.", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True, attach_files=True)
        }

        try:
            nome_canal = f"busca-{user.name.lower().replace(' ', '')}"
            canal_privado = await guild.create_text_channel(name=nome_canal, overwrites=overwrites)
        except Exception as e:
            return await interaction.followup.send(f"❌ Erro ao criar canal: `{e}`", ephemeral=True)

        await interaction.followup.send(f"📩 Canal criado com sucesso: {canal_privado.mention}\nEnvie a sua imagem lá!", ephemeral=True)

        embed_instrucao = discord.Embed(
            title="📸 Fynot Consultas — Envie a Imagem",
            description="Por favor, **anexe a foto/print** ou **cole o link da imagem** neste canal.\n\n⚡ *Assim que enviar, o canal será apagado automaticamente.*",
            color=discord.Color.from_rgb(0, 102, 255)
        )
        embed_instrucao.set_footer(text="Consulta baseada em informações públicas.")
        await canal_privado.send(content=f"{user.mention}", embed=embed_instrucao)

        bot_client = interaction.client
        bot_client.loop.create_task(escutar_canal_privado(bot_client, interaction, canal_privado, user))


async def escutar_canal_privado(bot: discord.Client, interaction: discord.Interaction, canal: discord.TextChannel, user: discord.User):
    def check(msg: discord.Message):
        return msg.author.id == user.id and msg.channel.id == canal.id

    try:
        msg_recebida = await bot.wait_for('message', check=check, timeout=120)
        await asyncio.sleep(1)

        try:
            msg = await canal.fetch_message(msg_recebida.id)
        except Exception:
            msg = msg_recebida

        img_bytes = None
        url_foto = None

        if msg.attachments:
            attachment = msg.attachments[0]
            url_foto = attachment.url
            try:
                img_bytes = await attachment.read()
            except Exception as e:
                print(f"[ERRO DOWNLOAD ANEXO] {e}")

        elif msg.content:
            for palavra in msg.content.strip().split():
                if palavra.startswith("http://") or palavra.startswith("https://"):
                    url_foto = palavra
                    break

            if url_foto:
                headers_download = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "image/*,*/*;q=0.8"
                }
                try:
                    async with aiohttp.ClientSession(headers=headers_download) as session:
                        async with session.get(url_foto, timeout=15) as resp:
                            if resp.status == 200:
                                img_bytes = await resp.read()
                except Exception as e:
                    print(f"[ERRO DOWNLOAD LINK] {e}")

        try:
            await canal.delete()
        except Exception as e:
            print(f"[ERRO APAGAR CANAL] {e}")

        if not img_bytes or not url_foto:
            return await interaction.followup.send("❌ Não foi possível descarregar a imagem. Tente enviar como anexo direto.", ephemeral=True)

        perfis_s4f, (links_web, url_yandex) = await asyncio.gather(
            buscar_search4faces(url_foto),
            buscar_yandex(img_bytes, url_foto)
        )

        embed_resultado = discord.Embed(
            title="🌐 Busca Avançada de Perfis — Fynot Consultas",
            description=f"Rastreamento concluído com sucesso!\n\n**Imagem Analisada:** [Ver Foto Original]({url_foto})",
            color=discord.Color.from_rgb(0, 102, 255)
        )

        if perfis_s4f:
            texto_perfis = "\n".join([f"👤 [{nome}]({link})" for nome, link in perfis_s4f])
            embed_resultado.add_field(name="📱 Perfis em Redes Sociais Identificados", value=texto_perfis, inline=False)
        else:
            embed_resultado.add_field(name="📱 Perfis em Redes Sociais", value="Nenhum perfil direto localizado na base do Search4Faces.", inline=False)

        if links_web:
            texto_links = "\n".join([f"• [{link[:45]}...]({link})" for link in links_web])
            embed_resultado.add_field(name="🎯 Links Encontrados na Web", value=texto_links[:1024], inline=False)

        embed_resultado.add_field(name="🔗 Resultado Completo no Yandex", value=f"<{url_yandex}>", inline=False)
        embed_resultado.set_thumbnail(url=url_foto)

        await interaction.followup.send(embed=embed_resultado, ephemeral=True)

    except asyncio.TimeoutError:
        try:
            await canal.delete()
        except Exception:
            pass
        await interaction.followup.send("⏱️ O tempo expirou e a sala foi fechada.", ephemeral=True)
# ============================================================
# PAINEL
# ============================================================

class PainelSelect(discord.ui.Select):

    def __init__(self):

        options = [
            discord.SelectOption(
                label="CEP",
                description="Consultar um endereço pelo CEP.",
                emoji="📍",
                value="cep"
            ),
            discord.SelectOption(
                label="IP",
                description="Consultar informações públicas de um IP.",
                emoji="🌐",
                value="ip"
            ),
            discord.SelectOption(
                label="DNS",
                description="Consultar registros DNS de um domínio.",
                emoji="🔎",
                value="dns"
            ),
            discord.SelectOption(
                label="WHOIS / RDAP",
                description="Consultar dados públicos de um domínio.",
                emoji="📋",
                value="whois"
            ),
            discord.SelectOption(
                label="Scan URL",
                description="Analisar informações públicas de uma página.",
                emoji="🌎",
                value="scan"
            ),
            discord.SelectOption(
                label="Subdomínios",
                description="Consultar subdomínios de um domínio.",
                emoji="🌐",
                value="subdominios"
            ),
            discord.SelectOption(
                label="CNPJ",
                description="Consultar informações de um CNPJ.",
                emoji="🏢",
                value="cnpj"
            ),
            discord.SelectOption(
                label="Ip/DNS de um Site",
                description="Consultar informações IP, DNS de 1 site ou domínio.",
                emoji="🌐",
                value="site_ip_dns"
            ),
            discord.SelectOption(
                label="Username Check",
                description="Consultar informações de Usuários.",
                emoji="📁",
                value="usercheck"
            ),
            discord.SelectOption(
                label="Análise Facial",
                description="Realizar análise facial de uma imagem.",
                emoji="📷",
                value="facial"
            ),
        ]

        super().__init__(
            placeholder="Selecione o tipo de atendimento",
            options=options,
            custom_id="painel_select",
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        ativa, tempo = verificar_e_limpar_key(user_id)

        if not ativa:
            tempo_exibicao = "Não possui uma Key ativa."
            return await interaction.response.send_message(
                f"🚫 **Acesso Negado!**\n",
                "Você não possui uma Key ativa para utilizar as consultas.",
                ephemeral=True,
            )
        escolha = self.values[0]


        if escolha == "cep":
            await interaction.response.send_modal(
                CEPModal()
            )

        elif escolha == "ip":
            await interaction.response.send_modal(
                IPModal()
            )

        elif escolha == "dns":
            await interaction.response.send_modal(
                DNSModal()
            )

        elif escolha == "whois":
            await interaction.response.send_modal(
                WhoisModal()
            )

        elif escolha == "scan":
            await interaction.response.send_modal(
                ScanModal()
            )

        elif escolha == "subdominios":
            await interaction.response.send_modal(
                SubdominiosModal()
            )

        elif escolha == "cnpj":
            await interaction.response.send_modal(
                CnpjModal()
            )
        elif escolha == "site_ip_dns":
            await interaction.response.send_modal(
                SiteIpDnsModal()
            )
        elif escolha == "usercheck":
            await interaction.response.send_modal(
                UserModal()
            )
        elif escolha == "facial":
            await interaction.response.send_modal(
                BuscarRostoModal()
            )


class PainelView(View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PainelSelect())

# ============================================================
# BOT com as sistema de keys 
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

class ConsultaBot(discord.Client):

    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.add_view(PainelView())


        synced = await self.tree.sync()
        print(f"[LOG] {len(synced)} comandos sincronizados com o Discord!")

    async def on_ready(self):
        print(f"Bot conectado como {self.user}")
        print(f"ID: {self.user.id}")


bot = ConsultaBot()


ARQUIVO_KEYS = "keys.json"


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
        json.dump(dados, f, indent=4, ensure_ascii=False)


def verificar_e_limpar_key(user_id: str):
    
    dados = carregar_dados()
    user_info = dados.get("usuarios", {}).get(user_id)

    if not user_info:
        return False, "Você não possui nenhuma Key ativa."

    if user_info.get("tipo") == "lifetime":
        return True, "Permanente (Lifetime)"

    expira_em = user_info.get("expira_em")
    if not expira_em or expira_em == "lifetime":
        return True, "Permanente (Lifetime)"

    try:
        data_expira = datetime.fromisoformat(expira_em)
    except ValueError:
        return False, "Data de expiração inválida."

    agora = datetime.utcnow()

    if agora > data_expira:
        del dados["usuarios"][user_id]
        salvar_dados(dados)
        return False, "Sua Key expirou!"

    tempo_restante = data_expira - agora
    dias = tempo_restante.days
    horas, resto = divmod(tempo_restante.seconds, 3600)
    minutos, _ = divmod(resto, 60)

    texto_restante = f"{dias}d {horas}h {minutos}m"
    return True, texto_restante


# ============================================================
# /painel
# ============================================================
ID_CARGO_PERMITIDO = 1553904820249956437

@bot.tree.command(name="painel", description="Abre o painel de consultas")
async def painel(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    # 1. Verificação do Cargo
    cargos_usuario = [role.id for role in interaction.user.roles]
    if ID_CARGO_PERMITIDO not in cargos_usuario:
        return await interaction.response.send_message(
            "❌ **Acesso Negado!** Você não possui o cargo necessário para utilizar o painel.",
            ephemeral=True,
        )

    # 2. Verificação da Key
    ativa, tempo = verificar_e_limpar_key(user_id)
    if not ativa:
        return await interaction.response.send_message(
            f"🚫 **Acesso Negado!** {tempo}\n"
            "Compre a key para ativar seu acesso ao painel.",
            ephemeral=True,
        )

    # 3. Envio do Painel caso passe nas duas verificações
    embed = criar_embed(
        "🛠️ Painel de Consultas",
        " **Fynot Search — um painel de consultas e OSINT completo: CNPJ, CEP, Whois, Subdominios, Vazamentos, IP, Reconhecimento Facial,  e muito mais, tudo em um só lugar.**\n\n",
        discord.Color.blurple(),
    )

    await interaction.response.send_message(
        embed=embed, view=PainelView(), ephemeral=False
    )


# ============================================================
# /resgatarkey
# ============================================================

@bot.tree.command(
    name="resgatarkey",
    description="Resgata uma key de acesso para liberar o painel",
)
async def resgatarkey(interaction: discord.Interaction, key: str):
    key = key.strip()
    user_id = str(interaction.user.id)
    dados = carregar_dados()

    
    user_info = dados.get("usuarios", {}).get(user_id)
    if user_info:
        expira_em = user_info.get("expira_em")
        if expira_em == "lifetime":
            return await interaction.response.send_message(
                "❌ Você já possui acesso Vitalício (Lifetime) ativo!",
                ephemeral=True,
            )

        try:
            data_expira = datetime.fromisoformat(expira_em)
            if datetime.utcnow() < data_expira:
                return await interaction.response.send_message(
                    "❌ Você já possui uma Key ativa! Aguarde seu tempo expirar para resgatar outra.",
                    ephemeral=True,
                )
        except (ValueError, TypeError):
            pass

    
    if key not in dados["keys"]:
        return await interaction.response.send_message(
            "❌ Key inválida, inexistente ou já resgatada por outro usuário.",
            ephemeral=True,
        )

    
    info_key = dados["keys"].pop(key)
    tipo = info_key["tipo"]

    agora = datetime.utcnow()

    if tipo == "1d":
        expira = agora + timedelta(days=1)
        expira_str = expira.isoformat()
        texto_duracao = "1 Dia"
    elif tipo == "7d":
        expira = agora + timedelta(days=7)
        expira_str = expira.isoformat()
        texto_duracao = "7 Dias"
    elif tipo == "30d":
        expira = agora + timedelta(days=30)
        expira_str = expira.isoformat()
        texto_duracao = "30 Dias"
    elif tipo == "90d":
        expira = agora + timedelta(days=90)
        expira_str = expira.isoformat()
        texto_duracao = "90 Dias"
    else:
        expira_str = "lifetime"
        texto_duracao = "Vitalício (Lifetime)"

    
    dados["usuarios"][user_id] = {
        "key_resgatada": key,
        "tipo": tipo,
        "resgatada_em": agora.isoformat(),
        "expira_em": expira_str,
    }

    salvar_dados(dados)

    await interaction.response.send_message(
        f"✅ **Key Resgatada com Sucesso!**\n"
        f"🔑 **Key:** `{key}`\n"
        f"⏳ **Duração do Acesso:** `{texto_duracao}`\n\n",
        ephemeral=True,
    )

def obter_key_usuario(user_id: str):
    """
    Retorna os detalhes da key do usuário para o comando /minhakey.
    Retorna: (ativa: bool, key_codigo: str, tempo_restante: str)
    """
    dados = carregar_dados()
    user_info = dados.get("usuarios", {}).get(user_id)

    if not user_info:
        return False, None, None

    ativa, tempo_restante = verificar_e_limpar_key(user_id)
    if not ativa:
        return False, None, None

    key_codigo = user_info.get("key", "N/A")
    return True, key_codigo, tempo_restante


def resgatar_key(user_id: str, codigo_key: str):
    """
    Resgata uma key criada e vincula ao ID do usuário.
    Se o usuário já possuir dias ativos, o tempo é somado.
    """
    dados = carregar_dados()
    keys = dados.get("keys", {})

    if codigo_key not in keys:
        return False, "❌ Esta Key é inválida ou não existe."

    info_key = keys[codigo_key]

    if info_key.get("usada"):
        return False, "❌ Esta Key já foi utilizada."

    duracao_dias = info_key.get("dias", 30)
    tipo = info_key.get("tipo", "temp")

    agora = datetime.utcnow()
    user_info = dados.get("usuarios", {}).get(user_id)

    if tipo == "lifetime":
        dados["usuarios"][user_id] = {
            "key": codigo_key,
            "tipo": "lifetime",
            "expira_em": "lifetime"
        }
    else:
        # Se o usuário já tiver uma expiração ativa, soma os dias novos
        if user_info and user_info.get("tipo") != "lifetime":
            try:
                exp_atual = datetime.fromisoformat(user_info.get("expira_em"))
                base_calculo = exp_atual if exp_atual > agora else agora
            except (ValueError, TypeError):
                base_calculo = agora
        else:
            base_calculo = agora

        nova_expiracao = base_calculo + timedelta(days=duracao_dias)

        dados["usuarios"][user_id] = {
            "key": codigo_key,
            "tipo": "temp",
            "expira_em": nova_expiracao.isoformat()
        }

    # Marca a key como usada
    info_key["usada"] = True
    info_key["usada_por"] = user_id
    info_key["usada_em"] = agora.isoformat()

    salvar_dados(dados)
    return True, f"✅ Key de **{duracao_dias} dias** resgatada com sucesso!"


# ============================================================
# COMANDOS DO DISCORD
# ============================================================

@bot.tree.command(name="minhakey", description="Exibe a sua Key cadastrada e o status de acesso")
async def minhakey(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    ativa, nova_key, tempo = obter_key_usuario(user_id)

    if ativa:
        await interaction.response.send_message(
            f"🔑 **Sua Key:** `{nova_key}`\n"
            f"⏳ **Tempo restante:** `{tempo}`",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ **Você não possui nenhuma Key ativa vinculada à sua conta.**",
            ephemeral=True
        )

# ============================================================
# INICIAR
# ============================================================

if __name__ == "__main__":

    bot.run(
        DISCORD_TOKEN
    )
