import time
import random 
import string
from datetime import datetime
import requests
import schedule
from telegram import Bot

from src.config import TOKEN, load_settings
from src.models.db import Matrix
from src.config import ADMINS, DEVELOPER

bot = Bot(TOKEN)

def reset_daily_bonus():
    """
    Resets the daily bonus claim timestamps for all users.
    This function should run daily at midnight.
    """
    matrix = Matrix()
    users = matrix.get_users()
    for user in users:
        user.claimed_daily_bonus = None  # Clear the last claim timestamp
    matrix.commit()
    print("Daily bonus reset for all users.")

def claim_daily_bonus(user_id):
    """
    Checks if the user is eligible for the daily bonus and processes the claim.
    """
    matrix = Matrix()
    user = matrix.get_user(user_id)
    # Check if the user has already claimed the bonus in the last 24 hours
    if user.claimed_daily_bonus == True:
        return f"You can claim your bonus again tomorrow."
    
    settings = load_settings()
    user.bonus += settings['daily_bonus']
    user.balance += settings['daily_bonus']
    user.claimed_daily_bonus = True
    matrix.commit()
    return f"Daily bonus of {settings['daily_bonus']} TRX has been successfully added to your account!"

def create_task():
    matrix = Matrix()
    def generate_random_string():
        characters = string.ascii_letters + string.digits
        random_string = ''.join(random.choice(characters) for _ in range(8))
        return random_string
    
    matrix.clear_latest()
    task_code = generate_random_string()
    name = datetime.today().strftime('%Y-%m-%d')
    matrix.update_task(task_name=name, task_code=task_code)
    message = f"New task created: \nTask name: {name} \nTask code: {task_code}"   
    for user in ADMINS,DEVELOPER:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={user}&text={message}"
            print(requests.get(url).json())
        except Exception as e:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={DEVELOPER}&text={message}"
            print(requests.get(url).json())

def check_eligible_for_daily_bonus():
    """
    Check if a user is eligible for bonus
    Logic: check if user has referred 5 or more people in 24 hours
    """
    settings = load_settings()
    matrix = Matrix()
    users = matrix.get_users()
    for user in users:
        referrals_in_24_hours = 0
        for referral in user.referrals:
            if referral.joined_at > time.time() - 24 * 60 * 60 and referral.total_slots > 0:
                referrals_in_24_hours += 1
        if referrals_in_24_hours >= 5:
            user.bonus += settings['daily_bonus']
            user.balance += settings['daily_bonus']
            try:
                bot.sendMessage(user.user_id, f"Congratulations !\n"
                f"You got bonus of {settings['daily_bonus']} TRX for referring 5 persons in 24 hours")
            except:
                pass
    matrix.commit()

def debug():
    print("Scheduler is running...")


def check_eligible_for_weekly_bonus():
    """
    Logic: check if user has referred 5 and those refereed 5 each (1x5x5) or more people in week
    """
    settings = load_settings()
    matrix = Matrix()
    users = matrix.get_users()
    for user in users:
        lv1_referrals_in_week = 0
        for referral in user.referrals:
            if referral.joined_at > time.time() - 7 * 24 * 60 * 60 and referral.total_slots > 0:
                lv2_referrals_in_week = 0
                for r in referral.referrals:
                    if r.joined_at > time.time() - 7 * 24 * 60 * 60 and r.total_slots > 0:
                        lv2_referrals_in_week += 1
                if lv2_referrals_in_week >= 5:
                    lv1_referrals_in_week += 1
        if lv1_referrals_in_week >= 5:
            user.bonus += settings['weekly_bonus']
            user.balance += settings['weekly_bonus']
            try:
                bot.sendMessage(user.user_id, f"Congratulations !\n"
                f"You got bonus of {settings['weekly_bonus']} TRX for completing 3 levels referrals in a week.")
            except:
                pass
    matrix.commit()


def check_eligible_for_lifetime_bonus():
    """
    Logic: check if user has referred 5 and those refereed 5 each for 5 levels (1x5x5x5x5)
    """
    settings = load_settings()
    matrix = Matrix()
    users = matrix.get_users()
    for user in users:
        lv5_completed = 0
        if len(user.referrals) >= 5 and user.total_slots > 0:  # lv1
            for r in user.referrals:
                if len(r.referrals) >= 5 and r.total_slots > 0:  # lv2
                    for s in r.referrals:
                        if len(s.referrals) >= 5 and s.total_slots > 0:  # lv3
                            for t in s.referrals:
                                if len(t.referrals) >= 5 and t.total_slots > 0:  # lv4
                                    for u in t.referrals:
                                        if len(u.referrals) >= 5 and u.total_slots > 0:  # lv5
                                            lv5_completed += 1
        if lv5_completed >= 5:
            user.bonus += settings['5_level_bonus']
            user.balance += settings['5_level_bonus']
            try:
                bot.sendMessage(user.user_id, f"Congratulations !\n"
                f"You got bonus of {settings['daily_bonus']} TRX for completing 5 level referrals")
            except:
                pass
    matrix.commit()
    
def check_joined(update,context):

    group_chat_id = update.message.chat.id #replace this with group id number, if you already know it
    user_id = update.message.from_user.id #replace this with user id number, if you already know it
    check = None
    if(group_chat_id == 4712313487):
        check = context.bot.getChatMember(group_chat_id,user_id) #check if the user exist in the target group
    else:
        check = None
    if check: #If check variable isn't null, user is in the group
        update.message.reply_text("Successfully verified that you have joined the server.")
    else:
        update.message.reply_text("Please run the command in the server and not in our DMs!")


