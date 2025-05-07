# Discord Registration Bot

A Discord bot for user registration management, featuring a leveling system, virtual currency, mining, casino, and giveaways.

## Features

- User registration system with Lodestone verification (FFXIV)
- Leveling and XP system
- Virtual currency system (OwO Coins)
- Mining system
- Casino with automatic roulette
- Giveaway system
- Daily missions
- Customizable profile
- Leaderboard
- Currency transfer system

## Requirements

- Python 3.8 or higher
- Discord.py 2.5.2
- Firebase Admin SDK
- Other dependencies listed in `requirements.txt`

## Setup

1. Clone the repository
2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure the environment variables:
   - Create a .env file with the following variables:
     ```
     DISCORD_TOKEN=your_bot_token
     ```
4. Configure Firebase:
   - Add the Firebase Admin SDK credentials file
   - Set up the database URL in the code

## Usage

1. Run the bot:
   ```bash
   python bot-discord.py
   ```

2. Use the commands on Discord:
   - `/setup` - Sets up the registration message
   - `/registrar` - Registers a new user
   - `/profile` - Displays your profile
   - `/shop` - Starts mining
   - `/mine` - Inicia a mineração
   - `/daily` - Collects daily rewards
   - `/help` - Shows all available commands

## Contribution

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 