import discord
from discord.ext import commands
import random
import os
from discord import FFmpegPCMAudio
from dotenv import load_dotenv
from discord.ui import Button, View

# Load the environment variables from the .env file
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', intents=intents)

# List of songs on your computer (replace with paths to Dokkan OSTs)
songs = [
    "TeqUIIntro.mp3",
    "AglJirenFinish2.mp3",
    "INTGammasStandby.mp3",
    "INTSSJTrioActive.mp3",
    "INTSSJTrioIntro.mp3",
    "TeqBlueGokuVegetaActive.mp3",
    "STRSSJ3.mp3",
    "TeqUIActive.mp3"
]

# A dictionary to hold players' points
players_points = {}
round_skipped = False

class GameView(View):
    def __init__(self, correct_answer, ctx, selected_songs):
        super().__init__(timeout=15)  # Set the timeout for 15 seconds
        self.correct_answer = correct_answer
        self.ctx = ctx
        self.selected_songs = selected_songs
        self.players_interacted = set()  # Track which players have interacted
        self.correct_players = []  # Initialize the correct_players list to track correct answers
        self.voice_channel_members = self.ctx.author.voice.channel.members  # Get members in the voice channel

        # Create dynamic buttons based on selected songs
        for idx, song in enumerate(self.selected_songs):
            button = Button(label=f'🔥 {song}', style=discord.ButtonStyle.primary, custom_id=f"button_{idx+1}")
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

        if option == self.correct_answer:
            players_points[interaction.user.name] = players_points.get(interaction.user.name, 0) + 1
            self.correct_players.append(interaction.user.name)
            await interaction.followup.send(f"Correct! {interaction.user.name} gets a point!", ephemeral=True)
        else:
            await interaction.followup.send(f"Wrong! The correct answer was {self.correct_answer}.", ephemeral=True)

        if len(self.players_interacted) == len(self.voice_channel_members) - 1:  # All members in VC have interacted
            await self.stop_round()

    async def stop_round(self):
        # Disable all buttons
        for item in self.children:
            item.disabled = True

         # Announce the answer and players who got a point
        if self.correct_players:
            correct_players_str = ", ".join(self.correct_players)
            await self.ctx.send(f"The answer was **{self.correct_answer}**! {correct_players_str} got a point!")
        else:
            await self.ctx.send(f"The answer was **{self.correct_answer}**! No one got it right.")
        
        # Send the message after button disable
        await self.ctx.send("The round is over!")

        # Stop the round and move on to the next
        self.stop()


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def game(ctx):
    """Starts the game if user is in a VC"""
    global round_skipped
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        voice_client = await channel.connect()

        # Start an infinite loop for the game
        while True:
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
            question_msg = await ctx.send(f"\n**What OST is this? Choose your answer below.**\n\n")
            await question_msg.edit(content=f"\n**What OST is this?**\n", view=view)

            # Play the correct song
            voice_client.play(FFmpegPCMAudio(correct_song))

            # Wait for the game to stop (after the song finishes or all players have interacted)
            await view.wait()

            # After the round ends, stop the current song
            voice_client.stop()

    else:
        await ctx.send("You need to be in a voice channel first!")

@bot.command()
async def skip(ctx):
    """Skips the current round and moves to the next one"""
    global round_skipped  # Access the global variable to flag the round as skipped
    round_skipped = True  # Set the flag to indicate the round is skipped
    await ctx.send("The round is being skipped. Moving to the next round...")

@bot.command()
async def stop(ctx):
    """Ends the game and announces the winner"""
    await ctx.send("Game is stopping...")

    # Stop and disconnect from the voice channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client:
        await voice_client.disconnect()

    # Announce the winner
    if players_points:
        winner = max(players_points, key=players_points.get)
        await ctx.send(f"The game is over! {winner} wins with {players_points[winner]} points!")
    else:
        await ctx.send("No one scored any points.")

bot.run(BOT_TOKEN)  # Run the bot with your actual bot token
