import discord
from discord.ext import commands
import random
import os
from discord import FFmpegPCMAudio
from dotenv import load_dotenv
from discord.ui import Button, View
import asyncio
import time

# Load the environment variables from the .env file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

# Directory path where the songs are located
directory = r'C:\Users\Megas\Documents\GitHub\GuessDokkanOst\songs'
# Get a list of all .mp3 files in the directory
songs = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.mp3')]

# A dictionary to hold players' points
players_points = {}
round_skipped = False
game_running = False # Flag to check if the game is currently running
players_interacted = set()
current_gameview = None


#Leaderboard of players
def get_top_players():
    """Returns the top 3 players based on their points, including those with 0 points."""
    global players_interacted  # Ensure we have access to the global players_interacted set

    # Ensure all interacted players are in the leaderboard, even if they have 0 points
    all_players = set(players_interacted)  # Ensure all interacted players are added
    for player in all_players:
        if player not in players_points:
            players_points[player] = 0  # Set score to 0 for players who didn't score any points

    # Sort players based on points, in descending order
    sorted_players = sorted(players_points.items(), key=lambda x: x[1], reverse=True)

    # Ensure there are always 3 entries in the leaderboard, even if no players have scored
    while len(sorted_players) < 3:
        sorted_players.append(("", 0))  # Add empty entries with 0 points if fewer than 3 players

    return sorted_players[:3]

class GameView(View):
    def __init__(self, correct_answer, interaction, selected_songs, voice_client):
        super().__init__(timeout=15)  # Set the timeout for 15 seconds
        self.correct_answer = correct_answer
        self.interaction = interaction
        self.selected_songs = selected_songs
        self.voice_client = voice_client
        self.players_interacted = set()  # Track which players have interacted
        self.correct_players = []  # Initialize the correct_players list to track correct answers
        self.start_time = time.time()  # Record the start time of the round
        self.voice_channel_members = self.interaction.user.voice.channel.members  # Get members in the voice channel

        self.response_sent = False  # Flag to track if the initial response has been sent
        
        # List of emojis to randomly assign
        emojis = ['🔥', '🎵', '🎤', '💥', '🌟', '⚡', '💣']
        random.shuffle(emojis)  # Shuffle the emojis to prevent repetition
        
        # Create dynamic buttons based on selected songs
        for idx, song in enumerate(self.selected_songs):
            songbase = os.path.basename(song)
            song_name = os.path.splitext(songbase)[0]
            emoji = emojis[idx % len(emojis)]
            button = Button(label=f'{emoji}{song_name}', style=discord.ButtonStyle.primary, custom_id=f"button_{idx+1}")
            button.callback = self.create_button_callback(song)
            self.add_item(button)
        
        # Track this view as the most recent one
        global current_game_view
        current_game_view = self

    def create_button_callback(self, song):
        async def callback(interaction: discord.Interaction):
            await self.handle_option(interaction, song)
        return callback

    async def handle_option(self, interaction, option):
        global players_interacted
        if not game_running:  # Check if the game is still running
            await self.send_response(interaction, "The game has stopped. Please wait for the next game.", ephemeral=True)
            return
        
        # Defer the response right after the first interaction
        if not interaction.response.is_done():
            await interaction.response.defer()
            
        # Check if the user is in the same voice channel as the bot
        if interaction.user.voice is None or interaction.user.voice.channel != self.voice_client.channel:
            await interaction.followup.send("You must be in the same voice channel as the bot to play!", ephemeral=True)
            return
        
        if interaction.user.id in self.players_interacted:
            await self.send_response(interaction, "You already answered!", ephemeral=True)
            return

        self.players_interacted.add(interaction.user.id)
        players_interacted.add(interaction.user.name)
        
        # Calculate points
        elapsed_time = time.time() - self.start_time
        points = max(100, 1000 - (elapsed_time * (1000 - 100) / 15))
        
        # Check if the answer is correct
        correct_song = os.path.basename(self.correct_answer)
        correct_song_name = os.path.splitext(correct_song)[0]
        total_points = players_points.get(interaction.user.name, 0)
        
        if option == self.correct_answer:
            players_points[interaction.user.name] = total_points + int(points)
            self.correct_players.append(interaction.user.name)
            await interaction.followup.send(f"Correct! You get {int(points)} points! Your total points are now {total_points + int(points)}.", ephemeral=True)
        else:
            await interaction.followup.send(f"Wrong! The correct answer was {correct_song_name}. Your total points are still {total_points}.", ephemeral=True)

        if len(self.players_interacted) == len(self.voice_channel_members) - 1:
            await self.stop_round()

    async def send_response(self, interaction, message, ephemeral=False):
        # If the initial response hasn't been sent yet, use response.send_message()
        if not self.response_sent:
            if ephemeral:
                await self.interaction.followup.send(message, ephemeral=True)
            else:
                await self.interaction.channel.send(message)
            self.response_sent = True
        else:
            # After the first response, use channel.send()
            await self.interaction.channel.send(message)

    async def stop_round(self):
        if not game_running:  # Check if the game is still running before sending messages
            return

        # Disable all buttons
        for item in self.children:
            item.disabled = True
            
        correct_song = os.path.basename(self.correct_answer)
        correct_song_name = os.path.splitext(correct_song)[0]
        
        # Announce the answer and players who got a point
        if self.correct_players:
            correct_players_str = ", ".join(self.correct_players)
            await self.send_response(self.interaction, f"_ _ \nThe answer was **{correct_song_name}**! {correct_players_str} got it right! \n \n https://tenor.com/view/he-theyd-stand-dbz-stand-gif-18435828")
        else:
            await self.send_response(self.interaction, f"_ _ \nThe answer was **{correct_song_name}**! No one got it right. \n \n https://tenor.com/view/sad-anime-gif-21889993")

        # Display top 3 leaderboard
        top_players = get_top_players()
        if top_players:
            leaderboard = "\n".join([f"{idx+1}. {player[0] if player[0] else 'No player'} - {player[1]} points" 
                                for idx, player in enumerate(top_players)])
            await self.send_response(self.interaction, f"_ _\n\n**Leaderboard:**\n{leaderboard}\n\n")
        else:
            await self.send_response(self.interaction, "No one participated")

        self.stop()

    async def on_timeout(self):
        await self.stop_round()


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user}')

@bot.tree.command(name="endless", description="Endless barrage of Dokkan OSTs, stop with /stop")
async def endless(interaction: discord.Interaction):
    """Starts the game if the user is in a VC"""
    global players_points, game_running, players_interacted, round_skipped
    
    if game_running:  # Check if the game is already running
        await interaction.response.send_message("A game is already running. Please stop it first using /stop.")
        return
    
    players_interacted = set()
    players_points = {}
    
    game_running = True  # Set the flag to True to start
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        voice_client = await channel.connect()
        
        # Send the initial message
        await interaction.response.send_message(f"Starting the game! Get ready!")

        # Start an infinite loop for the game
        round_counter = 0
        while game_running and voice_client.is_connected():
            # Check if the round is skipped
            if round_skipped:
                round_skipped = False  # Reset the skip flag
                await interaction.channel.send("The round has been skipped! Moving to the next round...\n")
                continue  # Skip to the next round
            
            # Randomly choose 4 songs from the song list
            selected_songs = random.sample(songs, 4)

            # Select the correct answer (the song being played)
            correct_song = random.choice(selected_songs)
            correct_answer = correct_song

            # Create a view with buttons for the game
            view = GameView(correct_answer, interaction, selected_songs, voice_client)

            # Send the question and options (follow-up response)
            await interaction.channel.send(
                f"_ _\n\n```Round {round_counter + 1}: What OST is this? Choose your answer below.```"
                "\n\n", 
                view=view
                )

            # Play the correct song
            voice_client.play(FFmpegPCMAudio(correct_song))

            # Wait for the game to stop (after the song finishes or all players have interacted)
            await view.wait()
            
            # Add a delay before starting the next round
            await asyncio.sleep(1)
            round_counter += 1
            voice_client.stop()
    else:
        await interaction.response.send_message("You need to be in a voice channel first!")
        game_running = False

@bot.tree.command(name="game", description="Start a game of Dokkan OSTs")
async def game(interaction: discord.Interaction, rounds: int = 30):  # Default to 30 rounds
    global game_running, players_interacted
    
    # Check if the game is already running
    if game_running:
        await interaction.response.send_message("A game is already running. Please stop it first using /stop.")
        return

    players_interacted = set()
    
    game_running = True  # Set the flag to True to indicate the game is running

    # Check if the user is in a voice channel
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        voice_client = await channel.connect()

        # Confirm the number of rounds
        await interaction.response.send_message(f"Starting the game with {rounds} rounds!")

        # Start the game with the specified number of rounds
        await start_game(interaction, voice_client, rounds)
    else:
        await interaction.response.send_message("You need to be in a voice channel first!")
        game_running = False
        
async def start_game(interaction, voice_client, rounds):
    """Starts the game for the specified number of rounds"""
    global game_running, players_points
    players_points = {}
    round_counter = 0
    while round_counter < rounds and game_running:
        # Randomly choose 4 songs from the song list
        selected_songs = random.sample(songs, 4)

        # Select the correct answer (the song being played)
        correct_song = random.choice(selected_songs)

        # Create a view with buttons for the game
        view = GameView(correct_song, interaction, selected_songs, voice_client)

        # Check if the game is still running before sending the question message
        if not game_running:
            break
        
        # Send the question and options (initial message)
        await interaction.channel.send(f"_ _\n\n```Round {round_counter + 1}: What OST is this? Choose your answer below.```", view=view)

        # Play the correct song
        voice_client.play(FFmpegPCMAudio(correct_song))

        # Wait for the game to stop (after the song finishes or all players have interacted)
        await view.wait()

        # Increment the round counter
        round_counter += 1

        # Add a delay before starting the next round
        if round_counter < rounds:
            await asyncio.sleep(1)
            voice_client.stop()

    # Ensure no game-related messages are sent if the game was stopped
    if game_running:
        game_running = False
            
        # Disconnect from the voice channel
        voice_client.stop()
        await voice_client.disconnect()
        
        # Send game over message
        await interaction.channel.send(f"_ _ \nGame Over! {rounds} rounds completed.\n")
        
        # Announce the winner
        if players_points:
            winner = max(players_points, key=players_points.get)
            await interaction.channel.send(f"_ _\n\nThe winner is {winner} with {players_points[winner]} points!\n\n")
        else:
            await interaction.channel.send("_ _\nNo one scored any points.\n")
            
        # Display top 3 leaderboard
        top_players = get_top_players()

        # Ensure there are always 3 places in the leaderboard, even if no players are there
        if len(top_players) < 3:
            # Fill missing places with blank placeholders
            while len(top_players) < 3:
                top_players.append(("", 0))  # Append an empty entry with 0 points

        # Create the leaderboard string
        leaderboard = "\n".join([f"{idx+1}. {player[0] if player[0] else 'No player'} - {player[1]} points" for idx, player in enumerate(top_players)])

        await interaction.channel.send(f"_ _\n\n**FINAL Leaderboard:**\n{leaderboard}\n\n")
        
    # Reset the game_running flag after the game ends
    game_running = False



@bot.command()
async def skip(ctx):
    """Skips the current round and moves to the next one"""
    global round_skipped  # Access the global variable to flag the round as skipped
    round_skipped = True  # Set the flag to indicate the round is skipped
    await ctx.send("The round is being skipped. Moving to the next round...")

@bot.tree.command(name="stop", description="Ends the game")
async def stop(interaction: discord.Interaction):
    """Ends the game and announces the winner"""
    global game_running, current_game_view
    

    # Stop and disconnect from the voice channel
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if voice_client:
        await voice_client.disconnect()

    # If the game is still running, simulate the timeout behavior
    if current_game_view:
        await current_game_view.on_timeout()
    
    game_running = False
    
    # Print game over
    await interaction.channel.send(f"_ _\n\n\nTHE GAME HAS ENDED!!!\n\n\n")
    
    # Announce the winner
    if players_points:
        winner = max(players_points, key=players_points.get)
        if players_points[winner] == 0:  # Check if the highest points are 0
            await interaction.response.send_message("_ _\n\nNo one won. All players scored 0 points. \n\n")
        else:
            await interaction.response.send_message(f"_ _\n\nThe game is over! {winner} wins with {players_points[winner]} points! \n\n")
    else:
        await interaction.response.send_message("_ _\nNo one scored any points.\n")
        
    # Display top 3 leaderboard
    top_players = get_top_players()

    # Ensure there are always 3 places in the leaderboard, even if no players are there
    if len(top_players) < 3:
        # Fill missing places with blank placeholders
        while len(top_players) < 3:
            top_players.append(("", 0))  # Append an empty entry with 0 points

    # Create the leaderboard string
    leaderboard = "\n".join([f"{idx+1}. {player[0] if player[0] else 'No player'} - {player[1]} points" for idx, player in enumerate(top_players)])

    # Use channel for additional responses after the first one
    await interaction.channel.send(f"_ _\n\n**FINAL Leaderboard:**\n{leaderboard}\n\n")


bot.run(BOT_TOKEN)  # Run the bot with your actual bot token
