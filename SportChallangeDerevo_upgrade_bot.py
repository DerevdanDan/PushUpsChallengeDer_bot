import asyncio
from email.mime import application
import logging
from datetime import datetime, timedelta, time
from typing import Dict, Any, List, Optional
import json
import os
import pytz
from enum import Enum
import logging
from datetime import datetime


from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, JobQueue

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = ('8190480914:AAGzLaf9Om4aTPc6yXSyXk8-8ar09G_styk')
# Bot token - replace with your actual bot token
import os
BOT_TOKEN = os.getenv('BOT_TOKEN', '8190480914:AAGzLaf9Om4aTPc6yXSyXk8-8ar09G_styk')
# Data storage file
DATA_FILE = "fitness_challenge_data.json"

class ExerciseType(Enum):
    PUSHUPS = "push-ups"
    SQUATS = "squats"
    PULLUPS = "pull-ups"
    SITUPS = "sit-ups"
    BURPEES = "burpees"
    PLANKS = "planks (seconds)"

class ChallengeStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"

# Exercise tutorial videos and tips
EXERCISE_INFO = {
    ExerciseType.PUSHUPS: {
        "video": "https://www.youtube.com/watch?v=IODxDxX7oi4",
        "tips": "Keep your body straight, hands shoulder-width apart, lower chest to floor"
    },
    ExerciseType.SQUATS: {
        "video": "https://www.youtube.com/watch?v=aclHkVaku9U",
        "tips": "Feet shoulder-width apart, lower until thighs parallel to floor, keep chest up"
    },
    ExerciseType.PULLUPS: {
        "video": "https://www.youtube.com/watch?v=eGo4IYlbE5g",
        "tips": "Full grip on bar, pull until chin over bar, control the descent"
    },
    ExerciseType.SITUPS: {
        "video": "https://www.youtube.com/watch?v=1fbU_MkV7NE",
        "tips": "Lie flat, knees bent, hands behind head, lift shoulders off ground"
    },
    ExerciseType.BURPEES: {
        "video": "https://www.youtube.com/watch?v=TU8QYVW0gDU",
        "tips": "Squat, jump back to plank, push-up, jump forward, jump up"
    },
    ExerciseType.PLANKS: {
        "video": "https://www.youtube.com/watch?v=ASdvN_XEl_c",
        "tips": "Forearms on ground, body straight, hold position, breathe normally"
    }
}

class FitnessChallengeBot:
    def __init__(self):
        self.user_data = self.load_data()
    
    def load_data(self) -> Dict[str, Dict[str, Any]]:
        """Load user data from JSON file"""
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading data: {e}")
        return {}
    
    def save_data(self):
        """Save user data to JSON file"""
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump(self.user_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def get_user_data(self, user_id: str) -> Dict[str, Any]:
        """Get user data, create if doesn't exist"""
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                'challenges': {},
                'timezone': 'UTC',
                'reminder_times': {
                    'morning': '09:00',
                    'evening': '20:00'
                },
                'reminders_enabled': True
            }
            self.save_data()
        return self.user_data[user_id]
    
    def create_challenge(self, user_id: str, exercise: ExerciseType, total_reps: int, days: int) -> str:
        """Create a new challenge"""
        user_data = self.get_user_data(user_id)
        challenge_id = f"{exercise.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        challenge = {
            'id': challenge_id,
            'exercise': exercise.value,
            'total_reps': total_reps,
            'target_days': days,
            'current_reps': 0,
            'start_date': datetime.now().isoformat(),
            'target_date': (datetime.now() + timedelta(days=days)).isoformat(),
            'status': ChallengeStatus.ACTIVE.value,
            'daily_records': {},
            'daily_target': total_reps / days
        }
        
        user_data['challenges'][challenge_id] = challenge
        self.save_data()
        return challenge_id
    
    def add_reps(self, user_id: str, challenge_id: str, reps: int):
        """Add reps to a challenge"""
        user_data = self.get_user_data(user_id)
        if challenge_id not in user_data['challenges']:
            return False
        
        challenge = user_data['challenges'][challenge_id]
        challenge['current_reps'] += reps
        
        # Track daily records
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in challenge['daily_records']:
            challenge['daily_records'][today] = 0
        challenge['daily_records'][today] += reps
        
        # Check if challenge is completed
        if challenge['current_reps'] >= challenge['total_reps']:
            challenge['status'] = ChallengeStatus.COMPLETED.value
            challenge['completion_date'] = datetime.now().isoformat()
        
        self.save_data()
        return True
    
    def get_challenge_progress(self, user_id: str, challenge_id: str) -> Optional[Dict[str, Any]]:
        """Get challenge progress"""
        user_data = self.get_user_data(user_id)
        if challenge_id not in user_data['challenges']:
            return None
        
        challenge = user_data['challenges'][challenge_id]
        start_date = datetime.fromisoformat(challenge['start_date'])
        target_date = datetime.fromisoformat(challenge['target_date'])
        days_elapsed = (datetime.now() - start_date).days + 1
        days_remaining = (target_date - datetime.now()).days
        
        # Calculate actual daily average
        actual_daily_avg = challenge['current_reps'] / days_elapsed if days_elapsed > 0 else 0
        
        # Calculate needed daily average to finish on time
        needed_daily_avg = (challenge['total_reps'] - challenge['current_reps']) / max(days_remaining, 1)
        
        # Calculate projected completion date
        if actual_daily_avg > 0:
            remaining_reps = challenge['total_reps'] - challenge['current_reps']
            days_to_completion = remaining_reps / actual_daily_avg
            projected_date = datetime.now() + timedelta(days=days_to_completion)
        else:
            projected_date = None
        
        return {
            'challenge': challenge,
            'percentage': (challenge['current_reps'] / challenge['total_reps']) * 100,
            'days_elapsed': days_elapsed,
            'days_remaining': days_remaining,
            'actual_daily_avg': actual_daily_avg,
            'needed_daily_avg': needed_daily_avg,
            'projected_date': projected_date,
            'on_track': actual_daily_avg >= challenge['daily_target']
        }
    
    def get_active_challenges(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all active challenges for a user"""
        user_data = self.get_user_data(user_id)
        active_challenges = []
        
        for challenge_id, challenge in user_data['challenges'].items():
            if challenge['status'] == ChallengeStatus.ACTIVE.value:
                progress = self.get_challenge_progress(user_id, challenge_id)
                if progress:
                    active_challenges.append(progress)
        
        return active_challenges

# Initialize bot instance
bot_instance = FitnessChallengeBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = str(user.id)
    username = user.first_name or user.username or "Unknown"

    # bot_instance is already initialized globally, no need to re-initialize here
    # bot_instance = FitnessChallengeBot() # Remove or comment out this line if bot_instance is already global
    
    # Corrected line: Use get_user_data to ensure user data is loaded/initialized
    bot_instance.get_user_data(user_id) 

    logger.info(f"🆕 NEW USER: {username} (ID: {user_id}) started the bot")

    # Create main menu keyboard
    keyboard = [
        [KeyboardButton("🆕 New Challenge"), KeyboardButton("📊 My Challenges")],
        [KeyboardButton("➕ Add Reps"), KeyboardButton("📈 Progress")],
        [KeyboardButton("⚙️ Settings"), KeyboardButton("📚 Exercise Guide")],
        [KeyboardButton("🤝 Support the Bot")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_message = (
        f"Welcome to Fitness Challenge Bot, {username}! 💪\n\n"
        "🎯 Create personalized fitness challenges\n"
        "📊 Track multiple exercises simultaneously\n"
        "📅 Get daily reminders and progress updates\n"
        "🏆 Achieve your fitness goals step by step!\n\n"
        "Choose an option below to get started:"
    )
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    
async def handle_new_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new challenge creation"""
    user = update.effective_user
    username = user.first_name or user.username or "User"
    
    # Create exercise selection keyboard
    keyboard = []
    for exercise in ExerciseType:
        keyboard.append([InlineKeyboardButton(
            f"{exercise.value.title()}", 
            callback_data=f"exercise_{exercise.name}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"{username}, choose an exercise for your new challenge! 🏋️‍♂️",
        reply_markup=reply_markup
    )

async def handle_my_challenges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's active challenges"""
    user = update.effective_user
    username = user.first_name or user.username or "User"
    user_id = str(user.id)
    
    active_challenges = bot_instance.get_active_challenges(user_id)
    
    if not active_challenges:
        await update.message.reply_text(
            f"{username}, you don't have any active challenges yet! 🎯\n"
            "Tap 'New Challenge' to create your first one! 💪"
        )
        return
    
    message = f"🏆 Your Active Challenges, {username}:\n\n"
    
    for i, progress in enumerate(active_challenges, 1):
        challenge = progress['challenge']
        exercise = challenge['exercise']
        current = challenge['current_reps']
        total = challenge['total_reps']
        percentage = progress['percentage']
        days_remaining = progress['days_remaining']
        
        status_emoji = "🔥" if progress['on_track'] else "⚠️"
        
        message += (
            f"{status_emoji} **{exercise.title()}**\n"
            f"Progress: {current:,}/{total:,} ({percentage:.1f}%)\n"
            f"Days left: {days_remaining}\n"
            f"Daily avg: {progress['actual_daily_avg']:.1f}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def handle_add_reps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle adding reps to challenges"""
    user = update.effective_user
    username = user.first_name or user.username or "User"
    user_id = str(user.id)
    
    active_challenges = bot_instance.get_active_challenges(user_id)
    
    if not active_challenges:
        await update.message.reply_text(
            f"{username}, you don't have any active challenges to add reps to! 🎯"
        )
        return
    
    # Create challenge selection keyboard
    keyboard = []
    for progress in active_challenges:
        challenge = progress['challenge']
        keyboard.append([InlineKeyboardButton(
            f"{challenge['exercise'].title()} ({challenge['current_reps']}/{challenge['total_reps']})",
            callback_data=f"add_reps_{challenge['id']}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"{username}, which challenge do you want to add reps to? 💪",
        reply_markup=reply_markup
    )

async def handle_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed progress and forecasts"""
    user = update.effective_user
    username = user.first_name or user.username or "User"
    user_id = str(user.id)
    
    active_challenges = bot_instance.get_active_challenges(user_id)
    
    if not active_challenges:
        await update.message.reply_text(
            f"{username}, you don't have any active challenges! Start one to see progress! 🎯"
        )
        return
    
    for progress in active_challenges:
        challenge = progress['challenge']
        exercise = challenge['exercise']
        
        # Create detailed progress message
        message = f"📊 **{exercise.title()} Challenge Progress**\n\n"
        
        # Basic stats
        current = challenge['current_reps']
        total = challenge['total_reps'] 
        percentage = progress['percentage']
        
        message += f"🎯 **Goal**: {total:,} reps in {challenge['target_days']} days\n"
        message += f"🔥 **Current**: {current:,} reps ({percentage:.1f}%)\n"
        message += f"📅 **Days elapsed**: {progress['days_elapsed']}\n"
        message += f"⏰ **Days remaining**: {progress['days_remaining']}\n\n"
        
        # Progress bar
        filled_blocks = int(percentage / 5)
        empty_blocks = 20 - filled_blocks
        progress_bar = "█" * filled_blocks + "░" * empty_blocks
        message += f"[{progress_bar}] {percentage:.1f}%\n\n"
        
        # Daily averages and forecasts
        message += f"📈 **Your daily average**: {progress['actual_daily_avg']:.1f} reps\n"
        message += f"🎯 **Target daily average**: {challenge['daily_target']:.1f} reps\n"
        
        if progress['days_remaining'] > 0:
            message += f"🚀 **Needed to finish on time**: {progress['needed_daily_avg']:.1f} reps/day\n\n"
        
        # Forecast
        if progress['projected_date']:
            projected_str = progress['projected_date'].strftime('%B %d, %Y')
            target_str = datetime.fromisoformat(challenge['target_date']).strftime('%B %d, %Y')
            
            if progress['on_track']:
                message += f"🎉 **Forecast**: You'll finish by {projected_str}!\n"
                if progress['projected_date'].date() <= datetime.fromisoformat(challenge['target_date']).date():
                    message += "✅ You're on track to meet your goal! 🏆"
                else:
                    days_late = (progress['projected_date'] - datetime.fromisoformat(challenge['target_date'])).days
                    message += f"⚠️ You'll be {days_late} days late. Consider increasing your daily reps!"
            else:
                message += f"⚠️ **Warning**: At current pace, you'll finish late!\n"
                message += f"🎯 **Target finish**: {target_str}\n"
                message += f"📊 **Projected finish**: {projected_str}"
        
        await update.message.reply_text(message, parse_mode='Markdown')

async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings menu"""
    user = update.effective_user
    username = user.first_name or user.username or "User"
    
    keyboard = [
        [InlineKeyboardButton("⏰ Reminder Times", callback_data="settings_reminders")],
        [InlineKeyboardButton("🌍 Timezone", callback_data="settings_timezone")],
        [InlineKeyboardButton("🔔 Toggle Reminders", callback_data="settings_toggle")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"{username}, choose a setting to configure:",
        reply_markup=reply_markup
    )

async def handle_exercise_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show exercise guides"""
    user = update.effective_user
    username = user.first_name or user.username or "User"
    
    keyboard = []
    for exercise in ExerciseType:
        keyboard.append([InlineKeyboardButton(
            f"{exercise.value.title()}", 
            callback_data=f"guide_{exercise.name}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"{username}, choose an exercise to see proper form and tips! 📚",
        reply_markup=reply_markup
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    username = user.first_name or user.username or "User"
    user_id = str(user.id)
    data = query.data
    
    if data.startswith("exercise_"):
        # Exercise selection for new challenge
        exercise_name = data.split("_")[1]
        exercise = ExerciseType[exercise_name]
        
        context.user_data['selected_exercise'] = exercise
        context.user_data['challenge_step'] = 'total_reps'
        
        await query.edit_message_text(
            f"{username}, you selected **{exercise.value.title()}**! 💪\n\n"
            f"Now, how many total {exercise.value} do you want to complete?\n"
            f"Enter a number (e.g., 1000):",
            parse_mode='Markdown'
        )
    
    elif data.startswith("add_reps_"):
        # Adding reps to specific challenge
        challenge_id = data.replace("add_reps_", "")
        context.user_data['selected_challenge'] = challenge_id
        context.user_data['adding_reps'] = True
        
        progress = bot_instance.get_challenge_progress(user_id, challenge_id)
        if progress:
            exercise = progress['challenge']['exercise']
            await query.edit_message_text(
                f"{username}, how many {exercise} did you complete? 💪\n"
                f"Enter the number:"
            )
    
    elif data.startswith("guide_"):
        # Exercise guide
        exercise_name = data.split("_")[1]
        exercise = ExerciseType[exercise_name]
        info = EXERCISE_INFO[exercise]
        
        guide_message = (
            f"📚 **{exercise.value.title()} Guide**\n\n"
            f"💡 **Proper Form**:\n{info['tips']}\n\n"
            f"🎥 **Tutorial Video**:\n{info['video']}\n\n"
            f"Remember: Quality over quantity! Perfect your form first! 💪"
        )
        
        await query.edit_message_text(guide_message, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    message_text = update.message.text
    user = update.effective_user
    username = user.first_name or user.username or "Unknown"
    user_id = str(user.id)

    logger.info(f"👤 USER ACTIVITY: {username} (ID: {user_id}) used: {message_text}")

    
    # Handle menu buttons
    if message_text == "🆕 New Challenge":
        await handle_new_challenge(update, context)
    elif message_text == "📊 My Challenges":
        await handle_my_challenges(update, context)
    elif message_text == "➕ Add Reps":
        await handle_add_reps(update, context)
    elif message_text == "📈 Progress":
        await handle_progress(update, context)
    elif message_text == "⚙️ Settings":
        await handle_settings(update, context)
    elif message_text == "📚 Exercise Guide":
        await handle_exercise_guide(update, context)
    elif message_text == "🤝 Support the Bot": # New condition
        support_message = (
        "Thank you for considering supporting the Fitness Challenge Bot! 🙏\n\n"
        "Your support helps keep the bot running and allows for new features.\n\n"
        "You can tip the developer here: [Tip Here!](https://coff.ee/gowk3mb)\n\n"
        "Every bit helps! ✨")
        await update.message.reply_text(support_message, parse_mode='Markdown', disable_web_page_preview=True)
    
    
    # Handle challenge creation flow
    elif context.user_data.get('challenge_step') == 'total_reps':
        try:
            total_reps = int(message_text)
            if total_reps <= 0:
                await update.message.reply_text(
                    f"{username}, please enter a positive number! 🤔"
                )
                return
            
            if total_reps > 100000:
                await update.message.reply_text(
                    f"{username}, that's quite ambitious! Please enter a more realistic number (max 100,000). 😅"
                )
                return
            
            context.user_data['total_reps'] = total_reps
            context.user_data['challenge_step'] = 'days'
            
            exercise = context.user_data['selected_exercise']
            await update.message.reply_text(
                f"Great! {total_reps:,} {exercise.value} it is! 🎯\n\n"
                f"Now, how many days do you want to complete this challenge?\n"
                f"Enter number of days (e.g., 30):"
            )
            
        except ValueError:
            await update.message.reply_text(
                f"{username}, please enter a valid number! 🔢"
            )
    
    elif context.user_data.get('challenge_step') == 'days':
        try:
            days = int(message_text)
            if days <= 0:
                await update.message.reply_text(
                    f"{username}, please enter a positive number of days! 📅"
                )
                return
            
            if days > 365:
                await update.message.reply_text(
                    f"{username}, that's over a year! Please choose a shorter timeframe (max 365 days). 📅"
                )
                return
            
            # Create the challenge
            exercise = context.user_data['selected_exercise']
            total_reps = context.user_data['total_reps']
            
            challenge_id = bot_instance.create_challenge(user_id, exercise, total_reps, days)
            
            daily_target = total_reps / days
            
            success_message = (
                f"🎉 Challenge Created Successfully, {username}!\n\n"
                f"🏋️‍♂️ **Exercise**: {exercise.value.title()}\n"
                f"🎯 **Goal**: {total_reps:,} reps in {days} days\n"
                f"📅 **Daily Target**: {daily_target:.1f} reps/day\n"
                f"📊 **Start Date**: {datetime.now().strftime('%B %d, %Y')}\n"
                f"🏁 **Target Finish**: {(datetime.now() + timedelta(days=days)).strftime('%B %d, %Y')}\n\n"
                f"💪 Your challenge starts now! Use '➕ Add Reps' to log your progress!\n\n"
                f"🔔 Daily reminders will help keep you on track!"
            )
            
            await update.message.reply_text(success_message, parse_mode='Markdown')
            
            # Clear challenge creation data
            context.user_data.clear()
            
        except ValueError:
            await update.message.reply_text(
                f"{username}, please enter a valid number of days! 📅"
            )
    
    # Handle adding reps
    elif context.user_data.get('adding_reps'):
        try:
            reps = int(message_text)
            if reps <= 0:
                await update.message.reply_text(
                    f"{username}, please enter a positive number! 💪"
                )
                return
            
            if reps > 10000:
                await update.message.reply_text(
                    f"{username}, that seems like a lot! Please enter a realistic number (max 10,000). 😅"
                )
                return
            
            challenge_id = context.user_data['selected_challenge']
            success = bot_instance.add_reps(user_id, challenge_id, reps)
            
            if success:
                progress = bot_instance.get_challenge_progress(user_id, challenge_id)
                if progress:
                    challenge = progress['challenge']
                    exercise = challenge['exercise']
                    
                    success_message = (
                        f"Excellent work, {username}! 🎉\n\n"
                        f"✅ **Added**: {reps} {exercise}\n"
                        f"📊 **Total**: {challenge['current_reps']:,}/{challenge['total_reps']:,}\n"
                        f"📈 **Progress**: {progress['percentage']:.1f}%\n"
                        f"📅 **Daily Average**: {progress['actual_daily_avg']:.1f}\n"
                    )
                    
                    if challenge['status'] == 'completed':
                        success_message += (
                            f"\n🎉🏆 **CHALLENGE COMPLETED!** 🏆🎉\n"
                            f"You've successfully completed {challenge['total_reps']:,} {exercise}!\n"
                            f"Amazing dedication and hard work! 💪✨"
                        )
                    elif progress['on_track']:
                        success_message += f"\n🔥 You're on track to meet your goal! Keep it up!"
                    else:
                        needed = progress['needed_daily_avg']
                        success_message += f"\n⚠️ To finish on time, aim for {needed:.1f} reps/day"
                    
                    await update.message.reply_text(success_message, parse_mode='Markdown')
            else:
                await update.message.reply_text(
                    f"{username}, there was an error adding your reps. Please try again! 🤔"
                )
            
            context.user_data.clear()
            
        except ValueError:
            await update.message.reply_text(
                f"{username}, please enter a valid number! 🔢"
            )
    
    
    else:
        await update.message.reply_text(
            f"{username}, please use the menu buttons to navigate! 👇"
        )

async def log_daily_summary(context: ContextTypes.DEFAULT_TYPE):
    """Log daily user summary for Railway"""
    total_users = len(bot_instance.user_data)
    active_challenges = 0
    
    for user_data in bot_instance.user_data.values():
        for challenge in user_data.get('challenges', {}).values():
            if challenge.get('status') == 'active':
                active_challenges += 1
    
    logger.info(f"📊 DAILY SUMMARY: {total_users} total users, {active_challenges} active challenges")

async def send_daily_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Send daily reminders to users with active challenges"""
    for user_id, user_data in bot_instance.user_data.items():
        if not user_data.get('reminders_enabled', True):
            continue
        
        active_challenges = bot_instance.get_active_challenges(user_id)
        if not active_challenges:
            continue
        
        # Get user info (this would need to be stored or retrieved differently in production)
        try:
            user_id_int = int(user_id)
            
            reminder_text = "🔔 **Daily Fitness Reminder!**\n\n"
            reminder_text += "💪 Time to work on your challenges:\n\n"
            
            for progress in active_challenges:
                challenge = progress['challenge']
                exercise = challenge['exercise']
                daily_target = challenge['daily_target']
                
                # Check if user has done reps today
                today = datetime.now().strftime('%Y-%m-%d')
                today_reps = challenge['daily_records'].get(today, 0)
                
                if today_reps == 0:
                    reminder_text += f"🎯 {exercise.title()}: {daily_target:.0f} reps needed\n"
                elif today_reps < daily_target:
                    remaining = daily_target - today_reps
                    reminder_text += f"🔥 {exercise.title()}: {remaining:.0f} more reps to reach daily goal\n"
                else:
                    reminder_text += f"✅ {exercise.title()}: Daily goal achieved! 🎉\n"
            
            reminder_text += "\n💪 You've got this! Every rep counts! 🏆"
            
            await context.bot.send_message(
                chat_id=user_id_int,
                text=reminder_text,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error sending reminder to user {user_id}: {e}")

def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    logger.info("🚀 FITNESS BOT STARTING ON RAILWAY")
    logger.info(f"📅 Started at: {datetime.now()}")

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    job_queue = application.job_queue
    job_queue.run_daily(
        log_daily_summary,
        time=time(hour=23, minute=59),  # 11:59 PM daily
        name="daily_summary"
    )

    # Add job queue for reminders
    job_queue = application.job_queue
    
    # Schedule morning reminders (9:00 AM daily)
    job_queue.run_daily(
        send_daily_reminders,
        time=time(hour=9, minute=0),
        name="morning_reminder"
    )
    
    # Schedule evening reminders (8:00 PM daily) 
    job_queue.run_daily(
        send_daily_reminders,
        time=time(hour=20, minute=0),
        name="evening_reminder"
    )
    
    logger.info("💪 Bot ready to help users achieve fitness goals!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

    # Start the bot
    print("🤖 Advanced Fitness Challenge Bot is starting...")
    print("💪 Ready to help users achieve their fitness goals!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()