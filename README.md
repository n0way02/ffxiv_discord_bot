# Bot de Registro Discord

Um bot Discord para gerenciamento de registro de usuários, com sistema de níveis, moeda virtual, mineração, cassino e sorteios.

## Funcionalidades

- Sistema de registro de usuários com verificação via Lodestone (FFXIV)
- Sistema de níveis e XP
- Sistema de moeda virtual (OwO Coins)
- Sistema de mineração
- Cassino com roleta automática
- Sistema de sorteios
- Missões diárias
- Perfil personalizável
- Leaderboard
- Sistema de transferência de moedas

## Requisitos

- Python 3.8 ou superior
- Discord.py 2.5.2
- Firebase Admin SDK
- Outras dependências listadas em `requirements.txt`

## Configuração

1. Clone o repositório
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure as variáveis de ambiente:
   - Crie um arquivo `.env` com as seguintes variáveis:
     ```
     DISCORD_TOKEN=seu_token_do_bot
     ```
4. Configure o Firebase:
   - Adicione o arquivo de credenciais do Firebase Admin SDK
   - Configure a URL do banco de dados no código

## Uso

1. Execute o bot:
   ```bash
   python bot-discord.py
   ```

2. Use os comandos no Discord:
   - `/setup` - Configura a mensagem de registro
   - `/registrar` - Registra um novo usuário
   - `/profile` - Mostra seu perfil
   - `/shop` - Abre a loja
   - `/mine` - Inicia a mineração
   - `/daily` - Recebe recompensas diárias
   - `/help` - Mostra todos os comandos disponíveis

## Contribuição

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou enviar pull requests.

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para mais detalhes. 