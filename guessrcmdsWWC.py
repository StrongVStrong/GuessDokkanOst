import discord
from discord.ext import commands
import random
from discord.ext.commands import has_permissions
import os
from discord import FFmpegPCMAudio, app_commands
from dotenv import load_dotenv
from discord.ui import Button, View
import asyncio
import time, re

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

# Global Dictionaries
players_points = {}
radio_playing = {}
game_running = {}
players_interacted = {}
current_gameview = {}
round_skipped = {}
currently_playing = {}
looping_songs = {}


#Leaderboard of players
def get_top_players(guild_id):
    """Returns the top 3 players based on their points, including those with 0 points."""
    global players_interacted  # Ensure we have access to the global players_interacted set
    
    if guild_id not in players_points:
        players_points[guild_id] = {}
    if guild_id not in players_interacted:
        players_interacted[guild_id] = set()
    '''
    # Ensure all interacted players are in the leaderboard, even if they have 0 points
    all_players = set(players_interacted[guild_id])  # Ensure all interacted players are added
    for player in all_players:
        if player not in players_points[guild_id]:
            players_points[guild_id][player] = 0  # Set score to 0 for players who didn't score any points
    '''
    # Sort players based on points, in descending order
    sorted_players = sorted(players_points[guild_id].items(), key=lambda x: x[1], reverse=True)

    # Ensure there are always 3 entries in the leaderboard, even if no players have scored
    while len(sorted_players) < 3:
        sorted_players.append(("", 0))  # Add empty entries with 0 points if fewer than 3 players

    return sorted_players[:3]

class GameView(View):
    def __init__(self, correct_answer, interaction, selected_songs, voice_client, guild_id):
        super().__init__(timeout=10) 
        self.guild_id = guild_id 
        self.correct_answer = correct_answer
        self.interaction = interaction
        self.selected_songs = selected_songs
        self.voice_client = voice_client
        self.players_interacted = set()
        self.correct_players = []
        self.start_time = time.time()  # Record the start time of the round

        self.response_sent = False
        
        emojis = ['🔥', '🎵', '🎤', '💥', '🌟', '⚡', '💣']
        random.shuffle(emojis)  
        
        for idx, song in enumerate(self.selected_songs):
            songbase = os.path.basename(song)
            song_name = os.path.splitext(songbase)[0]
            emoji = emojis[idx % len(emojis)]
            button = Button(label=f'{emoji}{song_name}', style=discord.ButtonStyle.primary, custom_id=f"button_{idx+1}")
            button.callback = self.create_button_callback(song)
            self.add_item(button)
        
        global current_gameview
        current_gameview[self.guild_id] = self

    def create_button_callback(self, song):
        async def callback(interaction: discord.Interaction):
            await self.handle_option(interaction, song)
        return callback

    async def handle_option(self, interaction, option):
        global players_interacted
        if not game_running.get(self.guild_id, False):  # Check if the game is still running
            await self.send_response(interaction, "The game has stopped. Please wait for the next game.", ephemeral=True)
            return
        
        # Defer the response right after the first interaction
        if not interaction.response.is_done():
            await interaction.response.defer()
            
        # Check if the user is in the same voice channel as the bot
        if interaction.user.voice is None or interaction.user.voice.channel != self.voice_client.channel:
            await interaction.followup.send("You must be in the same voice channel as the bot to play!", ephemeral=True)
            return
        
        if interaction.user.id in players_interacted.get(self.guild_id, set()):
            await self.send_response(interaction, "You already answered!", ephemeral=True)
            return

        # Initialize the set for players if it's not already initialized for this guild
        if self.guild_id not in players_interacted:
            players_interacted[self.guild_id] = set()
        
        players_interacted[self.guild_id].add(interaction.user.id)
        
        # Add the player to players_points with 0 points if they haven't interacted before
        if interaction.user.name not in players_points[self.guild_id]:
            players_points[self.guild_id][interaction.user.name] = 0
        
        # Calculate points
        elapsed_time = time.time() - self.start_time
        points = max(100, 1000 - (elapsed_time * (1000 - 100) / 15))
        
        # Check if the answer is correct
        correct_song = os.path.basename(self.correct_answer)
        correct_song_name = os.path.splitext(correct_song)[0]
        total_points = players_points.get(self.guild_id, {}).get(interaction.user.name, 0)

        
        if option == self.correct_answer:
            players_points[self.guild_id][interaction.user.name] = total_points + int(points)
            self.correct_players.append(interaction.user.name)
            await interaction.followup.send(f"Correct! You get {int(points)} points! Your total points are now {total_points + int(points)}.", ephemeral=True)
        else:
            await interaction.followup.send(f"Wrong! The correct answer was {correct_song_name}. Your total points are still {total_points}.", ephemeral=True)

        # Check if the voice channel has no members (everyone left)
        if len([member for member in self.voice_client.channel.members if not member.bot]) == 0:
            await interaction.followup.send("Everyone left the voice channel. The game has ended.")
            game_running[self.guild_id] = False  # Set game_running to False to stop the game
            await current_gameview[self.guild_id].stop_round()
            return  # End the game if everyone leaves

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
        if not game_running.get(self.guild_id, False):  # Check if the game is still running before sending messages
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
        top_players = get_top_players(self.guild_id)
        if top_players:
            leaderboard = "\n".join([f"{idx+1}. {player[0] if player[0] else 'No player'} - {player[1]} points" for idx, player in enumerate(top_players)])
            await self.send_response(self.interaction, f"_ _\n\n**Leaderboard:**\n{leaderboard}\n\n")
        else:
            await self.send_response(self.interaction, "No one participated")

        # Reset the interacted players for this guild (this is the key change)
        if self.guild_id in players_interacted:
            players_interacted[self.guild_id].clear()
        
        self.stop()

    async def on_timeout(self):
        await self.stop_round()


@bot.event
async def on_ready():
    await bot.tree.sync()
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name="Guess the OST | /help"
    )
    await bot.change_presence(activity=activity)
    print(f'Logged in as {bot.user}')

@bot.tree.command(name="endless", description="Endless barrage of Dokkan OSTs, stop with /stop")
async def endless(interaction: discord.Interaction):
    """Starts the game if the user is in a VC"""
    global players_points, game_running, players_interacted, round_skipped
    
    guild_id = interaction.guild.id
    
    if game_running.get(guild_id, False):  # Check if the game is already running
        await interaction.response.send_message("A game is already running. Please stop it first using /stop.")
        return
    
    # Check if the bot is already in a voice channel
    voice_client = interaction.guild.voice_client
    if voice_client:
        await interaction.response.send_message("Bot is already connected to a voice channel.")
        return
    
    players_interacted[guild_id] = set()
    players_points[guild_id] = {}
    
    game_running[guild_id] = True  # Set the flag to True to start
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        voice_client = await channel.connect()
        
        # Send the initial message
        await interaction.response.send_message(f"Starting the game! Get ready!")

        # Start an infinite loop for the game
        round_counter = 0
        while game_running.get(guild_id, False) and voice_client.is_connected():
            # Check if the round is skipped
            if round_skipped.get(guild_id, False):
                round_skipped[guild_id] = False  # Reset the skip flag
                await interaction.channel.send("The round has been skipped! Moving to the next round...\n")
                continue  # Skip to the next round
            
            # Check if the voice channel has no members (everyone left)
            if len([member for member in voice_client.channel.members if not member.bot]) == 0:
                await interaction.followup.send("Everyone left the voice channel. The game has ended.")
                game_running[guild_id] = False  # Set game_running to False to stop the game
                if current_gameview.get(guild_id, None):
                    await current_gameview[guild_id].stop_round()
                voice_client.stop()
                await voice_client.disconnect()
                return  # End the game if everyone leaves
            
            # Randomly choose 4 songs from the song list
            selected_songs = random.sample(songs, 4)

            # Select the correct answer (the song being played)
            correct_song = random.choice(selected_songs)
            correct_answer = correct_song
            
            # Create a view with buttons for the game
            view = GameView(correct_answer, interaction, selected_songs, voice_client, guild_id)

            # Send the question and options (follow-up response)
            await interaction.channel.send(
                f"```Round {round_counter + 1}: What OST is this? Choose your answer below.```"
                "\n\n", 
                view=view
                )

            # Play the correct song
            voice_client.play(FFmpegPCMAudio(correct_song))

            # Wait for the game to stop (after the song finishes or all players have interacted)
            await view.wait()
            
            delay = 3  # Delay in seconds

            # Track time elapsed
            start_time = asyncio.get_event_loop().time()  # Track when the wait starts
            while True:
                # Check if the game has stopped
                if not game_running.get(guild_id, False):  # If game_running is False, stop the loop
                    print("Game has been stopped. Exiting round.")
                    break
                
                # Check if we've exceeded the desired delay (3 seconds)
                elapsed_time = asyncio.get_event_loop().time() - start_time
                if elapsed_time >= delay:  # If 3 seconds have passed, stop waiting
                    break
                
                # Sleep for a short period to prevent blocking the event loop and check again
                await asyncio.sleep(0.1)  # Sleep for 100ms and recheck the game state
            round_counter += 1
            voice_client.stop()
    else:
        await interaction.response.send_message("You need to be in a voice channel first!")
        game_running[guild_id] = False

@bot.tree.command(name="game", description="Start a game of Dokkan OSTs")
@app_commands.describe(rounds="Specify the number of rounds to play")
async def game(interaction: discord.Interaction, rounds: int = 30):  # Default to 30 rounds
    global game_running, players_interacted
    
    guild_id = interaction.guild.id
    
    if rounds < 1:
        await interaction.response.send_message(f"You cant play {rounds} rounds...")
        return
    
    # Check if the game is already running
    if game_running.get(guild_id, False):
        await interaction.response.send_message("A game is already running. Please stop it first using /stop.")
        return
    
    # Check if the bot is already in a voice channel
    voice_client = interaction.guild.voice_client
    if voice_client:
        await interaction.response.send_message("Bot is already connected to a voice channel.")
        return

    players_interacted[guild_id] = set()
    
    game_running[guild_id] = True  # Set the flag to True to indicate the game is running

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
        game_running[guild_id] = False
        
async def start_game(interaction, voice_client, rounds):
    """Starts the game for the specified number of rounds"""
    global game_running, players_points
    guild_id = interaction.guild.id
    players_points[guild_id] = {}
    round_counter = 0
    while round_counter < rounds and game_running.get(guild_id, False):
        # Check if the game is still running before sending the question message
        if not game_running.get(guild_id, False):
            break
        
        # Check if the voice channel has no members (everyone left)
        if len([member for member in voice_client.channel.members if not member.bot]) == 0:
            await interaction.followup.send("Everyone left the voice channel. The game has ended.")
            game_running[guild_id] = False  # Set game_running to False to stop the game
            if current_gameview.get(guild_id, None):
                await current_gameview[guild_id].stop_round()
            voice_client.stop()
            await voice_client.disconnect()
            return  # End the game if everyone leaves
        
        # Randomly choose 4 songs from the song list
        selected_songs = random.sample(songs, 4)

        # Select the correct answer (the song being played)
        correct_song = random.choice(selected_songs)

        # Create a view with buttons for the game
        view = GameView(correct_song, interaction, selected_songs, voice_client, guild_id)
        
        # Send the question and options (initial message)
        await interaction.channel.send(f"```Round {round_counter + 1}: What OST is this? Choose your answer below.```", view=view)

        # Play the correct song
        voice_client.play(FFmpegPCMAudio(correct_song))

        # Wait for the game to stop (after the song finishes or all players have interacted)
        await view.wait()

        # Increment the round counter
        round_counter += 1

        # Add a delay before starting the next round
        if round_counter < rounds:
            delay = 3  # Delay in seconds

            # Track time elapsed
            start_time = asyncio.get_event_loop().time()  # Track when the wait starts
            while True:
                # Check if the game has stopped
                if not game_running.get(guild_id, False):  # If game_running is False, stop the loop
                    print("Game has been stopped. Exiting round.")
                    break
                
                # Check if we've exceeded the desired delay (3 seconds)
                elapsed_time = asyncio.get_event_loop().time() - start_time
                if elapsed_time >= delay:  # If 3 seconds have passed, stop waiting
                    break
                
                # Sleep for a short period to prevent blocking the event loop and check again
                await asyncio.sleep(0.1)  # Sleep for 100ms and recheck the game state
            voice_client.stop()

    # Ensure no game-related messages are sent if the game was stopped
    if game_running.get(guild_id, False):
        game_running[guild_id] = False
            
        # Disconnect from the voice channel
        voice_client.stop()
        await voice_client.disconnect()
        
        # Send game over message
        await interaction.channel.send(f"Game Over! {rounds} rounds completed.\n")
        
        # Display the top player (only the highest points player)
        top_players = get_top_players(guild_id)

        if top_players:
            # Get the player with the highest points (first player in the sorted list)
            winner_name, winner_points = top_players[0]
            
            if winner_name and winner_points > 0:
                await interaction.followup.send(f"_ _\n**The winner is {winner_name} with {winner_points} points!**\n _ _")
            else:
                await interaction.followup.send("_ _\nNo one won. All players scored 0 points.\n _ _")
        else:
            await interaction.followup.send("_ _\nNo one scored any points.\n _ _")

            
        # Display top 3 leaderboard
        top_players = get_top_players(guild_id)

        # Ensure there are always 3 places in the leaderboard, even if no players are there
        if len(top_players) < 3:
            # Fill missing places with blank placeholders
            while len(top_players) < 3:
                top_players.append(("", 0))  # Append an empty entry with 0 points

        # Create the leaderboard string
        leaderboard = "\n".join([f"{idx+1}. {player[0] if player[0] else 'No player'} - {player[1]} points" for idx, player in enumerate(top_players)])

        await interaction.channel.send(f"**FINAL Leaderboard:**\n{leaderboard}\n\n")
        
    # Reset the game_running flag after the game ends
    game_running[guild_id] = False


@bot.tree.command(name="skipround", description="Skip the current round")
async def skipround(interaction: discord.Interaction):
    global game_running, currently_playing
    """Skips the current round and moves to the next one"""
    guild_id = interaction.guild.id
    if game_running.get(guild_id, False):
        await interaction.response.send_message("Skipping", ephemeral = True)
        await interaction.channel.send(f"_ _\nRound has been skipped\n_ _")
        await current_gameview[guild_id].stop_round()
    elif currently_playing.get(guild_id, False):
        await interaction.response.send_message("Not playing a game. Stop the bot first using /dc.")
    else:
        await interaction.response.send_message("No game is running in this server.")
    

@bot.tree.command(name="stop", description="Ends the game")
async def stop(interaction: discord.Interaction):
    global game_running, current_gameview
    
    guild_id = interaction.guild.id
    
    # Check if the game is running for this guild
    if not game_running.get(guild_id, False):
        await interaction.response.send_message("No game is running in this server.")
        return

    # Stop and disconnect from the voice channel
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if voice_client:
        voice_client.stop()
        await voice_client.disconnect()

    # If the game is still running, simulate the stop behavior
    if current_gameview.get(guild_id, None):
        await current_gameview[guild_id].stop_round()
    
    game_running[guild_id] = False
    
    # Print game over
    await interaction.channel.send(f"_ _\n\n\nTHE GAME HAS ENDED!!!\n\n\n_ _")
    
    # Display the top player (only the highest points player)
    top_players = get_top_players(guild_id)

    if top_players:
        # Get the player with the highest points (first player in the sorted list)
        winner_name, winner_points = top_players[0]
        
        if winner_name and winner_points > 0:
            await interaction.response.send_message(f"_ _\n**The winner is {winner_name} with {winner_points} points!**\n _ _")
        else:
            await interaction.response.send_message("_ _\nNo one won. All players scored 0 points.\n _ _")
    else:
        await interaction.response.send_message("_ _\nNo one scored any points.\n")

    # Ensure there are always 3 places in the leaderboard, even if no players are there
    if len(top_players) < 3:
        # Fill missing places with blank placeholders
        while len(top_players) < 3:
            top_players.append(("", 0))  # Append an empty entry with 0 points

    # Create the leaderboard string
    leaderboard = "\n".join([f"{idx+1}. {player[0] if player[0] else 'No player'} - {player[1]} points" for idx, player in enumerate(top_players)])

    # Use channel for additional responses after the first one
    await interaction.channel.send(f"**FINAL Leaderboard:**\n{leaderboard}\n\n")


# Play command with autocomplete for song names
@bot.tree.command(name="play", description="Play a song in a voice channel")
@app_commands.describe(song="Search for a song to play")
async def play(interaction: discord.Interaction, song: str):
    global game_running, currently_playing, looping_songs
    
    # Check if a game is already running
    if game_running.get(interaction.guild.id, False):
        await interaction.response.send_message("A game is already running. Stop the game first using /stop.")
        return
    
    # Check if the bot is already in a voice channel
    voice_client = interaction.guild.voice_client
    if voice_client:
        await interaction.response.send_message("Bot is already connected to a voice channel.")
        return
    
    # Find the song path from the list of songs
    song_path = None
    for song_file in songs:
        if os.path.splitext(os.path.basename(song_file))[0].lower() == song.lower():
            song_path = song_file
            break
    
    if song_path is None:
        await interaction.response.send_message("Song not found.")
        return

    # Get the voice channel the user is in
    voice_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not voice_channel:
        await interaction.response.send_message("You need to be in a voice channel to play a song.")
        return

    # Join the voice channel
    vc = await voice_channel.connect()
    
    # Track the currently playing song
    currently_playing[interaction.guild.id] = os.path.splitext(os.path.basename(song_path))[0]

    # Play the song using FFmpeg
    vc.play(discord.FFmpegPCMAudio(song_path), after=lambda e: print('done', e))
    
    # Send a response that the song is playing
    await interaction.response.send_message(f"Now playing: {os.path.splitext(os.path.basename(song_path))[0]}")

    # Wait until the song finishes playing
    while vc.is_playing():
        await asyncio.sleep(0.1)
        
    # If loop is enabled, start looping the song
    while looping_songs.get(interaction.guild.id, False):
        # Replay the song
        vc.play(discord.FFmpegPCMAudio(song_path), after=lambda e: print('done', e))
        await interaction.followup.send(f"Looping: {os.path.splitext(os.path.basename(song_path))[0]}")
        
        # Wait until the song finishes playing
        while vc.is_playing():
            await asyncio.sleep(0.1)

    # After the song finishes, disconnect from the voice channel
    await vc.disconnect()
    currently_playing[interaction.guild.id] = False

def clean_text(text):
    # Remove special characters (like &, [, ], etc.) and convert to lowercase
    return re.sub(r'[^a-zA-Z0-9\s]', '', text).lower()

# Autocomplete function for song search within the `/play` command
@play.autocomplete('song')
async def song_autocomplete(interaction: discord.Interaction, song: str):
    # Clean the user input
    cleaned_song_input = clean_text(song)
    
    matching_songs = []
    for song_name in songs:
        cleaned_song_name = clean_text(os.path.splitext(os.path.basename(song_name))[0])

        # Check if all words in the cleaned input are present in the cleaned song name
        if all(word in cleaned_song_name for word in cleaned_song_input.split()):
            matching_songs.append(app_commands.Choice(name=os.path.splitext(os.path.basename(song_name))[0], value=os.path.splitext(os.path.basename(song_name))[0]))
    return matching_songs[:25]

# Command to loop or unloop the currently playing song
@bot.tree.command(name="loop", description="Loop or unloop the currently playing song.")
async def loop(interaction: discord.Interaction):
    global currently_playing, looping_songs, radio_playing
    
    # Get the currently playing song for the guild
    song_name = currently_playing.get(interaction.guild.id)
    
    if radio_playing.get(interaction.guild.id, False):
        await interaction.response.send_message("Play this song using /play to loop.")
        return
    
    if not song_name:
        await interaction.response.send_message("Play a song using /play to loop.")
        return
    
    # Check if the song is already looping
    if looping_songs.get(interaction.guild.id, False):
        # Song is already looping, unloop it
        looping_songs[interaction.guild.id] = False
        await interaction.response.send_message(f"Stopped looping {song_name}.")
    else:
        # Song is not looping, set it to loop
        looping_songs[interaction.guild.id] = True
        await interaction.response.send_message(f"Started looping {song_name}.")

@bot.tree.command(name="dc", description="Disconnect the bot from playing OSTs")
async def dc(interaction: discord.Interaction):
    global game_running, looping_songs
    voice_client = interaction.guild.voice_client
    
    if voice_client and not game_running.get(interaction.guild.id, False):
        if looping_songs.get(interaction.guild.id, False):
            # Song is already looping, unloop it
            looping_songs[interaction.guild.id] = False
            await interaction.response.send_message("Bot has disconnected.")
        else:
            await interaction.response.send_message("Bot has disconnected.")
            
        if radio_playing.get(interaction.guild.id, False):
            radio_playing[interaction.guild.id] = False
            
        await voice_client.disconnect(force = True)
        currently_playing[interaction.guild.id] = False
    elif game_running.get(interaction.guild.id, False):
        await interaction.response.send_message("The game is running. Stop the game first using /stop.")
    else:
        await interaction.response.send_message("Bot is not connected to any voice channel.")

# Radio command to play random songs infinitely
@bot.tree.command(name="radio", description="Play random songs in a loop")
async def radio(interaction: discord.Interaction):
    global game_running, radio_playing

    # Check if a game is already running
    if game_running.get(interaction.guild.id, False):
        await interaction.response.send_message("A game is already running. Stop the game first using /stop.")
        return

    # Check if the bot is already in a voice channel
    voice_client = interaction.guild.voice_client
    if voice_client:
        await interaction.response.send_message("Bot is already connected to a voice channel.")
        return

    # Get the voice channel the user is in
    voice_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not voice_channel:
        await interaction.response.send_message("You need to be in a voice channel to start the radio.")
        return

    # Join the voice channel
    vc = await voice_channel.connect()
    
    # Mark radio as playing
    radio_playing[interaction.guild.id] = True
    
    # Initial response to start the radio
    await interaction.response.send_message("Starting the radio...")

    async def play_next_song():
        while radio_playing.get(interaction.guild.id, False):  # Continue playing until radio is stopped
            # Select a random song from the list
            song_file = random.choice(songs)
            song_name = os.path.splitext(os.path.basename(song_file))[0]
            print(f"Now playing: {song_name}")
            
            # Play the song using FFmpeg
            vc.play(discord.FFmpegPCMAudio(song_file))

            # Send a follow-up message to notify about the song being played
            await interaction.followup.send(f"Now playing: {song_name}")

            # Wait until the song finishes playing
            while vc.is_playing():
                await asyncio.sleep(0.1)  # Check every second if the song is still playing

            # Check if a game has started or if the radio should stop
            if game_running.get(interaction.guild.id, False):
                break

        # Disconnect after the radio is stopped or the game starts
        await vc.disconnect()

    # Start the song loop
    await play_next_song()

# Skip command to stop the current song and play the next one
@bot.tree.command(name="skip", description="Skip the current song in the radio and play the next one.")
async def skip(interaction: discord.Interaction):
    global radio_playing, currently_playing

    # Check if the radio is playing
    if radio_playing.get(interaction.guild.id, False):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            # Stop the current song immediately
            voice_client.stop()
            await interaction.response.send_message("Song skipped! Playing the next random song.")
        else:
            await interaction.response.send_message("Not playing a song right now.")
    elif currently_playing.get(interaction.guild.id, False):
        await interaction.response.send_message("The bot is currently playing a regular song. Stop the song first using /dc.")
    else:
        await interaction.response.send_message("The radio is not currently playing, skip game rounds with /skipround.")

@bot.tree.command(name="help", description="List available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Available Commands", description="Here are the commands you can use:", color=0x00ff00)
    embed.add_field(name="/game", value="Start a game of Guess the Dokkan OST", inline=False)
    embed.add_field(name="/endless", value="Endless barrage of Dokkan OSTs, stop with /stop", inline=False)
    embed.add_field(name="/play", value="Play a song of choice in a voice channel", inline=False)
    embed.add_field(name="/loop", value="Loop the current song from /play", inline=False)
    embed.add_field(name="/radio", value="Play random songs in a loop", inline=False)
    embed.add_field(name="/skipround", value="Skip the current game round", inline=False)
    embed.add_field(name="/skip", value="Skip the radio OST", inline=False)
    embed.add_field(name="/stop", value="Stop the current game", inline=False)
    embed.add_field(name="/dc", value="Disconnect the bot from playing OSTs normally", inline=False)
    
    await interaction.response.send_message(embed=embed)
    
bot.run(BOT_TOKEN)
