import discord
from discord.ext import commands
import requests
from discord import app_commands
from discord.ui import Button, View, Select
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import random
import string
import asyncio
import os
from dotenv import load_dotenv
import re
from datetime import datetime, timezone, timedelta
import aiohttp
import time

load_dotenv()

# importa as credenciais do frirebase
cred = credentials.Certificate("./site-ffxiv-firebase-adminsdk-jew90-e78f4be266.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://site-ffxiv-default-rtdb.firebaseio.com/"
})

db_ref = db.reference()

#intents
intents = discord.Intents.all()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

async def verificar_usuario_existente(guild_id: str, discord_id: str) -> bool:
    """
    Verifica se um usuário já está registrado no servidor.
    Retorna True se o usuário já existe, False caso contrário.
    """
    try:
        # Verifica em ambas as categorias (membros e visitantes)
        membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get()
        if membros and isinstance(membros, dict):
            for membro in membros.values():
                if isinstance(membro, dict) and membro.get("discord_id") == discord_id:
                    return True
                    
        visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get()
        if visitantes and isinstance(visitantes, dict):
            for visitante in visitantes.values():
                if isinstance(visitante, dict) and visitante.get("discord_id") == discord_id:
                    return True
        
        return False
    except Exception as e:
        print(f"Erro ao verificar usuário existente: {e}")
        return False

# função que processa o registro
async def process_registro(interaction: discord.Interaction, lodestone_url: str):
    await interaction.response.defer(ephemeral=True)
    try:
        # Verifica se o usuário já está registrado
        guild_id = str(interaction.guild.id)
        discord_id = str(interaction.user.id)
        
        if await verificar_usuario_existente(guild_id, discord_id):
            await interaction.followup.send("Você já está registrado neste servidor! Não é possível fazer um novo registro.", ephemeral=True)
            return
            
        response = requests.get(lodestone_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            character_name = soup.find("p", class_="frame__chara__name")
            if character_name:
                nome_completo = character_name.text.strip().split(" ")
                nome = nome_completo[0]
                sobrenome = " ".join(nome_completo[1:]) if len(nome_completo) > 1 else ""
                free_company_div = soup.find("div", class_="character__freecompany__name")
                if free_company_div:
                    free_company_link = free_company_div.find("a")
                    if free_company_link:
                        free_company_href = free_company_link.get("href")
                        free_company_name = free_company_link.text.strip()
                    else:
                        free_company_href = None
                        free_company_name = None
                else:
                    free_company_href = None
                    free_company_name = None
                
                codigo_verificacao = 'owo-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                
                # Criar botão de verificação
                class VerificacaoView(View):
                    def __init__(self):
                        super().__init__(timeout=300.0)  # 5 minutos de timeout
                    
                    @discord.ui.button(label="Verificar!", style=discord.ButtonStyle.primary, emoji="<:petharumi2:1310712833625034872>")
                    async def verificar_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                        await button_interaction.response.defer(ephemeral=True)
                        try:
                            response = requests.get(lodestone_url)
                            if response.status_code == 200:
                                soup = BeautifulSoup(response.content, "html.parser")
                                descricao_personagem = soup.find("div", class_="character__selfintroduction")
                                if descricao_personagem:
                                    descricao_texto = descricao_personagem.text.strip()
                                    if codigo_verificacao in descricao_texto:
                                        guild_id = interaction.guild.id
                                        guild_name = interaction.guild.name
                                        user_data = {
                                            "nome": nome,
                                            "sobrenome": sobrenome,
                                            "free_company": free_company_name,
                                            "discord_id": str(interaction.user.id),
                                            "discord_name": str(interaction.user),
                                            "lodestone_url": lodestone_url,
                                            "registered_at": {".sv": "timestamp"},
                                            "message_count": 0,
                                            "last_message": {".sv": "timestamp"}
                                        }

                                        cargos = db_ref.child("servidores").child(str(interaction.guild.id)).get()
                                        if cargos:
                                            cargo_membro_id = int(cargos.get("cargo_membro"))
                                            cargo_visitante_id = int(cargos.get("cargo_visitante"))
                                            cargo_membro = discord.utils.get(interaction.guild.roles, id=cargo_membro_id)
                                            cargo_visitante = discord.utils.get(interaction.guild.roles, id=cargo_visitante_id)
                                            free_company_configurada_id = cargos.get("free_company_id")
                                            
                                            if free_company_href == f"/lodestone/freecompany/{free_company_configurada_id}/":
                                                # Registra como membro
                                                db_ref.child("servidores").child(str(guild_id)).child("usuarios_membros").push(user_data)
                                                await interaction.user.add_roles(cargo_membro)
                                                await interaction.user.remove_roles(cargo_visitante)
                                                mensagem = f"Parabéns {nome} {sobrenome}! Você foi registrado(a) como membro da FC e recebeu o cargo de Membro! <:limaheart2:1310712852008403064>"
                                            else:
                                                # Registra como visitante
                                                db_ref.child("servidores").child(str(guild_id)).child("usuarios_visitantes").push(user_data)
                                                await interaction.user.add_roles(cargo_visitante)
                                                await interaction.user.remove_roles(cargo_membro)
                                                mensagem = f"Parabéns {nome} {sobrenome}! Você foi registrado(a) como visitante. <:harumibleh:1310712824120475650>\nJá pensou em entrar na FC? <:facalima2:1310706236647407776> \n"
                                                mensagem += f"\nVocê ia receber um cargo maneiro de membro :3 <:facalima2:1310706236647407776> \nCaso você tenha entrado recentemente na FC, seu cargo será atualizado em algumas horas. <:limaheart2:1310712852008403064>"
                                            
                                            novo_apelido = f"{nome} {sobrenome}"
                                            try:
                                                await interaction.user.edit(nick=novo_apelido)
                                                mensagem += "\nSeu apelido foi atualizado!"
                                            except discord.errors.Forbidden:
                                                mensagem += "\nSeu apelido não pôde ser alterado, verifique as permissões do bot."
                                            except Exception as e:
                                                mensagem += f"\nOcorreu um erro ao alterar o apelido: {e}"
                                            
                                            try:
                                                # Envia a mensagem de sucesso na DM
                                                await interaction.user.send(mensagem)
                                                # Envia uma mensagem curta no canal
                                                await button_interaction.followup.send("Registro concluído com sucesso! Verifique suas mensagens privadas para mais detalhes.", ephemeral=True)
                                            except discord.Forbidden:
                                                # Se não conseguir enviar DM, envia tudo no canal mesmo
                                                await button_interaction.followup.send(f"{mensagem}\n\n(Esta mensagem está sendo mostrada aqui porque suas mensagens privadas estão desativadas)", ephemeral=True)
                                        else:
                                            await button_interaction.followup.send("Free Company não configurada. Use /configurar_cargos para definir a Free Company.", ephemeral=True)
                                    else:
                                        await button_interaction.followup.send("Código de verificação não encontrado na sua descrição. Tente novamente.", ephemeral=True)
                                else:
                                    await button_interaction.followup.send("Não foi possível encontrar a descrição do seu personagem. Verifique se a URL está correta.", ephemeral=True)
                            else:
                                await button_interaction.followup.send("Ocorreu um erro ao acessar o Lodestone. Verifique a URL e tente novamente.", ephemeral=True)
                        except Exception as e:
                            print(f"Erro ao verificar usuário: {e}")
                            await button_interaction.followup.send("Ocorreu um erro ao verificar o registro. Tente novamente mais tarde.", ephemeral=True)

                    async def on_timeout(self):
                        try:
                            msg = await interaction.followup.send("Tempo de verificação esgotado. Tente se registrar novamente.", ephemeral=True)
                            await asyncio.sleep(30)
                            try:
                                await msg.delete()
                            except:
                                pass
                        except:
                            pass

                view = VerificacaoView()
                await interaction.followup.send(
                    f"Por favor, adicione o seguinte código à sua descrição no Lodestone:\n\n**{codigo_verificacao}**\n\nDepois de adicionar o código, clique no botão abaixo para verificar.",
                    view=view,
                    ephemeral=True
                )
            else:
                await interaction.followup.send("Perfil não encontrado no Lodestone. Verifique a URL e tente novamente.", ephemeral=True)
        else:
            await interaction.followup.send("Ocorreu um erro ao acessar o Lodestone. Verifique a URL e tente novamente.", ephemeral=True)
    except Exception as e:
        print(f"Erro ao registrar usuário: {e}")
        await interaction.followup.send("Ocorreu um erro ao registrar o usuário. Tente novamente mais tarde.", ephemeral=True)

# comando de registrar com a lodestone
@bot.tree.command(name="registrar", description="Registra um novo usuário.")
async def registrar(interaction: discord.Interaction, lodestone_url: str):
    await process_registro(interaction, lodestone_url)

#comando para configurar cargos e FC para um discord "novo"
@bot.tree.command(name="configurar_cargos", description="Configura os cargos e a Free Company para membros e visitantes.")
async def configurar_cargos(interaction: discord.Interaction, cargo_membro: discord.Role, cargo_visitante: discord.Role, free_company_id: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Você não tem permissão para usar este comando.", ephemeral=True)
        return
    await interaction.response.defer()
    try:
        db_ref.child("servidores").child(str(interaction.guild.id)).set({
            "cargo_membro": str(cargo_membro.id),
            "cargo_visitante": str(cargo_visitante.id),
            "free_company_id": free_company_id
        })
        await interaction.edit_original_response(content="Cargos e Free Company configurados com sucesso!")
    except Exception as e:
        print(f"Erro ao configurar cargos e Free Company: {e}")
        await interaction.edit_original_response(content="Ocorreu um erro ao configurar os cargos e a Free Company.")

# função que processa o registro sem FFXIV
async def process_registro_sem_ffxiv(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        # Verifica se o usuário já está registrado
        guild_id = str(interaction.guild.id)
        discord_id = str(interaction.user.id)
        
        if await verificar_usuario_existente(guild_id, discord_id):
            await interaction.followup.send("Você já está registrado neste servidor! Não é possível fazer um novo registro.", ephemeral=True)
            return
            
        cargos = db_ref.child("servidores").child(str(guild_id)).get()
        if cargos and cargos.get("cargo_visitante"):
            cargo_visitante_id = int(cargos.get("cargo_visitante"))
            cargo_visitante = discord.utils.get(interaction.guild.roles, id=cargo_visitante_id)
            
            # Registra o usuário como visitante sem FFXIV
            user_data = {
                "discord_id": str(interaction.user.id),
                "discord_name": str(interaction.user),
                "tipo": "sem_ffxiv",
                "registered_at": {".sv": "timestamp"}
            }
            db_ref.child("servidores").child(str(guild_id)).child("usuarios_visitantes").push(user_data)
            
            await interaction.user.add_roles(cargo_visitante)
            msg = await interaction.followup.send("Registro concluído com sucesso! <:petharumi2:1310712833625034872>", ephemeral=True)
            await asyncio.sleep(30)
            try:
                await msg.delete()
            except:
                pass
        else:
            msg = await interaction.followup.send("Cargo de visitante não configurado. Contate um administrador para configurar os cargos.", ephemeral=True)
            await asyncio.sleep(30)
            try:
                await msg.delete()
            except:
                pass
    except Exception as e:
        print(f"Erro ao registrar usuário sem FFXIV: {e}")
        msg = await interaction.followup.send("Ocorreu um erro ao registrar o usuário. Tente novamente mais tarde.", ephemeral=True)
        await asyncio.sleep(30)
        try:
            await msg.delete()
        except:
            pass

# comando de registro sem FFXIV
@bot.tree.command(name="registro_sem_ffxiv", description="Registra um usuário que não joga FFXIV.")
async def registro_sem_ffxiv(interaction: discord.Interaction):
    await process_registro_sem_ffxiv(interaction)

# Verifica se o bot está trabalhando normalmente
@bot.event
async def on_ready():
    activity = discord.Activity(name='a conversa de vocês', type=discord.ActivityType.listening)
    await bot.change_presence(activity=activity)
    print(f'{bot.user} está online!')
    
    # Recupera e recria as mensagens de registro
    try:
        mensagens = db_ref.child("mensagens_registro").get()
        if mensagens:
            for guild_id, data in mensagens.items():
                try:
                    channel = bot.get_channel(int(data["channel_id"]))
                    if channel:
                        try:
                            message = await channel.fetch_message(int(data["message_id"]))
                            if message:
                                # Recria o embed e view
                                embed = discord.Embed(
                                    title="Bem-vindo(a)! Eu sou o bot de regitro da FC OwO...",
                                    description="Antes de se registrar, lembre-se de ler nossas ⁠[Regras](your_rules_url_here). \n<:harumibleh:1310712824120475650>\nClique em \"Começar\" Para começar seu registro!",
                                    color=discord.Color.pink()
                                )
                                view = RegistroView()
                                await message.edit(embed=embed, view=view)
                        except discord.NotFound:
                            # Se a mensagem não existir mais, cria uma nova
                            embed = discord.Embed(
                                    title="Bem-vindo(a)! Eu sou o bot de regitro da FC OwO...",
                                    description="Antes de se registrar, lembre-se de ler nossas ⁠[Regras](your_rules_url_here). \n<:harumibleh:1310712824120475650>\nClique em \"Começar\" Para começar seu registro!",
                                    color=discord.Color.pink()
                                )
                            view = RegistroView()
                            new_message = await channel.send(embed=embed, view=view)
                            # Atualiza o ID da mensagem no Firebase
                            db_ref.child("mensagens_registro").child(guild_id).update({
                                "message_id": str(new_message.id)
                            })
                except Exception as e:
                    print(f"Erro ao recuperar mensagem para o servidor {guild_id}: {e}")
    except Exception as e:
        print(f"Erro ao recuperar mensagens de registro: {e}")

    # Recupera e reinicia as roletas ativas
    try:
        roletas = db_ref.child("roletas_ativas").get()
        if roletas:
            if not hasattr(bot, 'auto_roulette'):
                bot.auto_roulette = AutoRoulette(bot)
                
            for guild_id, data in roletas.items():
                try:
                    channel = bot.get_channel(int(data["channel_id"]))
                    if channel:
                        print(f"Reiniciando roleta no servidor {guild_id}")
                        # Limpa mensagens antigas antes de reiniciar
                        await bot.auto_roulette.cleanup_old_messages(channel, guild_id)
                        bot.loop.create_task(bot.auto_roulette.run_roulette(channel, guild_id))
                except Exception as e:
                    print(f"Erro ao recuperar roleta para o servidor {guild_id}: {e}")
    except Exception as e:
        print(f"Erro ao recuperar roletas ativas: {e}")

    try:
        synced = await bot.tree.sync()
        print(f'Sincronizou {len(synced)} comando(s) /')
    except Exception as e:
        print(f'Erro ao sincronizar comandos: {e}')

class RegistroView(View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Começar", style=discord.ButtonStyle.primary, emoji="<:facalima2:1310706236647407776>")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Criar o menu de seleção
        select = Select(
            placeholder="Escolha uma opção de registro",
            options=[
                discord.SelectOption(
                    label="Registrar com FFXIV",
                    description="Para jogadores com conta no FFXIV",
                    value="registrar_ffxiv"
                ),
                discord.SelectOption(
                    label="Registrar sem FFXIV",
                    description="Para visitantes sem conta no FFXIV",
                    value="registrar_sem_ffxiv"
                )
            ]
        )
        
        async def select_callback(interaction: discord.Interaction):
            if select.values[0] == "registrar_ffxiv":
                await interaction.response.send_modal(RegistroModal())
            else:
                await process_registro_sem_ffxiv(interaction)
        
        select.callback = select_callback
        view = View(timeout=None)
        view.add_item(select)
        response = await interaction.response.send_message("Escolha como deseja se registrar:", view=view, ephemeral=True)
        # Não deletamos esta mensagem pois ela contém a interação

class RegistroModal(discord.ui.Modal, title="Registro FFXIV"):
    lodestone_url = discord.ui.TextInput(
        label="URL do seu perfil na Lodestone",
        placeholder="https://na.finalfantasyxiv.com/lodestone/character/...",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await process_registro(interaction, str(self.lodestone_url))

@bot.tree.command(name="setup", description="Configura a mensagem de registro do servidor")
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    embed = discord.Embed(
                title="Bem-vindo(a)! Eu sou o bot de regitro da FC OwO...",
                description="Antes de se registrar, lembre-se de ler nossas ⁠[Regras](your_rules_url_here). \n<:harumibleh:1310712824120475650>\nClique em \"Começar\" Para começar seu registro!",
                color=discord.Color.pink()
                )
    
    view = RegistroView()
    message = await interaction.channel.send(embed=embed, view=view)
    
    # Salva a informação da mensagem no Firebase
    db_ref.child("mensagens_registro").child(str(interaction.guild.id)).set({
        "channel_id": str(message.channel.id),
        "message_id": str(message.id)
    })
    
    msg = await interaction.response.send_message("Mensagem de registro configurada com sucesso!", ephemeral=True)
    await asyncio.sleep(30)
    try:
        await msg.delete()
    except:
        pass

@bot.tree.command(name="migrar_usuarios", description="Migra usuários existentes para a nova estrutura do banco de dados")
@app_commands.default_permissions(administrator=True)
async def migrar_usuarios(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        # Busca todos os usuários existentes
        usuarios_antigos = db_ref.child("usuarios").get()
        if not usuarios_antigos:
            await interaction.followup.send("Não foram encontrados usuários para migrar.", ephemeral=True)
            return

        # Contador de usuários migrados
        migrados = 0
        
        for user_id, user_data in usuarios_antigos.items():
            guild_id = str(user_data.get("guild_id"))
            
            # Verifica se o servidor ainda existe no bot
            guild = interaction.client.get_guild(int(guild_id))
            if not guild:
                continue
                
            # Busca o membro no servidor
            try:
                # Na estrutura antiga não temos o discord_id, então vamos tentar encontrar
                # o membro pelo nome completo
                nome_completo = f"{user_data.get('nome')} {user_data.get('sobrenome')}".strip()
                member = None
                
                # Busca todos os membros do servidor
                async for guild_member in guild.fetch_members():
                    # Verifica se o nickname ou o nome do usuário corresponde
                    if (guild_member.nick and guild_member.nick.strip() == nome_completo) or \
                       guild_member.name.strip() == nome_completo:
                        member = guild_member
                        break
                
                if not member:
                    continue
                    
            except Exception as e:
                print(f"Erro ao buscar membro {nome_completo}: {e}")
                continue
                
            # Prepara os dados do usuário
            new_user_data = {
                "nome": user_data.get("nome"),
                "sobrenome": user_data.get("sobrenome"),
                "free_company": user_data.get("free_company"),
                "discord_id": str(member.id),
                "discord_name": str(member),
                "registered_at": {".sv": "timestamp"},
                "migrated_from": user_id  # Referência ao ID antigo
            }
            
            # Verifica os cargos do servidor
            cargos = db_ref.child("servidores").child(guild_id).get()
            if cargos:
                cargo_membro_id = int(cargos.get("cargo_membro"))
                cargo_visitante_id = int(cargos.get("cargo_visitante"))
                
                # Verifica qual cargo o usuário tem
                if any(role.id == cargo_membro_id for role in member.roles):
                    # Usuário é membro
                    db_ref.child("servidores").child(guild_id).child("usuarios_membros").push(new_user_data)
                elif any(role.id == cargo_visitante_id for role in member.roles):
                    # Usuário é visitante
                    db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").push(new_user_data)
                    
                migrados += 1
        
        # Remove os dados antigos após a migração bem-sucedida
        if migrados > 0:
            db_ref.child("usuarios").delete()
            await interaction.followup.send(f"Migração concluída! {migrados} usuários foram migrados para a nova estrutura.", ephemeral=True)
        else:
            await interaction.followup.send("Nenhum usuário foi migrado. Verifique se há usuários válidos para migração.", ephemeral=True)
            
    except Exception as e:
        print(f"Erro durante a migração: {e}")
        await interaction.followup.send("Ocorreu um erro durante a migração dos usuários.", ephemeral=True)

async def remover_registro_usuario(guild_id: str, discord_id: str) -> tuple[bool, str, str]:
    """
    Remove o registro de um usuário do banco de dados.
    Retorna uma tupla com:
    - bool: True se removido com sucesso, False caso contrário
    - str: Tipo de usuário que foi removido ('membro' ou 'visitante')
    - str: Nome do usuário que foi removido
    """
    try:
        # Verifica em membros
        membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get()
        if membros:
            for key, membro in membros.items():
                if membro.get("discord_id") == discord_id:
                    db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key).delete()
                    nome_completo = f"{membro.get('nome', '')} {membro.get('sobrenome', '')}".strip()
                    return True, "membro", nome_completo or membro.get("discord_name", "Usuário")
        
        # Verifica em visitantes
        visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get()
        if visitantes:
            for key, visitante in visitantes.items():
                if visitante.get("discord_id") == discord_id:
                    db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key).delete()
                    nome_completo = f"{visitante.get('nome', '')} {visitante.get('sobrenome', '')}".strip()
                    return True, "visitante", nome_completo or visitante.get("discord_name", "Usuário")
        
        return False, "", ""
    except Exception as e:
        print(f"Erro ao remover registro do usuário: {e}")
        return False, "", ""

@bot.tree.command(name="remover_registro", description="Remove o registro de um usuário do servidor")
@app_commands.default_permissions(administrator=True)
async def remover_registro(interaction: discord.Interaction, usuario: discord.Member):
    """
    Remove o registro de um usuário do servidor.
    Parâmetros:
        usuario: O usuário que terá o registro removido (mencione o usuário)
    """
    await interaction.response.defer(ephemeral=True)
    try:
        guild_id = str(interaction.guild.id)
        discord_id = str(usuario.id)
        
        # Tenta remover o registro
        removido, tipo, nome = await remover_registro_usuario(guild_id, discord_id)
        
        if removido:
            # Remove os cargos relacionados
            cargos = db_ref.child("servidores").child(guild_id).get()
            if cargos:
                cargo_membro_id = int(cargos.get("cargo_membro"))
                cargo_visitante_id = int(cargos.get("cargo_visitante"))
                
                cargo_membro = discord.utils.get(interaction.guild.roles, id=cargo_membro_id)
                cargo_visitante = discord.utils.get(interaction.guild.roles, id=cargo_visitante_id)
                
                if cargo_membro and cargo_membro in usuario.roles:
                    await usuario.remove_roles(cargo_membro)
                if cargo_visitante and cargo_visitante in usuario.roles:
                    await usuario.remove_roles(cargo_visitante)
            
            await interaction.followup.send(
                f"Registro de {nome} removido com sucesso!\n"
                f"Tipo de registro removido: {tipo}\n"
                f"Os cargos relacionados também foram removidos.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"Não foi encontrado nenhum registro para {usuario.display_name} neste servidor.",
                ephemeral=True
            )
            
    except Exception as e:
        print(f"Erro ao executar comando de remover registro: {e}")
        await interaction.followup.send(
            "Ocorreu um erro ao tentar remover o registro do usuário.",
            ephemeral=True
        )

async def fetch_lodestone_data(lodestone_url: str) -> dict:
    """Busca dados do personagem no Lodestone"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(lodestone_url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    # Busca a imagem do personagem
                    character_image = soup.find("div", class_="frame__chara__face").find("img")
                    image_url = character_image["src"] if character_image else None
                    
                    # Busca o ID do personagem da URL
                    character_id = re.search(r'/lodestone/character/(\d+)/', lodestone_url)
                    character_id = character_id.group(1) if character_id else None

                    # Busca o nome do personagem
                    character_name = soup.find("p", class_="frame__chara__name")
                    character_name = character_name.text.strip() if character_name else None
                    
                    return {
                        "image_url": image_url,
                        "character_id": character_id,
                        "character_name": character_name,
                        "lodestone_url": lodestone_url,
                        "tomestone_url": f"https://tomestone.gg/character/{character_id}/{character_name.replace(' ', '-').lower()}" if character_id and character_name else None
                    }
    except Exception as e:
        print(f"Erro ao buscar dados do Lodestone: {e}")
        return None

def calculate_level(message_count: int) -> tuple[int, int, int]:
    """
    Calcula o nível baseado no número de mensagens.
    Retorna: (nível, xp_atual_no_nivel, xp_próximo_nível)
    """
    base_xp = 100  # XP base para o primeiro nível
    level = 1
    xp_total = message_count * 10  # Cada mensagem vale 10 XP
    xp_for_current = 0
    
    while True:
        xp_for_next = int(base_xp * (level ** 1.5))  # Convertendo para inteiro
        if xp_total < xp_for_next:
            # Retorna o XP dentro do nível atual, não o total
            xp_in_current_level = int(xp_total - xp_for_current)  # Convertendo para inteiro
            return level, xp_in_current_level, int(xp_for_next - xp_for_current)
        xp_for_current = xp_for_next
        level += 1

async def check_level_up(message, old_message_count: int, new_message_count: int) -> tuple[bool, int, int]:
    """
    Verifica se o usuário subiu de nível.
    Retorna: (subiu_de_nivel, nivel_antigo, nivel_novo)
    """
    _, _, old_next_level = calculate_level(old_message_count)
    new_level, new_xp, new_next_level = calculate_level(new_message_count)
    old_level, old_xp, _ = calculate_level(old_message_count)
    
    if new_level > old_level:
        return True, old_level, new_level
    return False, old_level, old_level

def calculate_coins_earned(message: discord.Message) -> int:
    """
    Calcula quantos OwO Coins o usuário ganhou com a mensagem.
    Base: 1 coin
    Com link: +5 coins
    Com imagem: +5 coins
    Exemplo: Mensagem com link e imagem = 11 coins (1 base + 5 link + 5 imagem)
    """
    coins = 1  # Moeda base por mensagem
    
    # Verifica se tem links
    has_links = bool(re.search(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content))
    if has_links:
        coins += 5
    
    # Verifica se tem imagens/anexos
    if message.attachments:
        coins += 5
    
    return coins

# Dicionário para rastrear mensagens de spam
user_message_timestamps = {}

def check_spam_cooldown(user_id: str) -> bool:
    """
    Verifica se o usuário está em cooldown por spam.
    Retorna True se o usuário está em cooldown, False caso contrário.
    """
    current_time = time.time()
    
    if user_id not in user_message_timestamps:
        user_message_timestamps[user_id] = []
    
    # Remove timestamps mais antigos que 10 segundos
    user_message_timestamps[user_id] = [ts for ts in user_message_timestamps[user_id] if current_time - ts < 5]
    
    # Se tiver 5 ou mais mensagens nos últimos 10 segundos, está em cooldown
    if len(user_message_timestamps[user_id]) >= 5:
        return True
    
    # Adiciona o timestamp atual
    user_message_timestamps[user_id].append(current_time)
    return False

@bot.event
async def on_message(message):
    if message.author.bot:
        return
        
    try:
        # Verifica se o usuário está em cooldown por spam
        if check_spam_cooldown(str(message.author.id)):
            return
            
        # Incrementa o contador de mensagens do usuário
        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        
        # Atualiza o progresso da missão de mensagens
        await update_quest_progress(guild_id, user_id, "message_count")
        
        # Busca em ambas as categorias
        user_ref = None
        user_type = None
        user_data = None
        
        membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get()
        if membros:
            for key, membro in membros.items():
                if membro.get("discord_id") == user_id:
                    user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key)
                    user_type = "membro"
                    user_data = membro
                    break
        
        if not user_ref:
            visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get()
            if visitantes:
                for key, visitante in visitantes.items():
                    if visitante.get("discord_id") == user_id:
                        user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key)
                        user_type = "visitante"
                        user_data = visitante
                        break
        
        if user_ref and user_data:
            # Pega a contagem atual de mensagens e coins
            current_count = user_data.get("message_count", 0)
            current_coins = user_data.get("owo_coins", 0)
            new_count = current_count + 1
            
            # Calcula os coins ganhos
            coins_earned = calculate_coins_earned(message)
            new_coins = current_coins + coins_earned
            
            # Verifica se subiu de nível
            leveled_up, old_level, new_level = await check_level_up(message, current_count, new_count)
            
            # Atualiza o contador e os coins
            user_ref.update({
                "message_count": new_count,
                "last_message": {".sv": "timestamp"},
                "owo_coins": new_coins
            })
            
            # Se subiu de nível, envia a mensagem de parabéns
            if leveled_up:
                # Calcula XP atual e próximo nível
                _, current_xp, next_level_xp = calculate_level(new_count)
                
                # Adiciona 20 coins de brinde por level up
                bonus_coins = 20
                new_coins = new_coins + bonus_coins
                user_ref.update({
                    "owo_coins": new_coins
                })
                
                embed = discord.Embed(
                    title="<:petharumi2:1310712833625034872> Level Up! <:petharumi2:1310712833625034872>",
                    description=f"Parabéns {message.author.mention}!",
                    color=get_user_embed_color(user_data)
                )
                
                # Usa o avatar do Discord
                embed.set_thumbnail(url=message.author.display_avatar.url)
                
                embed.add_field(
                    name="Novo Nível",
                    value=f"Você alcançou o nível **{new_level}**! <:limaheart2:1310712852008403064>",
                    inline=False
                )
                
                embed.add_field(
                    name="Progresso",
                    value=f"XP: {current_xp}/{next_level_xp}",
                    inline=False
                )

                embed.add_field(
                    name="OwO Coins",
                    value=f"Você tem **{new_coins}** <:owocoin:1364995129022349382>\n*+{bonus_coins} coins de brinde por subir de nível!*",
                    inline=False
                )
                
                # Envia o embed no canal onde a mensagem foi enviada
                await message.channel.send(embed=embed)
                
    except Exception as e:
        print(f"Erro ao processar mensagem: {e}")

def get_user_embed_color(user_data: dict) -> discord.Color:
    """
    Retorna a cor personalizada do usuário ou a cor padrão se não tiver uma.
    """
    try:
        if "embed_color" in user_data:
            return discord.Color(int(user_data["embed_color"][1:], 16))
    except:
        pass
    return discord.Color.blue()  # Cor padrão

@bot.tree.command(name="profile", description="Mostra seu perfil no servidor")
async def profile(interaction: discord.Interaction, usuario: discord.Member = None):
    """
    Mostra o perfil de um usuário no servidor.
    Se nenhum usuário for especificado, mostra seu próprio perfil.
    """
    await interaction.response.defer()
    try:
        target_user = usuario or interaction.user
        guild_id = str(interaction.guild.id)
        user_id = str(target_user.id)
        
        # Busca dados do usuário
        user_data = None
        user_type = None
        
        # Procura em membros
        membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get()
        if membros:
            for membro in membros.values():
                if membro.get("discord_id") == user_id:
                    user_data = membro
                    user_type = "Membro"
                    break
        
        # Se não encontrou em membros, procura em visitantes
        if not user_data:
            visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get()
            if visitantes:
                for visitante in visitantes.values():
                    if visitante.get("discord_id") == user_id:
                        user_data = visitante
                        user_type = "Visitante"
                        break
        
        if not user_data:
            await interaction.followup.send("Você não está registrado no servidor. Entre em contato com um administrador para ser registrado.", ephemeral=True)
            return
        
        # Calcula nível e XP
        message_count = user_data.get("message_count", 0)
        level, current_xp, next_level_xp = calculate_level(message_count)
        
        # Pega os coins
        coins = user_data.get("owo_coins", 0)
        
        # Busca dados do Lodestone se disponível
        lodestone_data = None
        if "lodestone_url" in user_data:
            lodestone_data = await fetch_lodestone_data(user_data["lodestone_url"])
        
        # Calcula tempo no servidor
        joined_at = target_user.joined_at
        if joined_at is None:
            days_in_server = 0
        else:
            # Certifica que ambas as datas estão em UTC
            if joined_at.tzinfo is None:
                joined_at = joined_at.replace(tzinfo=timezone.utc)
            current_time = datetime.now(timezone.utc)
            time_in_server = current_time - joined_at
            days_in_server = time_in_server.days
        
        # Determina o cargo especial
        special_role = ""
        if str(target_user.id) == "your_id_here":  # Seu ID
            special_role = "👑 Owner"
        elif target_user.guild_permissions.administrator:
            special_role = "⚡ Administrador"
        
        # Usa a cor personalizada do usuário
        embed = discord.Embed(
            title=f"Perfil de {target_user.display_name}",
            color=get_user_embed_color(user_data)
        )
        
        # Usa o avatar do Discord
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # Informações básicas
        status_text = f"**Tipo:** {user_type}"
        if special_role:
            status_text = f"**Cargo:** {special_role}\n{status_text}"
            
        status_text += f"\n**Nível:** {level}\n**XP:** {current_xp}/{next_level_xp}\n**OwO Coins:** {coins} <:owocoin:1364995129022349382>"
        
        embed.add_field(
            name="Status",
            value=status_text,
            inline=False
        )
        
        embed.add_field(
            name="Estatísticas",
            value=f"**Tempo no Servidor:** {days_in_server} dias\n**Mensagens Enviadas:** {message_count}",
            inline=False
        )
        
        # Links (se disponível)
        if lodestone_data:
            links = []
            if lodestone_data["lodestone_url"]:
                links.append(f"[Lodestone]({lodestone_data['lodestone_url']})")
            if lodestone_data["tomestone_url"]:
                links.append(f"[Tomestone.gg]({lodestone_data['tomestone_url']})")
            
            if links:
                embed.add_field(
                    name="Links",
                    value=" | ".join(links),
                    inline=False
                )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Erro ao mostrar perfil: {e}")
        await interaction.followup.send("Ocorreu um erro ao tentar mostrar o perfil.", ephemeral=True)

@bot.tree.command(name="coins", description="Mostra seus OwO Coins ou de outro usuário")
async def coins(interaction: discord.Interaction, usuario: discord.Member = None):
    """
    Mostra quantos OwO Coins um usuário tem.
    Se nenhum usuário for especificado, mostra seus próprios coins.
    """
    await interaction.response.defer()
    try:
        target_user = usuario or interaction.user
        guild_id = str(interaction.guild.id)
        user_id = str(target_user.id)
        
        # Busca dados do usuário
        user_data = None
        
        # Procura em membros
        membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get()
        if membros:
            for membro in membros.values():
                if membro.get("discord_id") == user_id:
                    user_data = membro
                    break
        
        # Se não encontrou em membros, procura em visitantes
        if not user_data:
            visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get()
            if visitantes:
                for visitante in visitantes.values():
                    if visitante.get("discord_id") == user_id:
                        user_data = visitante
                        break
        
        if not user_data:
            await interaction.followup.send("Este usuário não está registrado no servidor.", ephemeral=True)
            return
        
        coins = user_data.get("owo_coins", 0)
        
        embed = discord.Embed(
            title="OwO Coins",
            description=f"Coins de {target_user.mention}",
            color=get_user_embed_color(user_data)
        )
        
        # Usa o avatar do Discord
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        embed.add_field(
            name="Total de Coins",
            value=f"**{coins}** <:owocoin:1364995129022349382>",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Erro ao mostrar coins: {e}")
        await interaction.followup.send("Ocorreu um erro ao tentar mostrar os coins.", ephemeral=True)

def create_progress_bar(current: int, maximum: int, length: int = 10) -> str:
    """
    Cria uma barra de progresso visual.
    Exemplo: [▰▰▰▰▱▱▱▱▱▱] 40%
    """
    # Ensure values are non-negative
    current = max(0, current)
    maximum = max(1, maximum)  # Prevent division by zero
    
    # Ensure current doesn't exceed maximum
    current = min(current, maximum)
    
    # Calculate filled blocks
    filled = int((current / maximum) * length)
    percentage = int((current / maximum) * 100)
    
    # Create the bar
    bar = "▰" * filled + "▱" * (length - filled)
    
    return f"[{bar}] {percentage}%"

@bot.tree.command(name="xp", description="Mostra seu progresso de XP e nível")
async def xp(interaction: discord.Interaction, usuario: discord.Member = None):
    """
    Mostra o progresso de XP de um usuário com uma barra visual.
    Se nenhum usuário for especificado, mostra seu próprio progresso.
    """
    await interaction.response.defer()
    try:
        target_user = usuario or interaction.user
        guild_id = str(interaction.guild.id)
        user_id = str(target_user.id)
        
        # Busca dados do usuário
        user_data = None
        user_type = None
        
        # Procura em membros
        membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get()
        if membros:
            for membro in membros.values():
                if membro.get("discord_id") == user_id:
                    user_data = membro
                    user_type = "Membro"
                    break
        
        # Se não encontrou em membros, procura em visitantes
        if not user_data:
            visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get()
            if visitantes:
                for visitante in visitantes.values():
                    if visitante.get("discord_id") == user_id:
                        user_data = visitante
                        user_type = "Visitante"
                        break
        
        if not user_data:
            await interaction.followup.send("Este usuário não está registrado no servidor.", ephemeral=True)
            return
        
        # Calcula nível e XP
        message_count = user_data.get("message_count", 0)
        level, current_xp, next_level_xp = calculate_level(message_count)
        
        # Cria o embed com a cor personalizada do usuário
        embed = discord.Embed(
            title=f"Progresso de {target_user.display_name}",
            color=get_user_embed_color(user_data)
        )
        
        # Usa o avatar do Discord
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # Informações de nível
        embed.add_field(
            name=f"Nível {level}",
            value=f"**XP Total:** {int(current_xp)}\n**Próximo Nível:** {int(next_level_xp - current_xp)} XP restantes",
            inline=False
        )
        
        # Barra de progresso
        progress_bar = create_progress_bar(current_xp, next_level_xp, 15)
        embed.add_field(
            name="Progresso",
            value=f"`{progress_bar}`",
            inline=False
        )
        
        # Estatísticas extras
        embed.add_field(
            name="Estatísticas",
            value=f"**Mensagens Enviadas:** {message_count}\n**OwO Coins:** {user_data.get('owo_coins', 0)} <:owocoin:1364995129022349382>",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Erro ao mostrar XP: {e}")
        await interaction.followup.send("Ocorreu um erro ao tentar mostrar o progresso de XP.", ephemeral=True)

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)  # 3 minutos
        self.current_page = 1
        self.total_pages = 3
        
    def update_buttons(self):
        # Desabilita botão de voltar se estiver na primeira página
        self.first_page.disabled = self.current_page == 1
        self.prev_page.disabled = self.current_page == 1
        
        # Desabilita botão de avançar se estiver na última página
        self.next_page.disabled = self.current_page == self.total_pages
        self.last_page.disabled = self.current_page == self.total_pages
    
    def get_page_embed(self) -> discord.Embed:
        if self.current_page == 1:
            embed = discord.Embed(
                title="<:petharumi2:1310712833625034872> Comandos do Bot (1/3)",
                description="Aqui estão os comandos disponíveis:",
                color=discord.Color.blue()
            )

            # Comandos de Perfil
            perfil_commands = """
`/profile [@usuário]`
• Mostra seu perfil ou de outro usuário
• Exibe nível, XP, coins, tempo no servidor
• Mostra links do Lodestone e Tomestone.gg

`/xp [@usuário]`
• Mostra progresso detalhado de XP
• Exibe barra de progresso visual
• Informa XP necessário para próximo nível
• Mostra total de mensagens enviadas

`/coins [@usuário]`
• Mostra quantidade de OwO Coins

`/leaderboard`
• Mostra o ranking de níveis dos usuários
• Navegue pelas páginas usando os botões
"""
            embed.add_field(
                name="📋 Comandos de Perfil",
                value=perfil_commands,
                inline=False
            )

                        # Comandos de Economia
            economy_commands = """
`/daily`
• Receba coins e XP diariamente
• Recompensas aleatórias:
  - 1-100 OwO Coins
  - 1-300 XP
• Pode ser usado a cada 24 horas

`/daily_quests`
• Mostra suas quests diárias

`/pay <quantidade> <@usuário>`
• Transfere OwO Coins para outro usuário
• Exemplo: /pay 100 @Usuario123
• Ambos precisam estar registrados

`/request_coins <quantidade> <@usuário>`
• Solicita OwO Coins de outro usuário
• O usuário receberá uma DM para aceitar/rejeitar
• Verificação automática de saldo
"""
            embed.add_field(
                name="💰 Comandos de Economia",
                value=economy_commands,
                inline=False
            )

            # Sistema de XP


        elif self.current_page == 2:  # Página 2
            embed = discord.Embed(
                title="<:petharumi2:1310712833625034872> Comandos do Bot (2/3)",
                description="Continuação dos comandos disponíveis:",
                color=discord.Color.blue()
            )


            # Loja e Personalização
            shop_info = """
`/shop`
• Abre a loja de personalização
• Mostra seu saldo atual de OwO Coins
• Permite personalizar seus embeds:
  - Cores do Perfil (50 coins)
  - 10 cores predefinidas disponíveis
  - Opção para digitar código hexadecimal personalizado
  - A cor escolhida será aplicada em todos seus embeds
"""
            embed.add_field(
                name="🛍️ Loja e Personalização",
                value=shop_info,
                inline=False
            )

                        # mina
            mine_info = """
`/mine`
• Minera algum minério
• Minerar custa energia
• Só pode ser usado no canal #mina

`/mining_shop`
• Abre a loja da mina, onde você pode:
  - Melhorar sua Picareta
  - Comprar energia
• Só pode ser usado no canal #mina

`/mining_inventory`
• Mostra seu inventário de minérios
• Só pode ser usado no canal #mina

`/sell_ores`
• Vende seus minérios
• Só pode ser usado no canal #mina
"""
            embed.add_field(
                name="⛏️ Mineração",
                value=mine_info,
                inline=False
            )    

        else:  # Página 2
            embed = discord.Embed(
                title="<:petharumi2:1310712833625034872> Comandos do Bot (3/3)",
                description="Dicas:",
                color=discord.Color.blue()
            )        

            # Dicas
            tips = """
• Use `/profile` para ver seu progresso geral
• `/xp` mostra uma barra de progresso detalhada
• `/coins` é um jeito rápido de ver seus OwO Coins
• `/daily` para ganhar recompensas diárias
• `/pay` permite transferir coins para outros usuários
• Visite o canal #mineracao para minerar e ganhar coins
• Visite o canal #owo-casino para jogar e ganhar (ou não) coins
"""
            embed.add_field(
                name="💡 Dicas",
                value=tips,
                inline=False
            )
           
            xp_info = """
**Como funciona o XP?**
• Cada mensagem = 10 XP
• XP para subir de nível aumenta progressivamente
• Ao subir de nível, uma mensagem especial é exibida
• Seu nível reflete sua atividade no servidor

**Como ganhar OwO Coins?**
• Enviando mensagens: +1 coin
• Mensagens com imagens/links: +5 coins
• Subir de nível: +20 coins de brinde
• Daily: 1-50 coins + 1-300 XP (a cada 24h)
• Receber transferências de outros usuários
"""
            embed.add_field(
                name="📊 Sistema de XP e Coins",
                value=xp_info,
                inline=False
            )

        return embed
    
    @discord.ui.button(label="<<", style=discord.ButtonStyle.gray)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
    
    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.blurple)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(1, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
    
    @discord.ui.button(label="Próxima", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(self.total_pages, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
    
    @discord.ui.button(label=">>", style=discord.ButtonStyle.gray)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = self.total_pages
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
    
    async def on_timeout(self):
        # Remove os botões quando o tempo acabar
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

@bot.tree.command(name="help", description="Mostra informações sobre os comandos do bot")
async def help(interaction: discord.Interaction):
    """
    Mostra informações detalhadas sobre os comandos disponíveis.
    """
    await interaction.response.defer()
    try:
        # Cria a view com os botões
        view = HelpView()
        
        # Envia a primeira página
        message = await interaction.followup.send(embed=view.get_page_embed(), view=view)
        view.message = message
        
    except Exception as e:
        print(f"Erro ao mostrar ajuda: {e}")
        await interaction.followup.send("Ocorreu um erro ao mostrar a ajuda.", ephemeral=True)

class CustomColorModal(discord.ui.Modal, title="Cor Personalizada"):
    color = discord.ui.TextInput(
        label="Cor (Formato Hexadecimal)",
        placeholder="#FF0000 para vermelho, #00FF00 para verde, etc...",
        required=True,
        max_length=7,
        min_length=7
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Valida o formato da cor
            color = str(self.color)
            if not color.startswith('#') or not all(c in '0123456789ABCDEFabcdef' for c in color[1:]):
                await interaction.response.send_message("Formato de cor inválido! Use o formato #RRGGBB (ex: #FF0000)", ephemeral=True)
                return

            # Verifica se o usuário tem coins suficientes
            guild_id = str(interaction.guild.id)
            user_id = str(interaction.user.id)
            
            # Busca dados do usuário
            user_data = None
            user_ref = None
            
            membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get()
            if membros:
                for key, membro in membros.items():
                    if membro.get("discord_id") == user_id:
                        user_data = membro
                        user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key)
                        break
            
            if not user_data:
                visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get()
                if visitantes:
                    for key, visitante in visitantes.items():
                        if visitante.get("discord_id") == user_id:
                            user_data = visitante
                            user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key)
                            break
            
            if not user_data or not user_ref:
                await interaction.response.send_message("Erro ao encontrar seus dados!", ephemeral=True)
                return
                
            current_coins = user_data.get("owo_coins", 0)
            if current_coins < 50:
                await interaction.response.send_message("Você não tem OwO Coins suficientes! Necessário: 50 coins", ephemeral=True)
                return
            
            # Salva a cor personalizada
            user_ref.update({
                "embed_color": color,
                "owo_coins": current_coins - 50
            })
            
            # Cria um embed de teste com a nova cor
            embed = discord.Embed(
                title="Teste de Cor",
                description="Sua cor personalizada foi aplicada!",
                color=int(color[1:], 16)
            )
            
            await interaction.response.send_message(
                f"Cor personalizada definida com sucesso!\n"
                f"Saldo atual: {current_coins - 50} <:owocoin:1364995129022349382>",
                embed=embed,
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Erro ao definir cor: {e}")
            await interaction.response.send_message("Ocorreu um erro ao definir a cor. Verifique o formato e tente novamente.", ephemeral=True)

class ColorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)  # 5 minutos
        self.add_item(ColorSelect())
        
    @discord.ui.button(label="Cor Personalizada", style=discord.ButtonStyle.secondary, emoji="🎨", custom_id="custom_color")
    async def custom_color(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomColorModal())

class ColorSelect(discord.ui.Select):
    def __init__(self):
        colors = [
            ("Vermelho", "#FF0000", "🔴"),
            ("Verde", "#00FF00", "🟢"),
            ("Azul", "#0000FF", "🔵"),
            ("Roxo", "#800080", "🟣"),
            ("Rosa", "#FF69B4", "💗"),
            ("Laranja", "#FFA500", "🟠"),
            ("Amarelo", "#FFD700", "💛"),
            ("Ciano", "#00FFFF", "💠"),
            ("Branco", "#FFFFFF", "⚪"),
            ("Preto", "#000000", "⚫")
        ]
        
        options = [
            discord.SelectOption(
                label=name,
                value=hex_code,
                emoji=emoji,
                description=f"Mudar a cor para {name.lower()}"
            ) for name, hex_code, emoji in colors
        ]
        
        super().__init__(
            placeholder="Escolha uma cor predefinida...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            # Verifica se o usuário tem coins suficientes
            guild_id = str(interaction.guild.id)
            user_id = str(interaction.user.id)
            
            # Busca dados do usuário
            user_data = None
            user_ref = None
            
            membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get()
            if membros:
                for key, membro in membros.items():
                    if membro.get("discord_id") == user_id:
                        user_data = membro
                        user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key)
                        break
            
            if not user_data:
                visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get()
                if visitantes:
                    for key, visitante in visitantes.items():
                        if visitante.get("discord_id") == user_id:
                            user_data = visitante
                            user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key)
                            break
            
            if not user_data or not user_ref:
                await interaction.response.send_message("Erro ao encontrar seus dados!", ephemeral=True)
                return
                
            current_coins = user_data.get("owo_coins", 0)
            if current_coins < 50:
                await interaction.response.send_message("Você não tem OwO Coins suficientes! Necessário: 50 coins", ephemeral=True)
                return
            
            # Salva a cor selecionada
            selected_color = self.values[0]
            user_ref.update({
                "embed_color": selected_color,
                "owo_coins": current_coins - 50
            })
            
            # Cria um embed de teste com a nova cor
            embed = discord.Embed(
                title="Teste de Cor",
                description="Sua cor personalizada foi aplicada!",
                color=int(selected_color[1:], 16)
            )
            
            await interaction.response.send_message(
                f"Cor personalizada definida com sucesso!\n"
                f"Saldo atual: {current_coins - 50} <:owocoin:1364995129022349382>",
                embed=embed,
                ephemeral=True
            )
            
        except Exception as e:
            print(f"Erro ao definir cor: {e}")
            await interaction.response.send_message("Ocorreu um erro ao definir a cor. Tente novamente.", ephemeral=True)

class ShopView(discord.ui.View):
    def __init__(self, user_id: int, user_coins: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.user_coins = user_coins
        
    @discord.ui.button(label="Cores do Perfil", style=discord.ButtonStyle.primary, emoji="🎨", custom_id="embed_colors")
    async def embed_colors(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Este botão não é para você!", ephemeral=True)
            return
            
        if self.user_coins < 50:
            await interaction.response.send_message("Você não tem OwO Coins suficientes! Necessário: 50 coins", ephemeral=True)
            return
            
        view = ColorView()
        await interaction.response.send_message("Escolha uma cor para seus embeds:", view=view, ephemeral=True)

    @discord.ui.button(label="Comprar Tickets", style=discord.ButtonStyle.success, emoji="🎫", custom_id="buy_tickets")
    async def buy_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Este botão não é para você!", ephemeral=True)
            return

        # Verifica se existe um sorteio ativo
        guild_id = str(interaction.guild.id)
        current_raffle = db_ref.child("servidores").child(guild_id).child("raffle").get()
        
        if not current_raffle or not current_raffle.get("active", False):
            await interaction.response.send_message("Não há nenhum sorteio ativo no momento!", ephemeral=True)
            return

        # Abre o modal para comprar tickets
        await interaction.response.send_modal(BuyTicketsModal(self.user_coins, current_raffle["price"]))

class BuyTicketsModal(discord.ui.Modal, title="Comprar Tickets"):
    def __init__(self, user_coins: int, ticket_price: int):
        super().__init__(timeout=300)
        self.user_coins = user_coins
        self.ticket_price = ticket_price
        
        self.quantity = discord.ui.TextInput(
            label=f"Quantidade de Tickets ({ticket_price} coins cada)",
            placeholder="Digite a quantidade...",
            required=True,
            min_length=1,
            max_length=3
        )
        self.add_item(self.quantity)  # Adiciona o TextInput ao Modal

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity = int(self.quantity.value)
            if quantity <= 0:
                await interaction.response.send_message("A quantidade deve ser maior que 0!", ephemeral=True)
                return

            total_cost = quantity * self.ticket_price
            if total_cost > self.user_coins:
                await interaction.response.send_message(
                    f"Você não tem coins suficientes!\n"
                    f"Custo total: {total_cost} <:owocoin:1364995129022349382>\n"
                    f"Seu saldo: {self.user_coins} <:owocoin:1364995129022349382>",
                    ephemeral=True
                )
                return

            guild_id = str(interaction.guild.id)
            user_id = str(interaction.user.id)

            # Busca dados do usuário
            user_data = None
            user_ref = None

            # Busca em membros
            membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get() or {}
            for key, membro in membros.items():
                if membro.get("discord_id") == user_id:
                    user_data = membro
                    user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key)
                    break

            # Busca em visitantes se necessário
            if not user_data:
                visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get() or {}
                for key, visitante in visitantes.items():
                    if visitante.get("discord_id") == user_id:
                        user_data = visitante
                        user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key)
                        break

            if not user_data or not user_ref:
                await interaction.response.send_message("Erro ao encontrar seus dados!", ephemeral=True)
                return

            # Gera números únicos para os tickets
            current_raffle = db_ref.child("servidores").child(guild_id).child("raffle").get()
            current_tickets = set()
            if current_raffle.get("participants"):
                for tickets in current_raffle["participants"].values():
                    current_tickets.update(tickets)

            new_tickets = []
            while len(new_tickets) < quantity:
                ticket_number = random.randint(1, 9999)
                if ticket_number not in current_tickets:
                    new_tickets.append(ticket_number)
                    current_tickets.add(ticket_number)

            # Atualiza os tickets do usuário
            user_tickets = current_raffle.get("participants", {}).get(user_id, [])
            user_tickets.extend(new_tickets)

            # Atualiza o sorteio
            raffle_ref = db_ref.child("servidores").child(guild_id).child("raffle")
            raffle_ref.child("participants").child(user_id).set(user_tickets)
            raffle_ref.child("tickets_sold").set(len(current_tickets))

            # Deduz os coins
            new_balance = user_data.get("owo_coins", 0) - total_cost
            user_ref.update({
                "owo_coins": new_balance
            })

            # Cria embed de confirmação
            embed = discord.Embed(
                title="🎫 Tickets Comprados!",
                description=f"Você comprou **{quantity}** ticket(s) por **{total_cost}** <:owocoin:1364995129022349382>",
                color=discord.Color.green()
            )

            embed.add_field(
                name="Seus novos tickets",
                value=f"#{', #'.join(map(str, new_tickets))}",
                inline=False
            )

            embed.add_field(
                name="Seu novo saldo",
                value=f"**{new_balance}** <:owocoin:1364995129022349382>",
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError:
            await interaction.response.send_message("Por favor, digite um número válido!", ephemeral=True)
        except Exception as e:
            print(f"Erro ao comprar tickets: {e}")
            await interaction.response.send_message("Ocorreu um erro ao comprar os tickets.", ephemeral=True)

@bot.tree.command(name="shop", description="Abre a loja de itens")
async def shop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        # Busca dados do usuário
        user_data = None
        
        membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get()
        if membros:
            for membro in membros.values():
                if membro.get("discord_id") == user_id:
                    user_data = membro
                    break
        
        if not user_data:
            visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get()
            if visitantes:
                for visitante in visitantes.values():
                    if visitante.get("discord_id") == user_id:
                        user_data = visitante
                        break
        
        if not user_data:
            embed = discord.Embed(
                title="❌ Acesso Negado",
                description="Você precisa estar registrado para usar a loja!\n\n"
                           "Para se registrar, vá até o canal #registro e siga as instruções.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        coins = user_data.get("owo_coins", 0)
        
        embed = discord.Embed(
            title="<:owocoin:1364995129022349382> Loja OwO <:owocoin:1364995129022349382>",
            description=f"Bem-vindo à loja! Seu saldo: **{coins}** <:owocoin:1364995129022349382>",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="🎨 Cores do Perfil",
            value="Personalize a cor dos seus embeds\n**Preço:** 50 <:owocoin:1364995129022349382>",
            inline=False
        )

        # Adiciona informações do sorteio se houver um ativo
        current_raffle = db_ref.child("servidores").child(guild_id).child("raffle").get()
        if current_raffle and current_raffle.get("active", False):
            embed.add_field(
                name="🎫 Sorteio Ativo",
                value=f"**Prêmio:** {current_raffle['description']}\n"
                      f"**Preço do Ticket:** {current_raffle['price']} <:owocoin:1364995129022349382>",
                inline=False
            )
        
        view = ShopView(interaction.user.id, coins)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        print(f"Erro ao abrir loja: {e}")
        await interaction.followup.send("Ocorreu um erro ao abrir a loja.", ephemeral=True)

@bot.tree.command(name="pay", description="Transfere OwO Coins para outro usuário")
@app_commands.describe(
    quantidade="Quantidade de OwO Coins para transferir",
    usuario="Usuário que receberá os OwO Coins"
)
async def pay(interaction: discord.Interaction, quantidade: int, usuario: discord.Member):
    """
    Transfere OwO Coins para outro usuário.
    Parâmetros:
        quantidade: Quantidade de coins para transferir
        usuario: O usuário que receberá os coins (mencione o usuário)
    """
    await interaction.response.defer()
    try:
        # Verifica se a quantidade é válida
        if quantidade <= 0:
            await interaction.followup.send("A quantidade deve ser maior que 0!", ephemeral=True)
            return
            
        # Verifica se não está tentando transferir para si mesmo
        if usuario.id == interaction.user.id:
            await interaction.followup.send("Você não pode transferir OwO Coins para si mesmo!", ephemeral=True)
            return
            
        guild_id = str(interaction.guild.id)
        sender_id = str(interaction.user.id)
        receiver_id = str(usuario.id)
        
        # Busca dados do remetente e destinatário
        sender_data = None
        sender_ref = None
        receiver_data = None
        receiver_ref = None
        
        # Busca em membros
        membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get() or {}
        for key, membro in membros.items():
            if membro.get("discord_id") == sender_id:
                sender_data = membro
                sender_ref = db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key)
            elif membro.get("discord_id") == receiver_id:
                receiver_data = membro
                receiver_ref = db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key)
        
        # Busca em visitantes se necessário
        if not sender_data or not receiver_data:
            visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get() or {}
            for key, visitante in visitantes.items():
                if not sender_data and visitante.get("discord_id") == sender_id:
                    sender_data = visitante
                    sender_ref = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key)
                elif not receiver_data and visitante.get("discord_id") == receiver_id:
                    receiver_data = visitante
                    receiver_ref = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key)
        
        # Verifica se ambos os usuários foram encontrados
        if not sender_data:
            await interaction.followup.send("Você precisa estar registrado para transferir OwO Coins!", ephemeral=True)
            return
            
        if not receiver_data:
            await interaction.followup.send(f"{usuario.mention} precisa estar registrado para receber OwO Coins!", ephemeral=True)
            return
            
        # Verifica se o remetente tem coins suficientes
        sender_coins = sender_data.get("owo_coins", 0)
        if sender_coins < quantidade:
            await interaction.followup.send(
                f"Você não tem OwO Coins suficientes!\n"
                f"Seu saldo: **{sender_coins}** <:owocoin:1364995129022349382>",
                ephemeral=True
            )
            return
            
        # Realiza a transferência
        receiver_coins = receiver_data.get("owo_coins", 0)
        
        # Atualiza os valores no banco de dados
        try:
            sender_ref.update({
                "owo_coins": sender_coins - quantidade
            })
            
            receiver_ref.update({
                "owo_coins": receiver_coins + quantidade
            })
        except Exception as e:
            print(f"Erro ao atualizar coins no banco de dados: {e}")
            await interaction.followup.send("Ocorreu um erro ao transferir os OwO Coins. Tente novamente.", ephemeral=True)
            return
        
        # Cria o embed de confirmação
        embed = discord.Embed(
            title="💸 Transferência de OwO Coins",
            description=f"{interaction.user.mention} transferiu **{quantidade}** <:owocoin:1364995129022349382> para {usuario.mention}",
            color=get_user_embed_color(sender_data)
        )
        
        embed.add_field(
            name="Seu novo saldo",
            value=f"**{sender_coins - quantidade}** <:owocoin:1364995129022349382>",
            inline=True
        )
        
        embed.add_field(
            name=f"Saldo de {usuario.display_name}",
            value=f"**{receiver_coins + quantidade}** <:owocoin:1364995129022349382>",
            inline=True
        )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        print(f"Erro ao transferir OwO Coins: {e}")
        await interaction.followup.send("Ocorreu um erro ao transferir os OwO Coins. Tente novamente.", ephemeral=True)

@bot.tree.command(name="sync_history", description="Sincroniza o histórico de mensagens para atualizar XP e níveis")
@app_commands.describe(
    canal="Canal para sincronizar (opcional - se não especificado, sincroniza todos os canais)",
    ignorar_canal="Canal para ignorar durante a sincronização (opcional)"
)
@app_commands.default_permissions(administrator=True)
async def sync_history(interaction: discord.Interaction, canal: discord.TextChannel = None, ignorar_canal: discord.TextChannel = None):
    """
    Sincroniza todo o histórico de mensagens do servidor para atualizar XP e níveis dos usuários.
    Apenas o dono do bot pode usar este comando.
    """
    # Verifica se é o dono do bot
    if interaction.user.id != "your_id_here":  # Seu ID do Discord
        await interaction.response.send_message("Apenas o dono do bot pode usar este comando!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    try:
        guild_id = str(interaction.guild.id)
        
        # Busca todos os usuários registrados
        registered_users = {}
        
        # Busca membros
        membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get()
        if membros:
            for key, membro in membros.items():
                discord_id = membro.get("discord_id")
                if discord_id:
                    registered_users[discord_id] = {
                        "ref": db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key),
                        "data": membro,
                        "type": "membro"
                    }
        
        # Busca visitantes
        visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get()
        if visitantes:
            for key, visitante in visitantes.items():
                discord_id = visitante.get("discord_id")
                if discord_id:
                    registered_users[discord_id] = {
                        "ref": db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key),
                        "data": visitante,
                        "type": "visitante"
                    }
        
        if not registered_users:
            await interaction.followup.send("Não foram encontrados usuários registrados para atualizar.", ephemeral=True)
            return
        
        # Inicializa contadores para o relatório
        stats = {
            "total_messages": 0,
            "users_updated": 0,
            "ignored_messages": 0
        }
        
        # Dicionário para armazenar as estatísticas por usuário
        user_stats = {}
        
        # Progresso inicial
        progress_message = await interaction.followup.send(
            f"Iniciando sincronização do histórico{' do canal ' + canal.mention if canal else ''}...\n"
            f"{f'Ignorando mensagens do canal {ignorar_canal.mention}' if ignorar_canal else ''}\n"
            "Isso pode levar alguns minutos.",
            ephemeral=True
        )
        
        # Lista de canais a processar
        channels_to_process = [canal] if canal else interaction.guild.text_channels
        
        # Processa cada canal de texto
        for channel in channels_to_process:
            # Pula o canal se for o canal a ser ignorado
            if ignorar_canal and channel.id == ignorar_canal.id:
                continue
                
            try:
                # Atualiza mensagem de progresso a cada canal
                await progress_message.edit(
                    content=f"Processando canal: {channel.mention}...\n"
                           f"Mensagens processadas: {stats['total_messages']}\n"
                           f"Mensagens ignoradas: {stats['ignored_messages']}"
                )
                
                async for message in channel.history(limit=None):
                    stats['total_messages'] += 1
                    
                    # Ignora mensagens de bots
                    if message.author.bot:
                        continue
                    
                    # Verifica se o autor da mensagem está registrado
                    author_id = str(message.author.id)
                    if author_id in registered_users:
                        # Inicializa estatísticas do usuário se necessário
                        if author_id not in user_stats:
                            user_stats[author_id] = {
                                "messages": 0,
                                "name": str(message.author),
                                "old_level": calculate_level(registered_users[author_id]["data"].get("message_count", 0))[0]
                            }
                        
                        # Incrementa a contagem de mensagens
                        user_stats[author_id]["messages"] += 1
                
            except Exception as e:
                print(f"Erro ao processar canal {channel.name}: {e}")
                continue
        
        # Lista para armazenar usuários que subiram de nível
        level_ups = []
        
        # Atualiza os dados no Firebase
        for user_id, stats_data in user_stats.items():
            try:
                user_ref = registered_users[user_id]["ref"]
                current_data = registered_users[user_id]["data"]
                
                # Usa a nova contagem de mensagens (substitui ao invés de somar)
                new_message_count = stats_data["messages"]
                
                # Calcula novo nível
                new_level = calculate_level(new_message_count)[0]
                
                # Registra level ups
                if new_level > stats_data["old_level"]:
                    level_ups.append({
                        "name": stats_data["name"],
                        "old_level": stats_data["old_level"],
                        "new_level": new_level
                    })
                
                # Atualiza apenas a contagem de mensagens no Firebase
                user_ref.update({
                    "message_count": new_message_count
                })
                
                stats["users_updated"] += 1
                
            except Exception as e:
                print(f"Erro ao atualizar usuário {user_id}: {e}")
                continue
        
        # Cria embed com o relatório final
        embed = discord.Embed(
            title="📊 Relatório de Sincronização",
            description=f"Sincronização do histórico{' do canal ' + canal.mention if canal else ''} concluída!\n"
                       f"{f'Canal ignorado: {ignorar_canal.mention}' if ignorar_canal else ''}",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📝 Estatísticas Gerais",
            value=f"• Mensagens processadas: **{stats['total_messages']}**\n"
                  f"• Usuários atualizados: **{stats['users_updated']}**",
            inline=False
        )
        
        # Adiciona top 5 usuários mais ativos
        top_users = sorted(
            user_stats.items(),
            key=lambda x: x[1]["messages"],
            reverse=True
        )[:5]
        
        top_users_text = "\n".join(
            f"• {data['name']}: {data['messages']} mensagens"
            for user_id, data in top_users
        )
        
        embed.add_field(
            name="🏆 Top 5 Usuários Mais Ativos",
            value=top_users_text or "Nenhum usuário processado",
            inline=False
        )
        
        # Adiciona informações sobre level ups
        if level_ups:
            level_ups_text = "\n".join(
                f"• {user['name']}: Level {user['old_level']} → {user['new_level']}"
                for user in sorted(level_ups, key=lambda x: x['new_level'] - x['old_level'], reverse=True)[:5]
            )
            
            total_levels = sum(user['new_level'] - user['old_level'] for user in level_ups)
            
            embed.add_field(
                name="⭐ Level Ups",
                value=f"Total de níveis ganhos: **{total_levels}**\n\n{level_ups_text}",
                inline=False
            )
        
        await progress_message.edit(content="", embed=embed)
        
    except Exception as e:
        print(f"Erro durante a sincronização: {e}")
        await interaction.followup.send("Ocorreu um erro durante a sincronização do histórico.", ephemeral=True)

class LeaderboardView(discord.ui.View):
    def __init__(self, users_data: list, current_page: int = 1):
        super().__init__(timeout=180)  # 3 minutos de timeout
        self.users_data = users_data
        self.current_page = current_page
        self.items_per_page = 10
        self.total_pages = max(1, -(-len(users_data) // self.items_per_page))
        
        # Desabilita botões se necessário
        self.update_buttons()
    
    def update_buttons(self):
        # Desabilita botão de voltar se estiver na primeira página
        self.first_page.disabled = self.current_page == 1
        self.prev_page.disabled = self.current_page == 1
        
        # Desabilita botão de avançar se estiver na última página
        self.next_page.disabled = self.current_page == self.total_pages
        self.last_page.disabled = self.current_page == self.total_pages
    
    def get_page_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🏆 Ranking de Níveis",
            description=f"Página {self.current_page}/{self.total_pages}",
            color=discord.Color.gold()
        )
        
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.users_data))
        
        ranking_text = ""
        for idx, user in enumerate(self.users_data[start_idx:end_idx], start=start_idx + 1):
            # Determina a medalha para os 3 primeiros
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, "")
            
            ranking_text += f"{medal}**#{idx}** • {user['mention']}\n"
            ranking_text += f"Level {user['level']} ({user['type']})\n"
            ranking_text += f"`{user['progress_bar']}` {user['progress_percent']:.1f}%\n"
            ranking_text += f"Mensagens: {user['message_count']}\n\n"
        
        embed.add_field(
            name="Ranking",
            value=ranking_text or "Nenhum usuário encontrado",
            inline=False
        )
        
        embed.set_footer(text=f"Total de usuários: {len(self.users_data)}")
        return embed
    
    @discord.ui.button(label="<<", style=discord.ButtonStyle.gray)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
    
    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.blurple)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = max(1, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
    
    @discord.ui.button(label="Próxima", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = min(self.total_pages, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
    
    @discord.ui.button(label=">>", style=discord.ButtonStyle.gray)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = self.total_pages
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
    
    async def on_timeout(self):
        # Remove os botões quando o tempo acabar
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

@bot.tree.command(name="leaderboard", description="Mostra o ranking de níveis dos usuários")
async def leaderboard(interaction: discord.Interaction):
    """
    Mostra o ranking de níveis dos usuários do servidor.
    Usa botões para navegar entre as páginas.
    """
    await interaction.response.defer()
    try:
        guild_id = str(interaction.guild.id)
        
        # Lista para armazenar dados dos usuários
        users_data = []
        
        # Busca membros
        membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get() or {}
        for user_data in membros.values():
            message_count = user_data.get("message_count", 0)
            level, current_xp, next_level_xp = calculate_level(message_count)
            
            # Tenta encontrar o membro do Discord
            discord_member = interaction.guild.get_member(int(user_data["discord_id"])) if user_data.get("discord_id") else None
            mention = discord_member.mention if discord_member else f"{user_data.get('nome', '')} {user_data.get('sobrenome', '')}".strip() or user_data.get("discord_name", "Usuário")
            
            # Calcula progresso
            progress_percent = (current_xp / next_level_xp) * 100 if next_level_xp > 0 else 100
            progress_bar = create_progress_bar(current_xp, next_level_xp, 10)
            
            users_data.append({
                "mention": mention,
                "message_count": message_count,
                "level": level,
                "type": "Membro",
                "progress_percent": progress_percent,
                "progress_bar": progress_bar
            })
        
        # Busca visitantes
        visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get() or {}
        for user_data in visitantes.values():
            message_count = user_data.get("message_count", 0)
            level, current_xp, next_level_xp = calculate_level(message_count)
            
            # Tenta encontrar o membro do Discord
            discord_member = interaction.guild.get_member(int(user_data["discord_id"])) if user_data.get("discord_id") else None
            mention = discord_member.mention if discord_member else f"{user_data.get('nome', '')} {user_data.get('sobrenome', '')}".strip() or user_data.get("discord_name", "Usuário")
            
            # Calcula progresso
            progress_percent = (current_xp / next_level_xp) * 100 if next_level_xp > 0 else 100
            progress_bar = create_progress_bar(current_xp, next_level_xp, 10)
            
            users_data.append({
                "mention": mention,
                "message_count": message_count,
                "level": level,
                "type": "Visitante",
                "progress_percent": progress_percent,
                "progress_bar": progress_bar
            })
        
        # Ordena por nível (primeiro) e mensagens (segundo)
        users_data.sort(key=lambda x: (x["level"], x["message_count"]), reverse=True)
        
        # Cria a view com os botões
        view = LeaderboardView(users_data)
        
        # Envia a primeira página
        message = await interaction.followup.send(embed=view.get_page_embed(), view=view)
        view.message = message
        
    except Exception as e:
        print(f"Erro ao mostrar leaderboard: {e}")
        await interaction.followup.send("Ocorreu um erro ao mostrar o ranking.", ephemeral=True)

class RequestCoinsView(discord.ui.View):
    def __init__(self, requester_id: int, amount: int, guild_id: str, target_id: int):
        super().__init__(timeout=300)  # 5 minutos
        self.requester_id = requester_id
        self.amount = amount
        self.guild_id = guild_id
        self.target_id = target_id
    
    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.green, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Verifica se o usuário que clicou é o alvo da solicitação
            if interaction.user.id != self.target_id:
                await interaction.response.send_message("Você não pode responder a esta solicitação!", ephemeral=True)
                return
            
            # Adia a resposta para evitar timeout
            await interaction.response.defer()
            
            # Busca dados do doador (quem recebeu a DM)
            donor_data = None
            donor_ref = None
            requester_data = None
            requester_ref = None
            
            # Busca em membros
            membros = db_ref.child("servidores").child(self.guild_id).child("usuarios_membros").get() or {}
            for key, membro in membros.items():
                if membro.get("discord_id") == str(interaction.user.id):
                    donor_data = membro
                    donor_ref = db_ref.child("servidores").child(self.guild_id).child("usuarios_membros").child(key)
                elif membro.get("discord_id") == str(self.requester_id):
                    requester_data = membro
                    requester_ref = db_ref.child("servidores").child(self.guild_id).child("usuarios_membros").child(key)
            
            # Busca em visitantes se necessário
            if not donor_data or not requester_data:
                visitantes = db_ref.child("servidores").child(self.guild_id).child("usuarios_visitantes").get() or {}
                for key, visitante in visitantes.items():
                    if not donor_data and visitante.get("discord_id") == str(interaction.user.id):
                        donor_data = visitante
                        donor_ref = db_ref.child("servidores").child(self.guild_id).child("usuarios_visitantes").child(key)
                    elif not requester_data and visitante.get("discord_id") == str(self.requester_id):
                        requester_data = visitante
                        requester_ref = db_ref.child("servidores").child(self.guild_id).child("usuarios_visitantes").child(key)
            
            if not donor_data or not requester_data:
                await interaction.followup.send("Erro: Dados dos usuários não encontrados.", ephemeral=True)
                return
            
            # Verifica se ainda tem coins suficientes
            donor_coins = donor_data.get("owo_coins", 0)
            if donor_coins < self.amount:
                await interaction.followup.send(
                    f"Você não tem OwO Coins suficientes!\n"
                    f"Saldo atual: **{donor_coins}** <:owocoin:1364995129022349382>",
                    ephemeral=True
                )
                return
            
            # Realiza a transferência
            requester_coins = requester_data.get("owo_coins", 0)
            
            donor_ref.update({
                "owo_coins": donor_coins - self.amount
            })
            
            requester_ref.update({
                "owo_coins": requester_coins + self.amount
            })
            
            # Desabilita os botões
            for child in self.children:
                child.disabled = True
            
            # Atualiza a mensagem na DM
            embed = discord.Embed(
                title="✅ Solicitação Aceita!",
                description=f"Você transferiu **{self.amount}** <:owocoin:1364995129022349382> para <@{self.requester_id}>",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Seu novo saldo",
                value=f"**{donor_coins - self.amount}** <:owocoin:1364995129022349382>"
            )
            await interaction.edit_original_response(embed=embed, view=self)
            
            # Notifica o solicitante
            try:
                requester = await interaction.client.fetch_user(self.requester_id)
                embed = discord.Embed(
                    title="✅ Solicitação Aceita!",
                    description=f"<@{interaction.user.id}> aceitou sua solicitação e transferiu **{self.amount}** <:owocoin:1364995129022349382>",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Seu novo saldo",
                    value=f"**{requester_coins + self.amount}** <:owocoin:1364995129022349382>"
                )
                await requester.send(embed=embed)
            except:
                pass
            
        except Exception as e:
            print(f"Erro ao aceitar solicitação: {e}")
            await interaction.followup.send("Ocorreu um erro ao processar a solicitação.", ephemeral=True)
    
    @discord.ui.button(label="Rejeitar", style=discord.ButtonStyle.red, emoji="❌")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Verifica se o usuário que clicou é o alvo da solicitação
            if interaction.user.id != self.target_id:
                await interaction.response.send_message("Você não pode responder a esta solicitação!", ephemeral=True)
                return
            
            # Adia a resposta para evitar timeout
            await interaction.response.defer()
            
            # Desabilita os botões
            for child in self.children:
                child.disabled = True
            
            # Atualiza a mensagem na DM
            embed = discord.Embed(
                title="❌ Solicitação Rejeitada",
                description=f"Você rejeitou a solicitação de **{self.amount}** <:owocoin:1364995129022349382> de <@{self.requester_id}>",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed, view=self)
            
            # Notifica o solicitante
            try:
                requester = await interaction.client.fetch_user(self.requester_id)
                embed = discord.Embed(
                    title="❌ Solicitação Rejeitada",
                    description=f"<@{interaction.user.id}> rejeitou sua solicitação de **{self.amount}** <:owocoin:1364995129022349382>",
                    color=discord.Color.red()
                )
                await requester.send(embed=embed)
            except:
                pass
            
        except Exception as e:
            print(f"Erro ao rejeitar solicitação: {e}")
            await interaction.followup.send("Ocorreu um erro ao processar a rejeição.", ephemeral=True)
    
    async def on_timeout(self):
        try:
            # Desabilita os botões
            for child in self.children:
                child.disabled = True
            
            # Atualiza a mensagem com timeout
            embed = discord.Embed(
                title="⏰ Solicitação Expirada",
                description=f"A solicitação de **{self.amount}** <:owocoin:1364995129022349382> de <@{self.requester_id}> expirou",
                color=discord.Color.grey()
            )
            await self.message.edit(embed=embed, view=self)
            
            # Notifica o solicitante
            try:
                requester = await self.message.client.fetch_user(self.requester_id)
                embed = discord.Embed(
                    title="⏰ Solicitação Expirada",
                    description=f"Sua solicitação de **{self.amount}** <:owocoin:1364995129022349382> para <@{self.message.channel.recipient.id}> expirou",
                    color=discord.Color.grey()
                )
                await requester.send(embed=embed)
            except:
                pass
        except:
            pass

@bot.tree.command(name="request_coins", description="Solicita OwO Coins de outro usuário")
@app_commands.describe(
    quantidade="Quantidade de OwO Coins para solicitar",
    usuario="Usuário para solicitar os OwO Coins"
)
async def request_coins(interaction: discord.Interaction, quantidade: int, usuario: discord.Member):
    """
    Envia uma solicitação de OwO Coins para outro usuário.
    O usuário receberá uma DM com botões para aceitar ou rejeitar.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        # Verifica se a quantidade é válida
        if quantidade <= 0:
            await interaction.followup.send("A quantidade deve ser maior que 0!", ephemeral=True)
            return
        
        # Verifica se não está solicitando de si mesmo
        if usuario.id == interaction.user.id:
            await interaction.followup.send("Você não pode solicitar OwO Coins de si mesmo!", ephemeral=True)
            return
        
        guild_id = str(interaction.guild.id)
        target_id = str(usuario.id)
        
        # Verifica se o usuário alvo tem coins suficientes
        target_data = None
        
        # Busca em membros
        membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get() or {}
        for membro in membros.values():
            if membro.get("discord_id") == target_id:
                target_data = membro
                break
        
        # Busca em visitantes se necessário
        if not target_data:
            visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get() or {}
            for visitante in visitantes.values():
                if visitante.get("discord_id") == target_id:
                    target_data = visitante
                    break
        
        if not target_data:
            await interaction.followup.send(f"{usuario.mention} não está registrado no servidor!", ephemeral=True)
            return
        
        target_coins = target_data.get("owo_coins", 0)
        if target_coins < quantidade:
            await interaction.followup.send(
                f"{usuario.mention} não tem OwO Coins suficientes!\n"
                f"Saldo dele(a): **{target_coins}** <:owocoin:1364995129022349382>",
                ephemeral=True
            )
            return
        
        try:
            # Cria o embed para a DM
            embed = discord.Embed(
                title="💰 Solicitação de OwO Coins",
                description=f"<@{interaction.user.id}> está solicitando **{quantidade}** <:owocoin:1364995129022349382>",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="Seu saldo atual",
                value=f"**{target_coins}** <:owocoin:1364995129022349382>",
                inline=False
            )
            
            embed.add_field(
                name="Saldo após transferência",
                value=f"**{target_coins - quantidade}** <:owocoin:1364995129022349382>",
                inline=False
            )
            
            # Envia a DM com os botões, agora incluindo o target_id
            view = RequestCoinsView(interaction.user.id, quantidade, guild_id, usuario.id)
            dm_message = await usuario.send(embed=embed, view=view)
            view.message = dm_message
            
            # Confirma o envio da solicitação
            await interaction.followup.send(
                f"Solicitação de **{quantidade}** <:owocoin:1364995129022349382> enviada para {usuario.mention}!\n"
                "Ele(a) receberá uma mensagem privada para aceitar ou rejeitar.",
                ephemeral=True
            )
            
        except discord.Forbidden:
            await interaction.followup.send(
                f"Não foi possível enviar mensagem privada para {usuario.mention}.\n"
                "Verifique se eles têm mensagens diretas ativadas.",
                ephemeral=True
            )
            
    except Exception as e:
        print(f"Erro ao solicitar coins: {e}")
        await interaction.followup.send("Ocorreu um erro ao enviar a solicitação.", ephemeral=True)

def format_time_remaining(seconds: int) -> str:
    """
    Formata o tempo restante em horas, minutos e segundos.
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

@bot.tree.command(name="daily", description="Receba OwO Coins e XP diários (uma vez a cada 24 horas)")
async def daily(interaction: discord.Interaction):
    """
    Dá ao usuário uma quantidade aleatória de OwO Coins (1-50) e XP (1-300) uma vez por dia.
    Mostra o tempo restante se tentar usar antes das 24 horas.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        # Busca dados do usuário
        user_data = None
        user_ref = None
        
        # Busca em membros
        membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get() or {}
        for key, membro in membros.items():
            if membro.get("discord_id") == user_id:
                user_data = membro
                user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key)
                break
        
        # Busca em visitantes se necessário
        if not user_data:
            visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get() or {}
            for key, visitante in visitantes.items():
                if visitante.get("discord_id") == user_id:
                    user_data = visitante
                    user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key)
                    break
        
        if not user_data:
            await interaction.followup.send(
                "Você não está registrado no servidor. Entre em contato com um administrador para ser registrado.",
                ephemeral=True
            )
            return
        
        # Verifica o último daily
        current_time = int(datetime.now(timezone.utc).timestamp())
        last_daily = user_data.get("last_daily", 0)
        
        # Calcula tempo restante
        time_passed = current_time - last_daily
        cooldown = 24 * 60 * 60  # 24 horas em segundos
        
        if time_passed < cooldown:
            time_remaining = cooldown - time_passed
            formatted_time = format_time_remaining(time_remaining)
            
            embed = discord.Embed(
                title="⏰ Daily em Cooldown",
                description=f"Você precisa esperar **{formatted_time}** para pegar seu daily novamente!",
                color=discord.Color.red()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Gera recompensas aleatórias
        coins_earned = random.randint(1, 100)
        xp_earned = random.randint(1, 300)
        
        current_coins = user_data.get("owo_coins", 0)
        current_messages = user_data.get("message_count", 0)
        
        # Calcula níveis antes e depois
        old_level = calculate_level(current_messages)[0]
        new_messages = current_messages + (xp_earned // 10)  # Cada mensagem vale 10 XP
        new_level = calculate_level(new_messages)[0]
        
        # Atualiza os dados do usuário
        user_ref.update({
            "owo_coins": current_coins + coins_earned,
            "message_count": new_messages,
            "last_daily": current_time
        })
        
        # Cria embed de sucesso
        embed = discord.Embed(
            title="🎁 Daily Coletado!",
            description=f"Você recebeu:\n"
                       f"• **{coins_earned}** <:owocoin:1364995129022349382>\n"
                       f"• **{xp_earned}** XP",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Seu novo saldo",
            value=f"**{current_coins + coins_earned}** <:owocoin:1364995129022349382>",
            inline=False
        )
        
        # Se subiu de nível, adiciona a informação
        if new_level > old_level:
            embed.add_field(
                name="🎉 Level Up!",
                value=f"Você subiu do nível **{old_level}** para o nível **{new_level}**!",
                inline=False
            )
            
            # Adiciona coins de bônus por level up
            bonus_coins = 20 * (new_level - old_level)  # 20 coins por nível
            user_ref.update({
                "owo_coins": current_coins + coins_earned + bonus_coins
            })
            
            embed.add_field(
                name="🌟 Bônus de Level Up",
                value=f"**+{bonus_coins}** <:owocoin:1364995129022349382> por subir de nível!",
                inline=False
            )
        
        # Adiciona mensagem de sorte baseada na quantidade
        if coins_earned >= 45 and xp_earned >= 250:
            embed.add_field(
                name="🍀 Muita Sorte!",
                value="Você ganhou uma das maiores recompensas possíveis!",
                inline=False
            )
        elif coins_earned >= 35 or xp_earned >= 200:
            embed.add_field(
                name="✨ Boa Sorte!",
                value="Você ganhou uma ótima quantidade de recompensas!",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        print(f"Erro ao processar daily: {e}")
        await interaction.followup.send("Ocorreu um erro ao processar seu daily.", ephemeral=True)

@bot.tree.command(name="raffle", description="Gerencia sorteios")
@app_commands.describe(
    action="Ação a ser executada",
    price="Preço do ticket (apenas para create)",
    description="Descrição do prêmio (apenas para create)",
    channel="Canal onde o sorteio será anunciado (apenas para create)"
)
@app_commands.choices(action=[
    app_commands.Choice(name="create", value="create"),
    app_commands.Choice(name="end", value="end"),
    app_commands.Choice(name="info", value="info"),
    app_commands.Choice(name="tickets", value="tickets"),
    app_commands.Choice(name="cancel", value="cancel")
])
async def raffle(interaction: discord.Interaction, action: str, price: int = None, description: str = None, channel: discord.TextChannel = None):
    """
    Gerencia sorteios no servidor.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)

        if action == "create":
            # Verifica permissões de administrador
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("Você não tem permissão para criar sorteios!", ephemeral=True)
                return

            if price is None or description is None or channel is None:
                await interaction.followup.send("Você precisa especificar o preço, a descrição do prêmio e o canal de anúncio!", ephemeral=True)
                return

            if price <= 0:
                await interaction.followup.send("O preço do ticket deve ser maior que 0!", ephemeral=True)
                return

            # Verifica se já existe um sorteio ativo
            current_raffle = db_ref.child("servidores").child(guild_id).child("raffle").get()
            if current_raffle and current_raffle.get("active", False):
                await interaction.followup.send("Já existe um sorteio ativo! Finalize o atual antes de criar um novo.", ephemeral=True)
                return

            # Busca os cargos configurados
            cargos = db_ref.child("servidores").child(guild_id).get()
            if not cargos or not cargos.get("cargo_membro") or not cargos.get("cargo_visitante"):
                await interaction.followup.send("Os cargos de membro e visitante não estão configurados! Use /configurar_cargos primeiro.", ephemeral=True)
                return

            cargo_membro = interaction.guild.get_role(int(cargos.get("cargo_membro")))
            cargo_visitante = interaction.guild.get_role(int(cargos.get("cargo_visitante")))

            if not cargo_membro or not cargo_visitante:
                await interaction.followup.send("Erro ao encontrar os cargos de membro e visitante!", ephemeral=True)
                return

            # Cria novo sorteio
            raffle_data = {
                "active": True,
                "created_at": {".sv": "timestamp"},
                "created_by": user_id,
                "price": price,
                "description": description,
                "tickets_sold": 0,
                "participants": {},
                "announce_channel": channel.id
            }

            db_ref.child("servidores").child(guild_id).child("raffle").set(raffle_data)

            embed = discord.Embed(
                title="🎫 Novo Sorteio Criado!",
                description=f"{cargo_membro.mention} {cargo_visitante.mention}\n\n"
                           f"**Prêmio:** {description}\n"
                           f"**Preço do Ticket:** {price} <:owocoin:1364995129022349382>",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📝 Como Participar",
                value="**1.** Use `/shop` para abrir a loja\n"
                      "**2.** Clique no botão 'Comprar Tickets'\n"
                      "**3.** Digite a quantidade de tickets que deseja comprar\n"
                      "**4.** Pronto! Seus números serão gerados automaticamente",
                inline=False
            )

            embed.add_field(
                name="🎯 Comandos Úteis",
                value="• `/coins` - Ver quantos OwO Coins você tem\n"
                      "• `/raffle tickets` - Ver seus tickets comprados\n"
                      "• `/raffle info` - Ver informações do sorteio\n"
                      "• `/daily` - Coletar OwO Coins diários",
                inline=False
            )

            embed.add_field(
                name="ℹ️ Informações Importantes",
                value="• Cada ticket tem um número único\n"
                      "• Você pode comprar quantos tickets quiser\n"
                      "• O sorteio é totalmente aleatório\n"
                      "• O vencedor será anunciado neste canal",
                inline=False
            )

            embed.set_footer(text="Boa sorte a todos! 🍀")

            # Envia no canal especificado com menção aos cargos
            await channel.send(
                f"🎫 Novo sorteio disponível! {cargo_membro.mention} {cargo_visitante.mention}",
                embed=embed
            )
            await interaction.followup.send(f"Sorteio criado com sucesso! Anunciado em {channel.mention}", ephemeral=True)

        elif action == "end":
            # Verifica permissões de administrador
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("Você não tem permissão para finalizar sorteios!", ephemeral=True)
                return

            # Verifica se existe um sorteio ativo
            current_raffle = db_ref.child("servidores").child(guild_id).child("raffle").get()
            if not current_raffle or not current_raffle.get("active", False):
                await interaction.followup.send("Não há nenhum sorteio ativo para finalizar!", ephemeral=True)
                return

            # Busca os cargos configurados
            cargos = db_ref.child("servidores").child(guild_id).get()
            if cargos and cargos.get("cargo_membro") and cargos.get("cargo_visitante"):
                cargo_membro = interaction.guild.get_role(int(cargos.get("cargo_membro")))
                cargo_visitante = interaction.guild.get_role(int(cargos.get("cargo_visitante")))
            else:
                cargo_membro = None
                cargo_visitante = None

            # Lista todos os tickets vendidos
            participants = current_raffle.get("participants", {})
            if not participants:
                await interaction.followup.send("Não há participantes neste sorteio!", ephemeral=True)
                return

            # Cria lista de tickets
            all_tickets = []
            for user_id, user_tickets in participants.items():
                all_tickets.extend([(user_id, ticket_number) for ticket_number in user_tickets])

            # Sorteia um ticket
            winner_id, winning_ticket = random.choice(all_tickets)

            # Busca dados do vencedor
            winner_data = None
            winner_type = None

            # Procura em membros
            membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get() or {}
            for membro in membros.values():
                if membro.get("discord_id") == winner_id:
                    winner_data = membro
                    winner_type = "Membro"
                    break

            # Se não encontrou em membros, procura em visitantes
            if not winner_data:
                visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get() or {}
                for visitante in visitantes.values():
                    if visitante.get("discord_id") == winner_id:
                        winner_data = visitante
                        winner_type = "Visitante"
                        break

            # Cria embed do resultado
            embed = discord.Embed(
                title="🎉 Resultado do Sorteio!",
                description=f"**Prêmio:** {current_raffle['description']}\n\n"
                           f"**Ticket Vencedor:** #{winning_ticket}\n"
                           f"**Vencedor:** <@{winner_id}>",
                color=discord.Color.gold()
            )

            embed.add_field(
                name="Estatísticas",
                value=f"Total de Tickets Vendidos: {current_raffle['tickets_sold']}\n"
                      f"Total de Participantes: {len(participants)}",
                inline=False
            )

            # Marca o sorteio como inativo
            db_ref.child("servidores").child(guild_id).child("raffle").update({
                "active": False,
                "winner": {
                    "user_id": winner_id,
                    "ticket_number": winning_ticket
                }
            })

            # Envia o resultado no canal original do sorteio
            announce_channel = interaction.guild.get_channel(current_raffle["announce_channel"])
            if announce_channel:
                # Menciona os cargos se eles existirem
                mention_text = ""
                if cargo_membro and cargo_visitante:
                    mention_text = f"{cargo_membro.mention} {cargo_visitante.mention}\n\n"
                
                await announce_channel.send(
                    f"🎉 O sorteio foi finalizado! {mention_text}",
                    embed=embed
                )
                await interaction.followup.send(f"Sorteio finalizado com sucesso! Resultado anunciado em {announce_channel.mention}", ephemeral=True)
            else:
                # Se o canal não existir mais, envia no canal atual
                mention_text = ""
                if cargo_membro and cargo_visitante:
                    mention_text = f"{cargo_membro.mention} {cargo_visitante.mention}\n\n"
                
                await interaction.channel.send(
                    f"🎉 O sorteio foi finalizado! {mention_text}",
                    embed=embed
                )
                await interaction.followup.send("Sorteio finalizado com sucesso! O canal original não foi encontrado, então o resultado foi anunciado aqui.", ephemeral=True)

        elif action == "info":
            # Busca informações do sorteio atual
            current_raffle = db_ref.child("servidores").child(guild_id).child("raffle").get()
            if not current_raffle or not current_raffle.get("active", False):
                await interaction.followup.send("Não há nenhum sorteio ativo no momento!", ephemeral=True)
                return

            participants = current_raffle.get("participants", {})
            announce_channel = interaction.guild.get_channel(current_raffle["announce_channel"])
            
            embed = discord.Embed(
                title="🎫 Sorteio Atual",
                description=f"**Prêmio:** {current_raffle['description']}\n"
                           f"**Preço do Ticket:** {current_raffle['price']} <:owocoin:1364995129022349382>\n"
                           f"**Canal de Anúncios:** {announce_channel.mention if announce_channel else 'Canal não encontrado'}",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="Estatísticas",
                value=f"Total de Tickets Vendidos: {current_raffle['tickets_sold']}\n"
                      f"Total de Participantes: {len(participants)}",
                inline=False
            )

            # Mostra seus tickets se tiver algum
            user_tickets = participants.get(user_id, [])
            if user_tickets:
                embed.add_field(
                    name="Seus Tickets",
                    value=f"Você tem {len(user_tickets)} ticket(s)\n"
                          f"Números: {', '.join(f'#{t}' for t in sorted(user_tickets))}",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        elif action == "tickets":
            # Busca informações do sorteio atual
            current_raffle = db_ref.child("servidores").child(guild_id).child("raffle").get()
            if not current_raffle or not current_raffle.get("active", False):
                await interaction.followup.send("Não há nenhum sorteio ativo no momento!", ephemeral=True)
                return

            participants = current_raffle.get("participants", {})
            user_tickets = participants.get(user_id, [])

            if not user_tickets:
                await interaction.followup.send("Você não tem tickets para o sorteio atual!", ephemeral=True)
                return

            embed = discord.Embed(
                title="🎫 Seus Tickets",
                description=f"**Sorteio:** {current_raffle['description']}\n\n"
                           f"Você tem **{len(user_tickets)}** ticket(s)\n"
                           f"Números: {', '.join(f'#{t}' for t in sorted(user_tickets))}",
                color=discord.Color.blue()
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        elif action == "cancel":
            # Verifica permissões de administrador
            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("Você não tem permissão para cancelar sorteios!", ephemeral=True)
                return

            # Verifica se existe um sorteio ativo
            current_raffle = db_ref.child("servidores").child(guild_id).child("raffle").get()
            if not current_raffle or not current_raffle.get("active", False):
                await interaction.followup.send("Não há nenhum sorteio ativo para cancelar!", ephemeral=True)
                return

            # Busca os cargos configurados
            cargos = db_ref.child("servidores").child(guild_id).get()
            if cargos and cargos.get("cargo_membro") and cargos.get("cargo_visitante"):
                cargo_membro = interaction.guild.get_role(int(cargos.get("cargo_membro")))
                cargo_visitante = interaction.guild.get_role(int(cargos.get("cargo_visitante")))
            else:
                cargo_membro = None
                cargo_visitante = None

            # Lista todos os participantes
            participants = current_raffle.get("participants", {})
            if not participants:
                await interaction.followup.send("Não há participantes neste sorteio!", ephemeral=True)
                return

            # Processa reembolsos e bônus
            refund_summary = []
            total_refunded = 0
            total_bonus = 0

            for participant_id, tickets in participants.items():
                num_tickets = len(tickets)
                refund_amount = num_tickets * current_raffle["price"]  # Reembolso total
                bonus_amount = num_tickets * 10  # Bônus de consolação (10 coins por ticket)
                total_amount = refund_amount + bonus_amount

                # Busca dados do participante
                participant_data = None
                participant_ref = None

                # Procura em membros
                membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get() or {}
                for key, membro in membros.items():
                    if membro.get("discord_id") == participant_id:
                        participant_data = membro
                        participant_ref = db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key)
                        break

                # Se não encontrou em membros, procura em visitantes
                if not participant_data:
                    visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get() or {}
                    for key, visitante in visitantes.items():
                        if visitante.get("discord_id") == participant_id:
                            participant_data = visitante
                            participant_ref = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key)
                            break

                if participant_data and participant_ref:
                    current_coins = participant_data.get("owo_coins", 0)
                    new_balance = current_coins + total_amount
                    participant_ref.update({
                        "owo_coins": new_balance
                    })

                    refund_summary.append({
                        "user_id": participant_id,
                        "tickets": num_tickets,
                        "refund": refund_amount,
                        "bonus": bonus_amount,
                        "total": total_amount
                    })

                    total_refunded += refund_amount
                    total_bonus += bonus_amount

                    # Tenta enviar DM para o participante
                    try:
                        user = await interaction.client.fetch_user(int(participant_id))
                        embed = discord.Embed(
                            title="💰 Reembolso de Sorteio",
                            description=f"O sorteio **{current_raffle['description']}** foi cancelado.\n\n"
                                      f"**Seus Tickets:** {num_tickets}\n"
                                      f"**Reembolso:** {refund_amount} <:owocoin:1364995129022349382>\n"
                                      f"**Bônus de Consolação:** {bonus_amount} <:owocoin:1364995129022349382>\n"
                                      f"**Total Recebido:** {total_amount} <:owocoin:1364995129022349382>\n\n"
                                      f"Seu novo saldo: **{new_balance}** <:owocoin:1364995129022349382>",
                            color=discord.Color.blue()
                        )
                        await user.send(embed=embed)
                    except:
                        pass  # Ignora se não conseguir enviar DM

            # Cria embed do cancelamento
            embed = discord.Embed(
                title="❌ Sorteio Cancelado",
                description=f"O sorteio **{current_raffle['description']}** foi cancelado.\n\n"
                           f"**Total Reembolsado:** {total_refunded} <:owocoin:1364995129022349382>\n"
                           f"**Total em Bônus:** {total_bonus} <:owocoin:1364995129022349382>\n"
                           f"**Participantes:** {len(participants)}",
                color=discord.Color.red()
            )

            embed.add_field(
                name="📝 Detalhes",
                value="• Todos os tickets foram cancelados\n"
                      "• Coins foram reembolsados\n"
                      "• Bônus de 10 coins por ticket foi distribuído\n"
                      "• Participantes foram notificados por DM",
                inline=False
            )

            # Marca o sorteio como cancelado
            db_ref.child("servidores").child(guild_id).child("raffle").update({
                "active": False,
                "cancelled": True,
                "cancelled_at": {".sv": "timestamp"},
                "cancelled_by": user_id
            })

            # Envia o anúncio no canal original
            announce_channel = interaction.guild.get_channel(current_raffle["announce_channel"])
            if announce_channel:
                mention_text = ""
                if cargo_membro and cargo_visitante:
                    mention_text = f"{cargo_membro.mention} {cargo_visitante.mention}\n\n"
                
                await announce_channel.send(
                    f"⚠️ Atenção! O sorteio foi cancelado! {mention_text}",
                    embed=embed
                )
                await interaction.followup.send(f"Sorteio cancelado com sucesso! Anúncio enviado em {announce_channel.mention}", ephemeral=True)
            else:
                # Se o canal não existir mais, envia no canal atual
                mention_text = ""
                if cargo_membro and cargo_visitante:
                    mention_text = f"{cargo_membro.mention} {cargo_visitante.mention}\n\n"
                
                await interaction.channel.send(
                    f"⚠️ Atenção! O sorteio foi cancelado! {mention_text}",
                    embed=embed
                )
                await interaction.followup.send("Sorteio cancelado com sucesso! O canal original não foi encontrado, então o anúncio foi enviado aqui.", ephemeral=True)

    except Exception as e:
        print(f"Erro ao gerenciar sorteio: {e}")
        await interaction.followup.send("Ocorreu um erro ao processar o comando.", ephemeral=True)

class BetModal(discord.ui.Modal, title="Fazer Aposta"):
    def __init__(self, user_id: int, color: str):
        super().__init__()
        self.user_id = user_id
        self.color = color
        self.amount = discord.ui.TextInput(
            label="Quantidade de OwO Coins para apostar",
            placeholder="Digite o valor da sua aposta",
            required=True,
            min_length=1,
            max_length=10
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet_amount = int(self.amount.value)
            if bet_amount <= 0:
                await interaction.response.send_message("A aposta deve ser maior que 0!", ephemeral=True)
                return

            guild_id = str(interaction.guild.id)
            user_id = str(self.user_id)
            
            # Verifica se as apostas ainda estão abertas
            roulette_data = db_ref.child("servidores").child(guild_id).child("roulette").get()
            if not roulette_data or not roulette_data.get("betting_open", False):
                await interaction.response.send_message("As apostas já foram fechadas! Aguarde o próximo round.", ephemeral=True)
                return

            # Busca dados do usuário
            user_data = None
            user_ref = None
            
            # Procura em membros
            membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get() or {}
            for key, membro in membros.items():
                if membro.get("discord_id") == user_id:
                    user_data = membro
                    user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key)
                    break
            
            # Se não encontrou em membros, procura em visitantes
            if not user_data:
                visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get() or {}
                for key, visitante in visitantes.items():
                    if visitante.get("discord_id") == user_id:
                        user_data = visitante
                        user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key)
                        break

            if not user_data or not user_ref:
                await interaction.response.send_message("Erro ao encontrar seus dados!", ephemeral=True)
                return

            current_coins = user_data.get("owo_coins", 0)
            
            if bet_amount > current_coins:
                await interaction.response.send_message("Você não tem OwO Coins suficientes!", ephemeral=True)
                return

            # Atualiza os coins do usuário (deduz a aposta)
            new_balance = current_coins - bet_amount
            user_ref.update({
                "owo_coins": new_balance
            })

            # Registra a aposta
            if guild_id not in bot.auto_roulette.current_bets:
                bot.auto_roulette.current_bets[guild_id] = {}
            
            if user_id not in bot.auto_roulette.current_bets[guild_id]:
                bot.auto_roulette.current_bets[guild_id][user_id] = {}
            
            bot.auto_roulette.current_bets[guild_id][user_id][self.color] = {
                "amount": bet_amount,
                "user_ref": user_ref,
                "current_coins": new_balance
            }

            # Atualiza o total apostado no embed
            if guild_id in bot.auto_roulette.current_message:
                message = bot.auto_roulette.current_message[guild_id]
                embed = message.embeds[0]
                total_bet = sum(sum(bet["amount"] for bet in user_bets.values()) 
                              for user_bets in bot.auto_roulette.current_bets[guild_id].values())
                embed.set_field_at(1, name="💰 Total Apostado", value=f"{total_bet} <:owocoin:1364995129022349382>", inline=True)
                await message.edit(embed=embed)

            # Confirma a aposta
            color_emoji = "🔴" if self.color == "red" else "⚫" if self.color == "black" else "💚"
            color_name = "Vermelho" if self.color == "red" else "Preto" if self.color == "black" else "Verde"
            
            
            embed = discord.Embed(
                title="✅ Aposta Registrada",
                description=f"Você apostou **{bet_amount}** <:owocoin:1364995129022349382> no {color_emoji} **{color_name}**\n\n"
                          f"Seu novo saldo: **{new_balance}** <:owocoin:1364995129022349382>",
                color=discord.Color.green()
            )
            await update_quest_progress(guild_id, user_id, "play_roulette")
            
            message = await interaction.response.send_message(embed=embed, ephemeral=True)
            await asyncio.sleep(10)
            try:
                await message.delete()
            except:
                pass

        except ValueError:
            await interaction.response.send_message("Por favor, insira um número válido!", ephemeral=True)
        except Exception as e:
            print(f"Erro ao processar aposta: {e}")
            await interaction.response.send_message("Ocorreu um erro ao processar sua aposta!", ephemeral=True)

@bot.tree.command(name="setup_casino", description="Configura o canal do cassino e inicia a roleta automática")
@app_commands.default_permissions(administrator=True)
async def setup_casino(interaction: discord.Interaction, canal: discord.TextChannel):
    """
    Configura o canal do cassino e inicia a roleta automática.
    """
    # Verifica se é o usuário autorizado
    if interaction.user.id != "your_id_here":  # Seu ID
        await interaction.response.send_message("Apenas o dono do bot pode usar este comando!", ephemeral=True)
        return
        
    try:
        guild_id = str(interaction.guild.id)
        
        # Para a roleta atual se estiver rodando
        if hasattr(bot, 'auto_roulette'):
            await bot.auto_roulette.stop_roulette(guild_id)
        
        # Salva o ID do canal no banco de dados
        db_ref.child("servidores").child(guild_id).update({
            "casino_channel": str(canal.id)
        })
        
        # Salva o estado da roleta
        db_ref.child("roletas_ativas").child(guild_id).set({
            "channel_id": str(canal.id),
            "started_at": {".sv": "timestamp"}
        })
        
        # Cria o embed de boas-vindas
        embed = discord.Embed(
            title="🎰 Cassino OwO - Roleta Automática",
            description="Bem-vindo à Roleta Automática do Cassino OwO!\n\n"
                      "**Como Funciona:**\n"
                      "• A roleta roda automaticamente a cada 40 segundos\n"
                      "• Você tem 30 segundos para fazer suas apostas\n"
                      "• O resultado é mostrado nos 10 segundos restantes\n\n"
                      "**Chances e Multiplicadores:**\n"
                      "🔴 Vermelho - 50% - x2\n"
                      "⚫ Preto - 48% - x2\n"
                      "💚 Verde - 2% - x14",
            color=discord.Color.blurple()
        )
        
        # Envia a mensagem de boas-vindas no canal
        await canal.send(embed=embed)
        
        # Inicia a roleta automática
        if not hasattr(bot, 'auto_roulette'):
            bot.auto_roulette = AutoRoulette(bot)
        
        # Inicia a roleta em uma task separada
        bot.loop.create_task(bot.auto_roulette.run_roulette(canal, guild_id))
        
        await interaction.response.send_message(f"Canal do cassino configurado com sucesso em {canal.mention}! A roleta automática foi iniciada.", ephemeral=True)
        
    except Exception as e:
        print(f"Erro ao configurar canal do cassino: {e}")
        await interaction.response.send_message("Ocorreu um erro ao configurar o canal do cassino!", ephemeral=True)

@bot.tree.command(name="stop_casino", description="Para a roleta automática")
@app_commands.default_permissions(administrator=True)
async def stop_casino(interaction: discord.Interaction):
    """
    Para a roleta automática.
    """
    # Verifica se é o usuário autorizado
    if interaction.user.id != "your_id_here":  # Seu ID
        await interaction.response.send_message("Apenas o dono do bot pode usar este comando!", ephemeral=True)
        return
        
    try:
        guild_id = str(interaction.guild.id)
        
        if hasattr(bot, 'auto_roulette'):
            await bot.auto_roulette.stop_roulette(guild_id)
            
            # Remove o estado da roleta do Firebase
            db_ref.child("roletas_ativas").child(guild_id).delete()
            
            await interaction.response.send_message("A roleta automática foi parada com sucesso!", ephemeral=True)
        else:
            await interaction.response.send_message("A roleta automática não está rodando!", ephemeral=True)
            
    except Exception as e:
        print(f"Erro ao parar roleta: {e}")
        await interaction.response.send_message("Ocorreu um erro ao parar a roleta!", ephemeral=True)

class AutoRouletteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Sem timeout para rodar indefinidamente

    @discord.ui.button(label="🔴 Vermelho (x2)", style=discord.ButtonStyle.red, custom_id="red")
    async def red(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_bet(interaction, "red")

    @discord.ui.button(label="⚫ Preto (x2)", style=discord.ButtonStyle.secondary, custom_id="black")
    async def black(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_bet(interaction, "black")

    @discord.ui.button(label="💚 Verde (x14)", style=discord.ButtonStyle.green, custom_id="green")
    async def green(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.place_bet(interaction, "green")

    async def place_bet(self, interaction: discord.Interaction, color: str):
        guild_id = str(interaction.guild.id)
        
        # Verifica se as apostas estão abertas
        roulette_data = db_ref.child("servidores").child(guild_id).child("roulette").get()
        if not roulette_data or not roulette_data.get("betting_open", False):
            await interaction.response.send_message("As apostas estão fechadas! Aguarde o próximo round.", ephemeral=True)
            return
            
        # Verifica se a roleta está rodando
        if not bot.auto_roulette.is_running.get(guild_id, False):
            await interaction.response.send_message("A roleta não está funcionando neste momento!", ephemeral=True)
            return
            
        await interaction.response.send_modal(BetModal(interaction.user.id, color))

class AutoRoulette:
    def __init__(self, bot):
        self.bot = bot
        self.betting_time = 30  # 60 segundos para apostar
        self.result_time = 10   # 10 segundos para mostrar resultado
        self.is_running = {}    # Controle por servidor
        self.current_message = {}  # Mensagem atual por servidor
        self.current_bets = {}   # Apostas atuais por servidor
        self.history = {}       # Histórico de resultados por servidor (máximo 10)
        self.last_result_message = {}  # Última mensagem de resultado por servidor

    async def cleanup_old_messages(self, channel, guild_id):
        """Limpa mensagens antigas da roleta no canal"""
        try:
            # Busca as últimas 100 mensagens no canal
            async for message in channel.history(limit=100):
                # Se a mensagem é do bot e contém uma roleta ou resultado
                if message.author == self.bot.user and (
                    "🎰 Roleta OwO" in message.content or 
                    "Resultado da Roleta" in message.content or
                    (message.embeds and any(
                        "🎰 Roleta OwO" in embed.title or 
                        "Resultado da Roleta" in (embed.title or "") 
                        for embed in message.embeds
                    ))
                ):
                    try:
                        await message.delete()
                    except:
                        pass
        except Exception as e:
            print(f"Erro ao limpar mensagens antigas: {e}")

    def format_time(self, seconds):
        return f"{seconds//60:02d}:{seconds%60:02d}"

    def get_history_display(self, guild_id: str) -> str:
        if guild_id not in self.history or not self.history[guild_id]:
            return "Nenhum resultado ainda"
        
        history = self.history[guild_id]
        display = []
        for result in history:
            if result == "red":
                display.append("🔴")
            elif result == "black":
                display.append("⚫")
            else:
                display.append("💚")
        return " ".join(display)

    async def update_timer(self, channel, guild_id, message, start_time, duration):
        while True:
            if not self.is_running.get(guild_id, False):
                break
                
            current_time = int(time.time())
            remaining = max(0, duration - (current_time - start_time))
            
            if remaining <= 0:
                break
                
            embed = message.embeds[0]
            embed.set_field_at(0, name="⏰ Tempo Restante", value=self.format_time(remaining), inline=True)
            
            try:
                await message.edit(embed=embed)
            except:
                break
                
            await asyncio.sleep(1)

    async def run_roulette(self, channel, guild_id):
        # Limpa mensagens antigas antes de começar
        await self.cleanup_old_messages(channel, guild_id)
        
        self.is_running[guild_id] = True
        self.current_bets[guild_id] = {}
        if guild_id not in self.history:
            self.history[guild_id] = []
        
        while self.is_running.get(guild_id, False):
            try:
                # Limpa apostas da rodada anterior
                self.current_bets[guild_id] = {}
                
                # Limpa mensagens antigas
                if guild_id in self.current_message:
                    try:
                        await self.current_message[guild_id].delete()
                    except:
                        pass
                
                if guild_id in self.last_result_message:
                    try:
                        await self.last_result_message[guild_id].delete()
                    except:
                        pass

                # Reseta o estado no banco de dados
                db_ref.child("servidores").child(guild_id).child("roulette").set({
                    "betting_open": True,
                    "current_bets": {},
                    "total_bet": 0
                })
                
                # Abre as apostas
                start_time = int(time.time())
                
                embed = discord.Embed(
                    title="🎰 Roleta OwO",
                    description="**APOSTAS ABERTAS!**\n\n"
                              "🔴 **Vermelho** (Números Ímpares: 1,3,5,...,49) - 50% - x2\n"
                              "⚫ **Preto** (Números Pares: 2,4,6,...,48) - 48% - x2\n"
                              "💚 **Verde** (Número 0) - 2% - x14\n\n"
                              "Clique nos botões abaixo para apostar!",
                    color=discord.Color.blue()
                )
                embed.add_field(name="⏰ Tempo Restante", value=self.format_time(self.betting_time), inline=True)
                embed.add_field(name="💰 Total Apostado", value="0 <:owocoin:1364995129022349382>", inline=True)
                
                # Adiciona o histórico
                history_display = self.get_history_display(guild_id)
                embed.add_field(name="📜 Últimos Resultados", value=history_display, inline=False)
                
                # Atualiza status no banco de dados
                db_ref.child("servidores").child(guild_id).child("roulette").update({
                    "betting_open": True,
                    "current_bets": {},
                    "total_bet": 0
                })
                
                # Envia nova mensagem com botões
                message = await channel.send(embed=embed, view=AutoRouletteView())
                self.current_message[guild_id] = message
                
                # Atualiza o timer
                await self.update_timer(channel, guild_id, message, start_time, self.betting_time)
                
                if not self.is_running.get(guild_id, False):
                    break
                
                # Fecha as apostas
                db_ref.child("servidores").child(guild_id).child("roulette").update({
                    "betting_open": False
                })
                
                # Gera o resultado
                result = random.randint(0, 49)  # Gera um número entre 0 e 49
                if result == 0:
                    result_color = "green"
                    emoji = "💚"
                    color_name = f"Verde (0)"
                    multiplier = 14
                elif result % 2 == 1:  # Números ímpares (1,3,5,...,49)
                    result_color = "red"
                    emoji = "🔴"
                    color_name = f"Vermelho ({result})"
                    multiplier = 2
                else:  # Números pares (2,4,6,...,48)
                    result_color = "black"
                    emoji = "⚫"
                    color_name = f"Preto ({result})"
                    multiplier = 2
                
                # Atualiza o histórico
                self.history[guild_id].append(result_color)
                if len(self.history[guild_id]) > 10:
                    self.history[guild_id].pop(0)
                
                # Processa os resultados
                bets = self.current_bets.get(guild_id, {})
                total_bet = sum(sum(bet["amount"] for bet in user_bets.values()) for user_bets in bets.values())
                winners = []
                total_won = 0
                
                result_embed = discord.Embed(
                    title=f"🎰 Resultado da Roleta {emoji}",
                    description=f"**Caiu no: {color_name}!**\n\n"
                               f"Total Apostado: **{total_bet}** <:owocoin:1364995129022349382>",
                    color=discord.Color.green() if result_color == "green" else discord.Color.red() if result_color == "red" else discord.Color.dark_gray()
                )
                
                # Adiciona o histórico ao resultado
                history_display = self.get_history_display(guild_id)
                result_embed.add_field(name="📜 Últimos Resultados", value=history_display, inline=False)
                
                for user_id, user_bets in bets.items():
                    for bet_color, bet_data in user_bets.items():
                        user = await self.bot.fetch_user(int(user_id))
                        if bet_color == result_color:
                            winnings = bet_data["amount"] * multiplier
                            total_won += winnings
                            winners.append(f"{user.mention} ganhou **{winnings}** <:owocoin:1364995129022349382>")
                            
                            # Atualiza os coins do usuário
                            user_ref = bet_data["user_ref"]
                            current_coins = bet_data["current_coins"]
                            new_balance = current_coins + winnings
                            user_ref.update({
                                "owo_coins": new_balance
                            })
                            
                            # Atualiza a missão de vitória
                            await update_quest_progress(guild_id, user_id, "win_roulette")
                        else:
                            # Já descontou os coins quando apostou, não precisa fazer nada
                            pass
                
                if winners:
                    result_embed.add_field(
                        name="🏆 Vencedores",
                        value="\n".join(winners),
                        inline=False
                    )
                else:
                    result_embed.add_field(
                        name="<:harulost:1365057522645471405> Resultado",
                        value="Ninguém ganhou nesta rodada!",
                        inline=False
                    )
                
                # Mostra o resultado
                result_message = await channel.send(embed=result_embed)
                self.last_result_message[guild_id] = result_message
                
                # Aguarda antes da próxima rodada
                await asyncio.sleep(self.result_time)
                
            except Exception as e:
                print(f"Erro na roleta automática: {e}")
                await asyncio.sleep(5)  # Espera um pouco antes de tentar novamente

    async def stop_roulette(self, guild_id):
        self.is_running[guild_id] = False
        if guild_id in self.current_message:
            try:
                await self.current_message[guild_id].delete()
            except:
                pass
            del self.current_message[guild_id]
        if guild_id in self.last_result_message:
            try:
                await self.last_result_message[guild_id].delete()
            except:
                pass
            del self.last_result_message[guild_id]
        if guild_id in self.current_bets:
            del self.current_bets[guild_id]

# Sistema de Mineração
MINING_ORES = {
    "carvão": {
        "name": "Carvão",
        "emoji": "⚫",
        "value": 5,
        "rarity": 0.4,  # 40% de chance
        "energy_cost": 1
    },
    "ferro": {
        "name": "Ferro",
        "emoji": "⚙️",
        "value": 15,
        "rarity": 0.3,  # 30% de chance
        "energy_cost": 2
    },
    "ouro": {
        "name": "Ouro",
        "emoji": "💰",
        "value": 30,
        "rarity": 0.15,  # 15% de chance
        "energy_cost": 3
    },
    "diamante": {
        "name": "Diamante",
        "emoji": "💎",
        "value": 100,
        "rarity": 0.1,  # 10% de chance
        "energy_cost": 3
    },
    "esmeralda": {
        "name": "Esmeralda",
        "emoji": "💚",
        "value": 150,
        "rarity": 0.05,  # 5% de chance
        "energy_cost": 3
    }
}

# Configurações do sistema de mineração
MAX_ENERGY = 25
ENERGY_REGEN_RATE = 1  # Energia regenerada por minuto
ENERGY_REGEN_INTERVAL = 60  # Intervalo de regeneração em segundos

async def get_user_mining_data(guild_id: str, user_id: str) -> dict:
    """
    Obtém ou cria os dados de mineração do usuário.
    """
    user_data = None
    user_ref = None
    
    # Busca em membros
    membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get() or {}
    for key, membro in membros.items():
        if membro.get("discord_id") == user_id:
            user_data = membro
            user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key)
            break
    
    # Busca em visitantes se necessário
    if not user_data:
        visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get() or {}
        for key, visitante in visitantes.items():
            if visitante.get("discord_id") == user_id:
                user_data = visitante
                user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key)
                break
    
    if not user_data:
        return None, None
    
    # Inicializa dados de mineração se não existirem
    if "mining_data" not in user_data:
        user_data["mining_data"] = {
            "energy": MAX_ENERGY,
            "last_energy_update": int(time.time()),
            "inventory": {}
        }
        user_ref.update({"mining_data": user_data["mining_data"]})
    
    return user_data, user_ref

async def update_user_energy(user_data: dict, user_ref) -> int:
    """
    Atualiza a energia do usuário baseado no tempo passado.
    Retorna a energia atual.
    """
    current_time = int(time.time())
    last_update = user_data["mining_data"]["last_energy_update"]
    time_passed = current_time - last_update
    
    # Calcula energia regenerada
    energy_regen = (time_passed // ENERGY_REGEN_INTERVAL) * ENERGY_REGEN_RATE
    current_energy = min(MAX_ENERGY, user_data["mining_data"]["energy"] + energy_regen)
    
    # Atualiza no banco de dados
    user_data["mining_data"]["energy"] = current_energy
    user_data["mining_data"]["last_energy_update"] = current_time
    user_ref.update({"mining_data": user_data["mining_data"]})
    
    return current_energy

def get_random_ore() -> tuple[str, dict]:
    """
    Retorna um minério aleatório baseado nas probabilidades.
    """
    rand = random.random()
    cumulative = 0
    
    for ore_id, ore_data in MINING_ORES.items():
        cumulative += ore_data["rarity"]
        if rand <= cumulative:
            return ore_id, ore_data
    
    return "carvão", MINING_ORES["carvão"]  # Fallback para carvão

@bot.tree.command(name="setup_mining", description="Configura o canal de mineração")
@app_commands.default_permissions(administrator=True)
async def setup_mining(interaction: discord.Interaction, canal: discord.TextChannel):
    """
    Configura um canal como canal de mineração.
    """
    await interaction.response.defer()
    try:
        guild_id = str(interaction.guild.id)
        
        # Verifica se já existe um canal de mineração
        mining_channels = db_ref.child("servidores").child(guild_id).child("mining_channels").get() or {}
        if str(canal.id) in mining_channels:
            await interaction.followup.send("Este canal já está configurado como canal de mineração!", ephemeral=True)
            return
        
        # Adiciona o canal à lista de canais de mineração
        db_ref.child("servidores").child(guild_id).child("mining_channels").update({
            str(canal.id): {
                "name": canal.name,
                "setup_by": str(interaction.user.id),
                "setup_at": int(time.time())
            }
        })
        
        # Cria o embed de boas-vindas
        embed = discord.Embed(
            title="⛏️ Canal de Mineração",
            description="Bem-vindo ao canal de mineração!\n\n"
                       "**Como Funciona:**\n"
                       "• Use `/mine` para minerar\n"
                       "• Cada mineração gasta energia\n"
                       "• A energia se regenera com o tempo\n"
                       "• Use `/energy` para ver sua energia\n"
                       "• Use `/mining_inventory` para ver seu inventário\n"
                       "• Use `/mining_shop` para comprar uma picareta melhor\n"
                       "• Use `/sell_ores` para vender seus minérios\n\n"
                       "**Minérios Disponíveis:**\n"
                       "⚫ Carvão - 5 coins\n"
                       "⚙️ Ferro - 15 coins\n"
                       "💰 Ouro - 30 coins\n"
                       "💎 Diamante - 100 coins\n"
                       "💚 Esmeralda - 150 coins",
            color=discord.Color.blue()
        )
        
        await canal.send(embed=embed)
        await interaction.followup.send(f"Canal {canal.mention} configurado como canal de mineração!", ephemeral=True)
        
    except Exception as e:
        print(f"Erro ao configurar canal de mineração: {e}")
        await interaction.followup.send("Ocorreu um erro ao configurar o canal de mineração.", ephemeral=True)



@bot.tree.command(name="sell_ores", description="Vende seus minérios minerados")
async def sell_ores(interaction: discord.Interaction):
    """
    Permite ao usuário vender seus minérios minerados.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        guild_id = str(interaction.guild.id)
        user_data, user_ref = await get_user_mining_data(guild_id, str(interaction.user.id))
        
        if not user_data:
            await interaction.followup.send("Você não está registrado no servidor!", ephemeral=True)
            return
        
        inventory = user_data["mining_data"].get("inventory", {})
        if not inventory:
            await interaction.followup.send("Você não tem minérios para vender!", ephemeral=True)
            return
        
        # Calcula o valor total
        total_value = 0
        for ore_id, amount in inventory.items():
            total_value += MINING_ORES[ore_id]["value"] * amount
        
        # Atualiza os coins do usuário
        current_coins = user_data.get("owo_coins", 0)
        user_data["owo_coins"] = current_coins + total_value
        user_data["mining_data"]["inventory"] = {}
        user_ref.update({
            "owo_coins": user_data["owo_coins"],
            "mining_data": user_data["mining_data"]
        })
        
        # Cria embed de resultado
        embed = discord.Embed(
            title="💰 Venda de Minérios",
            description=f"Você vendeu todos os seus minérios por **{total_value}** <:owocoin:1364995129022349382>!",
            color=discord.Color.green()
        )
        
        # Adiciona detalhes da venda
        details = []
        for ore_id, amount in inventory.items():
            ore_data = MINING_ORES[ore_id]
            details.append(f"{ore_data['emoji']} **{ore_data['name']}** x{amount} = {ore_data['value'] * amount} coins")
        
        embed.add_field(
            name="Detalhes da Venda",
            value="\n".join(details),
            inline=False
        )
        
        embed.add_field(
            name="Novo Saldo",
            value=f"**{current_coins + total_value}** <:owocoin:1364995129022349382>",
            inline=False
        )
        
        message = await interaction.followup.send(embed=embed)
        await asyncio.sleep(20)
        try:
            await message.delete()
        except:
            pass
        
    except Exception as e:
        print(f"Erro ao vender minérios: {e}")
        await interaction.followup.send("Ocorreu um erro ao tentar vender seus minérios.", ephemeral=True)



# Sistema de Picaretas
MINING_PICKAXES = {
    "wooden": {
        "name": "Picareta de Madeira",
        "emoji": "🪵",
        "price": 0,  # Gratuita
        "multiplier": 1.0,  # Multiplicador base
        "description": "Picareta básica, sem bônus"
    },
    "stone": {
        "name": "Picareta de Pedra",
        "emoji": "🪨",
        "price": 500,
        "multiplier": 1.2,  # +20% de chance
        "description": "Aumenta em 20% a chance de encontrar minérios raros"
    },
    "iron": {
        "name": "Picareta de Ferro",
        "emoji": "⚒️",
        "price": 2000,
        "multiplier": 1.5,  # +50% de chance
        "description": "Aumenta em 50% a chance de encontrar minérios raros"
    },
    "gold": {
        "name": "Picareta de Ouro",
        "emoji": "⛏️",
        "price": 5000,
        "multiplier": 2.0,  # +100% de chance
        "description": "Aumenta em 100% a chance de encontrar minérios raros"
    },
    "diamond": {
        "name": "Picareta de Diamante",
        "emoji": "💎",
        "price": 10000,
        "multiplier": 3.0,  # +200% de chance
        "description": "Aumenta em 200% a chance de encontrar minérios raros"
    }
}

def get_random_ore(pickaxe_multiplier: float = 1.0) -> tuple[str, dict]:
    """
    Retorna um minério aleatório baseado nas probabilidades e multiplicador da picareta.
    """
    rand = random.random()
    cumulative = 0
    
    # Aplica o multiplicador da picareta nas probabilidades
    adjusted_rarities = {}
    total_rarity = 0
    for ore_id, ore_data in MINING_ORES.items():
        # Aplica o multiplicador apenas para minérios raros (ouro, diamante, esmeralda)
        if ore_id in ["ouro", "diamante", "esmeralda"]:
            adjusted_rarities[ore_id] = ore_data["rarity"] * pickaxe_multiplier
        else:
            adjusted_rarities[ore_id] = ore_data["rarity"]
        total_rarity += adjusted_rarities[ore_id]
    
    # Normaliza as probabilidades
    for ore_id in adjusted_rarities:
        adjusted_rarities[ore_id] /= total_rarity
    
    # Seleciona o minério
    for ore_id, adjusted_rarity in adjusted_rarities.items():
        cumulative += adjusted_rarity
        if rand <= cumulative:
            return ore_id, MINING_ORES[ore_id]
    
    return "carvão", MINING_ORES["carvão"]  # Fallback para carvão

@bot.tree.command(name="mining_shop", description="Abre a loja de mineração")
async def mining_shop(interaction: discord.Interaction):
    """
    Mostra a loja de mineração com picaretas disponíveis.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        guild_id = str(interaction.guild.id)
        user_data, user_ref = await get_user_mining_data(guild_id, str(interaction.user.id))
        
        if not user_data:
            await interaction.followup.send("Você não está registrado no servidor!", ephemeral=True)
            return
        
        # Obtém a picareta atual do usuário
        current_pickaxe = user_data["mining_data"].get("pickaxe", "wooden")
        current_coins = user_data.get("owo_coins", 0)
        current_energy = user_data["mining_data"].get("energy", 0)
        
        # Cria o embed da loja
        embed = discord.Embed(
            title="⛏️ Loja de Mineração",
            description="Compre picaretas melhores para aumentar suas chances de encontrar minérios raros!",
            color=discord.Color.blue()
        )
        
        # Adiciona informações do usuário
        embed.add_field(
            name="Seu Saldo",
            value=f"**{current_coins}** <:owocoin:1364995129022349382>",
            inline=False
        )
        
        embed.add_field(
            name="Sua Picareta Atual",
            value=f"{MINING_PICKAXES[current_pickaxe]['emoji']} **{MINING_PICKAXES[current_pickaxe]['name']}**\n{MINING_PICKAXES[current_pickaxe]['description']}",
            inline=False
        )

        # Adiciona item de energia
        energy_status = "✅ Disponível" if current_coins >= 2500 else "❌ Insuficiente"
        embed.add_field(
            name="⚡ Poção de Energia",
            value=f"Recupera toda sua energia\n"
                  f"Preço: * 2500** <:owocoin:1364995129022349382>\n"
                  f"Status: {energy_status}",
            inline=False
        )
        
        # Adiciona as picaretas disponíveis
        for pickaxe_id, pickaxe_data in MINING_PICKAXES.items():
            # Pula a picareta de madeira se o usuário já tiver uma melhor
            if pickaxe_id == "wooden" and current_pickaxe != "wooden":
                continue
                
            # Verifica se o usuário já tem esta picareta
            if pickaxe_id == current_pickaxe:
                status = "✅ Equipada"
            elif current_coins >= pickaxe_data["price"]:
                status = "🛒 Disponível"
            else:
                status = "❌ Insuficiente"
            
            embed.add_field(
                name=f"{pickaxe_data['emoji']} {pickaxe_data['name']}",
                value=f"Preço: **{pickaxe_data['price']}** <:owocoin:1364995129022349382>\n"
                      f"Bônus: **+{int((pickaxe_data['multiplier'] - 1) * 100)}%** chance de minérios raros\n"
                      f"Status: {status}",
                inline=True
            )
        
        # Cria a view com os botões de compra
        view = MiningShopView(user_data, user_ref, current_pickaxe, current_coins)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
    except Exception as e:
        print(f"Erro ao mostrar loja de mineração: {e}")
        await interaction.followup.send("Ocorreu um erro ao tentar mostrar a loja de mineração.", ephemeral=True)

class MiningShopView(discord.ui.View):
    def __init__(self, user_data: dict, user_ref, current_pickaxe: str, current_coins: int):
        super().__init__(timeout=180)  # 3 minutos
        self.user_data = user_data
        self.user_ref = user_ref
        self.current_pickaxe = current_pickaxe
        self.current_coins = current_coins
        
        # Adiciona botão de energia
        energy_button = discord.ui.Button(
            label="Comprar Poção de Energia",
            style=discord.ButtonStyle.green if current_coins >= 2500 else discord.ButtonStyle.red,
            disabled=current_coins < 2500,
            custom_id="buy_energy"
        )
        energy_button.callback = self.create_energy_callback()
        self.add_item(energy_button)
        
        # Adiciona botões para cada picareta
        for pickaxe_id, pickaxe_data in MINING_PICKAXES.items():
            # Pula a picareta de madeira se o usuário já tiver uma melhor
            if pickaxe_id == "wooden" and current_pickaxe != "wooden":
                continue
                
            # Verifica se o usuário já tem esta picareta
            if pickaxe_id == current_pickaxe:
                button = discord.ui.Button(
                    label=f"Equipada: {pickaxe_data['name']}",
                    style=discord.ButtonStyle.gray,
                    disabled=True,
                    custom_id=f"buy_{pickaxe_id}"
                )
            elif current_coins >= pickaxe_data["price"]:
                button = discord.ui.Button(
                    label=f"Comprar: {pickaxe_data['name']}",
                    style=discord.ButtonStyle.green,
                    custom_id=f"buy_{pickaxe_id}"
                )
            else:
                button = discord.ui.Button(
                    label=f"Insuficiente: {pickaxe_data['name']}",
                    style=discord.ButtonStyle.red,
                    disabled=True,
                    custom_id=f"buy_{pickaxe_id}"
                )
            
            button.callback = self.create_callback(pickaxe_id, pickaxe_data)
            self.add_item(button)

    def create_energy_callback(self):
        async def callback(interaction: discord.Interaction):
            try:
                # Verifica se o usuário ainda tem coins suficientes
                if self.current_coins < 2500:
                    await interaction.response.send_message(
                        "Você não tem OwO Coins suficientes para comprar a poção de energia!",
                        ephemeral=True
                    )
                    return
                
                # Atualiza a energia do usuário
                self.user_data["mining_data"]["energy"] = MAX_ENERGY
                self.user_data["owo_coins"] = self.current_coins - 2500
                self.user_ref.update({
                    "mining_data": self.user_data["mining_data"],
                    "owo_coins": self.user_data["owo_coins"]
                })
                
                # Cria embed de confirmação
                embed = discord.Embed(
                    title="✅ Poção de Energia Comprada!",
                    description="Sua energia foi restaurada completamente!",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="Novo Saldo",
                    value=f"**{self.current_coins - 2500}** <:owocoin:1364995129022349382>",
                    inline=False
                )
                
                embed.add_field(
                    name="Energia",
                    value=f"**{MAX_ENERGY}/{MAX_ENERGY}** ⚡",
                    inline=False
                )
                
                # Desabilita todos os botões
                for child in self.children:
                    child.disabled = True
                
                message = await interaction.response.edit_message(embed=embed, view=self)
                await asyncio.sleep(20)
                try:
                    await message.delete()
                except:
                    pass
                
            except Exception as e:
                print(f"Erro ao comprar poção de energia: {e}")
                await interaction.response.send_message(
                    "Ocorreu um erro ao tentar comprar a poção de energia.",
                    ephemeral=True
                )
        
        return callback

    def create_callback(self, pickaxe_id: str, pickaxe_data: dict):
        async def callback(interaction: discord.Interaction):
            try:
                # Verifica se o usuário ainda tem coins suficientes
                if self.current_coins < pickaxe_data["price"]:
                    await interaction.response.send_message(
                        "Você não tem OwO Coins suficientes para comprar esta picareta!",
                        ephemeral=True
                    )
                    return
                
                # Atualiza a picareta do usuário
                self.user_data["mining_data"]["pickaxe"] = pickaxe_id
                self.user_data["owo_coins"] = self.current_coins - pickaxe_data["price"]
                self.user_ref.update({
                    "mining_data": self.user_data["mining_data"],
                    "owo_coins": self.user_data["owo_coins"]
                })
                
                # Cria embed de confirmação
                embed = discord.Embed(
                    title="✅ Picareta Comprada!",
                    description=f"Você comprou a {pickaxe_data['emoji']} **{pickaxe_data['name']}**!",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="Novo Saldo",
                    value=f"**{self.current_coins - pickaxe_data['price']}** <:owocoin:1364995129022349382>",
                    inline=False
                )
                
                embed.add_field(
                    name="Bônus",
                    value=f"+{int((pickaxe_data['multiplier'] - 1) * 100)}% de chance de encontrar minérios raros",
                    inline=False
                )
                
                # Desabilita todos os botões
                for child in self.children:
                    child.disabled = True
                
                message = await interaction.response.edit_message(embed=embed, view=self)
                await asyncio.sleep(20)
                try:
                    await message.delete()
                except:
                    pass
                
            except Exception as e:
                print(f"Erro ao comprar picareta: {e}")
                await interaction.response.send_message(
                    "Ocorreu um erro ao tentar comprar a picareta.",
                    ephemeral=True
                )
        
        return callback

# Modifica a função mine para usar o multiplicador da picareta
@bot.tree.command(name="mine", description="Mina minérios no canal de mineração")
async def mine(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        guild_id = str(interaction.guild.id)
        channel_id = str(interaction.channel.id)
        user_id = str(interaction.user.id)
        
        # Verifica se o canal é um canal de mineração
        mining_channels = db_ref.child("servidores").child(guild_id).child("mining_channels").get() or {}
        if channel_id not in mining_channels:
            await interaction.followup.send("Este comando só pode ser usado em canais de mineração!", ephemeral=True)
            return
        
        # Obtém dados do usuário
        user_data, user_ref = await get_user_mining_data(guild_id, user_id)
        
        if not user_data:
            await interaction.followup.send("Você não está registrado no servidor!", ephemeral=True)
            return
        
        # Atualiza energia
        current_energy = await update_user_energy(user_data, user_ref)
        
        if current_energy <= 0:
            await interaction.followup.send("Você está sem energia! Aguarde um pouco para recuperar.", ephemeral=True)
            return
        
        # Obtém a picareta atual
        current_pickaxe = user_data["mining_data"].get("pickaxe", "wooden")
        pickaxe_multiplier = MINING_PICKAXES[current_pickaxe]["multiplier"]
        
        # Mina o minério
        ore_type, ore_data = get_random_ore(pickaxe_multiplier)
        
        # Atualiza o inventário
        inventory = user_data["mining_data"].get("inventory", {})
        inventory[ore_type] = inventory.get(ore_type, 0) + 1
        
        # Atualiza energia
        new_energy = current_energy - ore_data["energy_cost"]
        user_data["mining_data"]["energy"] = new_energy
        user_data["mining_data"]["inventory"] = inventory
        
        # Salva no banco de dados
        user_ref.update({"mining_data": user_data["mining_data"]})
        
        # Atualiza o progresso da missão
        await update_quest_progress(guild_id, user_id, "mine_ores", 1, ore_type)
        
        # Envia mensagem de sucesso
        embed = discord.Embed(
            title="⛏️ Mineração",
            description=f"Você minerou {ore_data['emoji']} **{ore_data['name']}**!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Energia Restante",
            value=f"{new_energy}/{MAX_ENERGY}",
            inline=False
        )
        message = await interaction.followup.send(embed=embed)
        await asyncio.sleep(10)
        try:
            await message.delete()
        except:
            pass
        
    except Exception as e:
        print(f"Erro ao minerar: {e}")
        await interaction.followup.send("Ocorreu um erro ao tentar minerar. Tente novamente mais tarde.", ephemeral=True)

@bot.tree.command(name="energy", description="Mostra sua energia atual de mineração")
async def energy(interaction: discord.Interaction):
    """
    Mostra a energia atual do usuário para mineração.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        guild_id = str(interaction.guild.id)
        user_data, user_ref = await get_user_mining_data(guild_id, str(interaction.user.id))
        
        if not user_data:
            await interaction.followup.send("Você não está registrado no servidor!", ephemeral=True)
            return
        
        # Atualiza energia
        current_energy = await update_user_energy(user_data, user_ref)
        
        # Calcula tempo para regeneração completa
        energy_to_regen = MAX_ENERGY - current_energy
        minutes_to_full = energy_to_regen // ENERGY_REGEN_RATE
        
        # Cria embed de energia
        embed = discord.Embed(
            title="⚡ Energia de Mineração",
            description=f"Energia atual de {interaction.user.mention}",
            color=discord.Color.blue()
        )
        
        # Adiciona barra de progresso
        progress = int((current_energy / MAX_ENERGY) * 10)
        progress_bar = "█" * progress + "░" * (10 - progress)
        
        embed.add_field(
            name="Energia Atual",
            value=f"**{current_energy}/{MAX_ENERGY}**\n`{progress_bar}`",
            inline=False
        )
        
        # Adiciona informações de regeneração
        if current_energy < MAX_ENERGY:
            embed.add_field(
                name="Regeneração",
                value=f"• Regenera **{ENERGY_REGEN_RATE}** energia por minuto\n"
                      f"• Tempo para regeneração completa: **{minutes_to_full}** minutos",
                inline=False
            )
        else:
            embed.add_field(
                name="Status",
                value="✅ Energia máxima!",
                inline=False
            )
        
        # Adiciona informações da picareta
        current_pickaxe = user_data["mining_data"].get("pickaxe", "wooden")
        pickaxe_data = MINING_PICKAXES[current_pickaxe]
        embed.add_field(
            name="Picareta Atual",
            value=f"{pickaxe_data['emoji']} **{pickaxe_data['name']}**\n"
                  f"+{int((pickaxe_data['multiplier'] - 1) * 100)}% de chance de minérios raros",
            inline=False
        )
        
        message = await interaction.followup.send(embed=embed, ephemeral=True)
        await asyncio.sleep(15)
        try:
            await message.delete()
        except:
            pass
        
    except Exception as e:
        print(f"Erro ao mostrar energia: {e}")
        await interaction.followup.send("Ocorreu um erro ao tentar mostrar sua energia.", ephemeral=True)

@bot.tree.command(name="mining_inventory", description="Mostra seu inventário de mineração")
async def mining_inventory(interaction: discord.Interaction):
    """
    Mostra o inventário de mineração do usuário.
    """
    await interaction.response.defer(ephemeral=True)
    try:
        guild_id = str(interaction.guild.id)
        user_data, user_ref = await get_user_mining_data(guild_id, str(interaction.user.id))
        
        if not user_data:
            await interaction.followup.send("Você não está registrado no servidor!", ephemeral=True)
            return
        
        # Atualiza energia
        current_energy = await update_user_energy(user_data, user_ref)
        
        inventory = user_data["mining_data"].get("inventory", {})
        if not inventory:
            message1 = await interaction.followup.send("Seu inventário está vazio!", ephemeral=True)
            await asyncio.sleep(10)
            try:
                await message1.delete()
            except:
                pass
            return
        
        # Cria embed do inventário
        embed = discord.Embed(
            title="🎒 Inventário de Mineração",
            description=f"Minérios coletados por {interaction.user.mention}",
            color=discord.Color.blue()
        )
        
        # Adiciona informações de energia
        embed.add_field(
            name="⚡ Energia",
            value=f"{current_energy}/{MAX_ENERGY}",
            inline=False
        )
        
        # Calcula valor total
        # Adiciona minérios
        for ore_id, amount in inventory.items():
            ore_data = MINING_ORES[ore_id]
            embed.add_field(
                name=f"{ore_data['emoji']} {ore_data['name']}",
                value=f"Quantidade: **{amount}**\nValor: **{ore_data['value'] * amount}** <:owocoin:1364995129022349382>",
                inline=True
            )
        
        message = await interaction.followup.send(embed=embed, ephemeral=True)
        await asyncio.sleep(20)
        try:
            await message.delete()
        except:
            pass
        
    except Exception as e:
        print(f"Erro ao mostrar inventário: {e}")
        await interaction.followup.send("Ocorreu um erro ao tentar mostrar seu inventário.", ephemeral=True)

# Dicionário de missões diárias possíveis
DAILY_QUESTS = {
    "message_count_small": {
        "title": "Conversante",
        "description": "Envie {count} mensagens no servidor",
        "rewards": {
            "coins": 100,
            "xp": 50
        }
    },
    "message_count_medium": {
        "title": "Conversador de mais",
        "description": "Envie {count} mensagens no servidor",
        "rewards": {
            "coins": 200,
            "xp": 100
        }
    },
    "message_count_large": {
        "title": "Falante pra caramba",
        "description": "Envie {count} mensagens no servidor",
        "rewards": {
            "coins": 300,
            "xp": 150
        }
    },
    "mine_ores_small": {
        "title": "Começando a Picaretar",
        "description": "Minere {count} minérios",
        "rewards": {
            "coins": 150,
            "xp": 75
        }
    },
    "mine_ores_medium": {
        "title": "Picaretando mais!",
        "description": "Minere {count} minérios",
        "rewards": {
            "coins": 250,
            "xp": 125
        }
    },
    "mine_ores_large": {
        "title": "Mestre da Picareta",
        "description": "Minere {count} minérios",
        "rewards": {
            "coins": 350,
            "xp": 175
        }
    },
    "mine_specific_ore": {
        "title": "Caçador de Tesouros",
        "description": "Minere {count} {ore_type}",
        "rewards": {
            "coins": 400,
            "xp": 200
        }
    },
    "play_roulette_small": {
        "title": "Apostador Iniciante",
        "description": "Faça {count} apostas na roleta",
        "rewards": {
            "coins": 200,
            "xp": 100
        }
    },
    "play_roulette_medium": {
        "title": "Apostador Experiente",
        "description": "Faça {count} apostas na roleta",
        "rewards": {
            "coins": 300,
            "xp": 150
        }
    },
    "play_roulette_large": {
        "title": "Apostador Mestre",
        "description": "Faça {count} apostas na roleta",
        "rewards": {
            "coins": 400,
            "xp": 200
        }
    },
    "win_roulette": {
        "title": "Sortudo",
        "description": "Ganhe {count} vezes na roleta",
        "rewards": {
            "coins": 500,
            "xp": 250
        }
    }
}

async def get_user_daily_quests(guild_id: str, user_id: str) -> dict:
    """
    Obtém ou cria as missões diárias do usuário.
    """
    try:
        # Busca as missões existentes
        quests_ref = db_ref.child("servidores").child(guild_id).child("daily_quests").child(user_id)
        quests_data = quests_ref.get()
        
        # Obtém o timestamp atual em UTC-3
        current_time = datetime.now(timezone(timedelta(hours=-3)))
        reset_time = current_time.replace(hour=21, minute=0, second=0, microsecond=0)
        
        # Verifica se precisa resetar as missões
        needs_reset = False
        if not quests_data or not quests_data.get("last_update"):
            needs_reset = True
        else:
            # Converte o timestamp do Firebase para datetime
            last_update = datetime.fromtimestamp(quests_data["last_update"] / 1000, timezone(timedelta(hours=-3)))
            # Se o último update foi antes do reset de hoje, precisa resetar
            if last_update < reset_time and current_time >= reset_time:
                needs_reset = True
        
        if needs_reset:
            # Gera 3 missões aleatórias
            available_quests = list(DAILY_QUESTS.keys())
            selected_quests = random.sample(available_quests, min(3, len(available_quests)))
            
            new_quests = {}
            for quest_type in selected_quests:
                quest_data = DAILY_QUESTS[quest_type]
                
                # Define a quantidade baseada no tipo de missão
                if "small" in quest_type:
                    count = random.randint(5, 10)
                elif "medium" in quest_type:
                    count = random.randint(15, 25)
                elif "large" in quest_type:
                    count = random.randint(30, 50)
                else:
                    count = random.randint(1, 5)
                
                # Se for missão de minério específico, escolhe um minério aleatório
                if quest_type == "mine_specific_ore":
                    ore_types = ["diamante", "esmeralda", "rubi", "safira", "ouro", "prata", "bronze", "ferro", "carvão"]
                    ore_type = random.choice(ore_types)
                    description = quest_data["description"].format(count=count, ore_type=ore_type)
                else:
                    description = quest_data["description"].format(count=count)
                
                new_quests[quest_type] = {
                    "title": quest_data["title"],
                    "description": description,
                    "required": count,
                    "current": 0,
                    "completed": False,
                    "rewards": quest_data["rewards"]
                }
            
            # Salva as novas missões
            quests_ref.set({
                "quests": new_quests,
                "last_update": {".sv": "timestamp"}
            })
            
            return new_quests
        
        return quests_data.get("quests", {})
    except Exception as e:
        print(f"Erro ao obter missões diárias: {e}")
        return {}

@bot.tree.command(name="daily_quests", description="Mostra suas missões diárias")
async def daily_quests(interaction: discord.Interaction):
    """
    Mostra as missões diárias do usuário.
    """
    await interaction.response.defer()
    try:
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        # Obtém as missões do usuário
        quests = await get_user_daily_quests(guild_id, user_id)
        
        if not quests:
            await interaction.followup.send("Não foi possível carregar suas missões diárias. Tente novamente mais tarde.", ephemeral=True)
            return
        
        # Separa as missões em ativas e completadas
        active_quests = {}
        completed_quests = {}
        
        for quest_type, quest_data in quests.items():
            if quest_data["completed"]:
                completed_quests[quest_type] = quest_data
            else:
                active_quests[quest_type] = quest_data
        
        # Cria o embed
        embed = discord.Embed(
            title="🎯 Missões Diárias",
            description="Complete as missões para ganhar recompensas!",
            color=discord.Color.blue()
        )
        
        # Adiciona as missões ativas primeiro
        if active_quests:
            embed.add_field(
                name="📝 Missões Ativas",
                value="",
                inline=False
            )
            
            for quest_type, quest_data in active_quests.items():
                progress = quest_data["current"] / quest_data["required"]
                progress_bar = "█" * int(progress * 10) + "░" * (10 - int(progress * 10))
                
                embed.add_field(
                    name=f"{quest_data['title']} ({quest_data['current']}/{quest_data['required']})",
                    value=f"{quest_data['description']}\n"
                          f"`{progress_bar}` {int(progress * 100)}%\n"
                          f"Recompensas: {quest_data['rewards']['coins']} <:owocoin:1364995129022349382> + {quest_data['rewards']['xp']} XP",
                    inline=False
                )
        
        # Adiciona as missões completadas por último
        if completed_quests:
            embed.add_field(
                name="✅ Missões Completadas",
                value="",
                inline=False
            )
            
            for quest_type, quest_data in completed_quests.items():
                embed.add_field(
                    name=f"{quest_data['title']} ✅",
                    value=f"{quest_data['description']}\n"
                          f"Recompensas: {quest_data['rewards']['coins']} <:owocoin:1364995129022349382> + {quest_data['rewards']['xp']} XP",
                    inline=False
                )
        
        # Adiciona footer com informações de reset
        embed.set_footer(text="As missões são resetadas todos os dias às 21:00")
        
        # Adiciona thumbnail do usuário
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        message = await interaction.followup.send(embed=embed)
        await asyncio.sleep(30)
        try:
            await message.delete()
        except:
            pass
        
    except Exception as e:
        print(f"Erro ao mostrar missões diárias: {e}")
        await interaction.followup.send("Ocorreu um erro ao mostrar suas missões diárias. Tente novamente mais tarde.", ephemeral=True)

async def update_quest_progress(guild_id: str, user_id: str, quest_type: str, amount: int = 1, specific_ore: str = None):
    """
    Atualiza o progresso de uma missão diária.
    """
    try:
        quests_ref = db_ref.child("servidores").child(guild_id).child("daily_quests").child(user_id)
        quests_data = quests_ref.get()
        
        if not quests_data or not quests_data.get("quests"):
            return
        
        quests = quests_data["quests"]
        
        # Atualiza todas as missões do tipo especificado
        for quest_key, quest in quests.items():
            if not quest["completed"]:
                # Verifica se é uma missão de minério específico
                if quest_key == "mine_specific_ore" and specific_ore:
                    if specific_ore in quest["description"]:
                        quest["current"] = min(quest["current"] + amount, quest["required"])
                # Verifica se é uma missão de mensagens
                elif "message_count" in quest_key and quest_type == "message_count":
                    quest["current"] = min(quest["current"] + amount, quest["required"])
                # Verifica se é uma missão de mineração geral
                elif "mine_ores" in quest_key and quest_type == "mine_ores":
                    quest["current"] = min(quest["current"] + amount, quest["required"])
                # Verifica se é uma missão de roleta
                elif "play_roulette" in quest_key and quest_type == "play_roulette":
                    quest["current"] = min(quest["current"] + amount, quest["required"])
                # Verifica se é uma missão de vitória na roleta
                elif quest_key == "win_roulette" and quest_type == "win_roulette":
                    quest["current"] = min(quest["current"] + amount, quest["required"])
                
                # Verifica se a missão foi completada
                if quest["current"] >= quest["required"]:
                    quest["completed"] = True
                    # Adiciona as recompensas
                    user_ref = None
                    user_data = None
                    
                    # Busca em membros
                    membros = db_ref.child("servidores").child(guild_id).child("usuarios_membros").get()
                    if membros:
                        for key, membro in membros.items():
                            if membro.get("discord_id") == user_id:
                                user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_membros").child(key)
                                user_data = membro
                                break
                    
                    # Se não encontrou em membros, busca em visitantes
                    if not user_ref:
                        visitantes = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").get()
                        if visitantes:
                            for key, visitante in visitantes.items():
                                if visitante.get("discord_id") == user_id:
                                    user_ref = db_ref.child("servidores").child(guild_id).child("usuarios_visitantes").child(key)
                                    user_data = visitante
                                    break
                    
                    if user_ref and user_data:
                        current_coins = user_data.get("owo_coins", 0)
                        current_xp = user_data.get("message_count", 0)
                        
                        user_ref.update({
                            "owo_coins": current_coins + quest["rewards"]["coins"],
                            "message_count": current_xp + quest["rewards"]["xp"]
                        })
                        
                        # Notifica o usuário sobre a conclusão da missão
                        try:
                            user = await bot.fetch_user(int(user_id))
                            embed = discord.Embed(
                                title="🎯 Missão Concluída!",
                                description=f"Você completou a missão **{quest['title']}**!",
                                color=discord.Color.green()
                            )
                            embed.add_field(
                                name="Recompensas",
                                value=f"**{quest['rewards']['coins']}** <:owocoin:1364995129022349382> + **{quest['rewards']['xp']}** XP",
                                inline=False
                            )
                            await user.send(embed=embed)
                        except:
                            pass
            
            # Atualiza o progresso no banco de dados
            quests_ref.update({"quests": quests})
            
    except Exception as e:
        print(f"Erro ao atualizar progresso da missão: {e}")

if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_TOKEN'))