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


#Leaderboard of players
def get_top_players():
    #Returns the top 3 players based on their points
    sorted_players = sorted(players_points.items(), key=lambda x: x[1], reverse=True)
    top_players = sorted_players[:3]  # Get top 3 players
    return top_players

class GameView(View):
    def __init__(self, correct_answer, ctx, selected_songs):
        super().__init__(timeout=15)  # Set the timeout for 15 seconds
        self.correct_answer = correct_answer
        self.ctx = ctx
        self.selected_songs = selected_songs
        self.players_interacted = set()  # Track which players have interacted
        self.correct_players = []  # Initialize the correct_players list to track correct answers
        self.start_time = time.time()  # Record the start time of the round
        self.voice_channel_members = self.ctx.author.voice.channel.members  # Get members in the voice channel

        # List of emojis to randomly assign
        emojis = ['🔥', '🎵', '🎤', '💥', '🌟', '⚡', '💣']
        
        # Ensure we don't repeat emojis by shuffling the list
        random.shuffle(emojis)
        
        # Create dynamic buttons based on selected songs
        for idx, song in enumerate(self.selected_songs):
            songbase = os.path.basename(song)
            song_name = os.path.splitext(songbase)[0]
            
            # Assign a unique emoji for each button
            emoji = emojis[idx % len(emojis)]
            
            button = Button(label=f'{emoji}{song_name}', style=discord.ButtonStyle.primary, custom_id=f"button_{idx+1}")
            button.callback = self.create_button_callback(song)
            self.add_item(button)

    def create_button_callback(self, song):
        async def callback(interaction: discord.Interaction):
            await self.handle_option(interaction, song)
        return callback

    async def handle_option(self, interaction, option):
        if interaction.user.id in self.players_interacted:
            await interaction.response.send_message("You already answered!", ephemeral=True)
            return

        self.players_interacted.add(interaction.user.id)
        await interaction.response.defer()  # Defer the response without sending any message
        
        # Calculate the elapsed time since the round started
        elapsed_time = time.time() - self.start_time
        # Calculate the points based on the elapsed time
        points = max(100, 1000 - (elapsed_time * (1000 - 100) / 15))
        
        # Get the song name without the path (just the filename) and remove the .mp3 extension
        correct_song = os.path.basename(self.correct_answer)
        correct_song_name = os.path.splitext(correct_song)[0]
        
        if option == self.correct_answer:
            players_points[interaction.user.name] = players_points.get(interaction.user.name, 0) + int(points)
            self.correct_players.append(interaction.user.name)
            await interaction.followup.send(f"Correct! You get {int(points)} points!", ephemeral=True)
        else:
            await interaction.followup.send(f"Wrong! The correct answer was {correct_song_name}.", ephemeral=True)

        if len(self.players_interacted) == len(self.voice_channel_members) - 1:  # All members in VC have interacted
            await self.stop_round()

    async def stop_round(self):
        # Disable all buttons
        for item in self.children:
            item.disabled = True
            
        # Get the song name without the path (just the filename) and remove the .mp3 extension
        correct_song = os.path.basename(self.correct_answer)
        correct_song_name = os.path.splitext(correct_song)[0]
        
        # Announce the answer and players who got a point
        if self.correct_players:
            correct_players_str = ", ".join(self.correct_players)
            await self.ctx.send(f"_ _ \nThe answer was **{correct_song_name}**! {correct_players_str} got a point! \n \n https://tenor.com/view/he-theyd-stand-dbz-stand-gif-18435828")
        else:
            await self.ctx.send(f"_ _ \nThe answer was **{correct_song_name}**! No one got it right. \n \n https://tenor.com/view/sad-anime-gif-21889993")

        # Display top 3 leaderboard
        top_players = get_top_players()
        if top_players:
            leaderboard = "_ _\n".join([f"{idx+1}. {player[0]} - {player[1]} points" for idx, player in enumerate(top_players)])
            await self.ctx.send(f"**Leaderboard (Top 3):**\n{leaderboard}")
        else:
            await self.ctx.send("No points have been scored yet.")
        
        # Stop the round and move on to the next
        self.stop()
        
    # Override on_timeout to stop the round if the time runs out
    async def on_timeout(self):
        await self.stop_round()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def endless(ctx):
    """Starts the game if user is in a VC"""
    global players_points, game_running
    players_points = {}
    global round_skipped
    
    if game_running:  # Check if the game is already running
        await ctx.send("A game is already running. Please stop it first using /stop.")
        return
    
    game_running = True  # Set the flag to True to start
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        voice_client = await channel.connect()

        # Start an infinite loop for the game
        while game_running and voice_client.is_connected():
            # Check if the round is skipped
            if round_skipped:
                round_skipped = False  # Reset the skip flag
                await ctx.send("The round has been skipped! Moving to the next round...\n")
                continue  # Skip to the next round
            
            # Randomly choose 4 songs from the song list
            selected_songs = random.sample(songs, 4)

            # Select the correct answer (the song being played)
            correct_song = random.choice(selected_songs)
            correct_answer = correct_song

            # Create a view with buttons for the game
            view = GameView(correct_answer, ctx, selected_songs)

            # Send the question and options
            question_msg = await ctx.send(f"_ _\n\n```What OST is this? Choose your answer below.```")
            await question_msg.edit(content=f"_ _\n\n```What OST is this? Choose your answer below.```", view=view)

            # Play the correct song
            voice_client.play(FFmpegPCMAudio(correct_song))

            # Wait for the game to stop (after the song finishes or all players have interacted)
            await view.wait()

            # After the round ends, stop the current song
            voice_client.stop()
            
            # Add a delay before starting the next round
            await asyncio.sleep(1)

    else:
        await ctx.send("You need to be in a voice channel first!")


@bot.command()
async def game(ctx):
    global game_running
    if game_running:
        await ctx.send("A game is already running. Please stop it first using /stop.")
        return

    game_running = True  # Set the flag to True to indicate the game is running
    """Starts the game if user is in a VC and asks how many rounds"""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        voice_client = await channel.connect()

        # Ask the user how many rounds they want to play
        view = View(timeout=15)
        button_5 = Button(label="5 Rounds", style=discord.ButtonStyle.primary, custom_id="button_5")
        button_10 = Button(label="10 Rounds", style=discord.ButtonStyle.primary, custom_id="button_10")
        button_15 = Button(label="15 Rounds", style=discord.ButtonStyle.primary, custom_id="button_15")

        # Add buttons to the view
        view.add_item(button_5)
        view.add_item(button_10)
        view.add_item(button_15)

        # Define button callbacks
        async def on_button_click(interaction: discord.Interaction):
            rounds = 0
            if interaction.data["custom_id"] == "button_5":
                rounds = 5
            elif interaction.data["custom_id"] == "button_10":
                rounds = 10
            elif interaction.data["custom_id"] == "button_15":
                rounds = 15

            await interaction.response.send_message(f"Starting the game with {rounds} rounds!")
            await start_game(ctx, voice_client, rounds)

        button_5.callback = on_button_click
        button_10.callback = on_button_click
        button_15.callback = on_button_click

        # Ask the user to choose the number of rounds
        await ctx.send("How many rounds would you like to play?", view=view)

    else:
        await ctx.send("You need to be in a voice channel first!")
        
async def start_game(ctx, voice_client, rounds):
    """Starts the game for the specified number of rounds"""
    global game_running, players_points
    players_points = {}
    round_counter = 0
    while round_counter < rounds:
        # Randomly choose 4 songs from the song list
        selected_songs = random.sample(songs, 4)

        # Select the correct answer (the song being played)
        correct_song = random.choice(selected_songs)

        # Create a view with buttons for the game
        view = GameView(correct_song, ctx, selected_songs)

        # Send the question and options
        question_msg = await ctx.send(f"_ _\n\n```What OST is this? Choose your answer below.```")
        await question_msg.edit(content=f"_ _\n\n```What OST is this? Choose your answer below.```", view=view)

        # Play the correct song
        voice_client.play(FFmpegPCMAudio(correct_song))

        # Wait for the game to stop (after the song finishes or all players have interacted)
        await view.wait()

        # After the round ends, stop the current song
        voice_client.stop()

        # Increment the round counter
        round_counter += 1

        # Add a delay before starting the next round
        if round_counter < rounds:
            await asyncio.sleep(1)

    await ctx.send(f"_ _ \nGame Over! {rounds} rounds completed.\n")
    
    # Announce the winner
    if players_points:
        winner = max(players_points, key=players_points.get)
        await ctx.send(f"The winner is {winner} with {players_points[winner]} points!")
    else:
        await ctx.send("No one scored any points.")
        
    # Display top 3 leaderboard
    top_players = get_top_players()
    if top_players:
        leaderboard = "\n".join([f"{idx+1}. {player[0]} - {player[1]} points" for idx, player in enumerate(top_players)])
        await ctx.send(f"**Leaderboard (Top 3):**\n{leaderboard}")
    else:
        await ctx.send("No points have been scored yet.")

    # Reset the game_running flag after the game ends
    game_running = False
    
    
    await voice_client.disconnect()


@bot.command()
async def skip(ctx):
    """Skips the current round and moves to the next one"""
    global round_skipped  # Access the global variable to flag the round as skipped
    round_skipped = True  # Set the flag to indicate the round is skipped
    await ctx.send("The round is being skipped. Moving to the next round...")

@bot.command()
async def stop(ctx):
    """Ends the game and announces the winner"""
    global game_running
    game_running = False
    await ctx.send("Game is stopping...")

    # Stop and disconnect from the voice channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client:
        await voice_client.disconnect()

    # Announce the winner
    if players_points:
        winner = max(players_points, key=players_points.get)
        await ctx.send(f"The game is over! {winner} wins with {players_points[winner]} points! \n _ _")
    else:
        await ctx.send("No one scored any points.")
        
    # Display top 3 leaderboard
    top_players = get_top_players()
    if top_players:
        leaderboard = "_ _\n".join([f"{idx+1}. {player[0]} - {player[1]} points" for idx, player in enumerate(top_players)])
        await ctx.send(f"**Leaderboard (Top 3):**\n{leaderboard}")
    else:
        await ctx.send("No points have been scored yet.")

bot.run(BOT_TOKEN)  # Run the bot with your actual bot token
