import json
import os 
from telegram import BotCommand

TOKEN = os.getenv("TELEGRAM_TOKEN")
OWNER_USERNAME = "@que"
OWNER = 5229812278
DEVELOPER = 5494608725
ADMINS = [5229812278, 1457077956]
GROUP = "https://t.me/tronflowchat"
GROUP_ID = 4712313487
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

SQLITE_FILE_PATH = "D:\Programming\mlm-bot-old\db\my_database.db"

COMMANDS = [
    BotCommand('start', 'Start chatting with bot.'),
    BotCommand('bonus', 'Claim your daily bonus'),
    BotCommand('profile', 'Get my profile'),
    BotCommand('top_referred', 'Get top referred user'),
    BotCommand('tree_view', 'Get your gifts in last 3 levels of matrix'),
    BotCommand('my_referral_tree', 'Get your referral tree view'),
    BotCommand('verify_join','Verify that you joined the server'),
    BotCommand('cancel', 'Cancel operation')]


# reply buttons, menu
BTN_BUY_SLOT = 'BUY GIFT'
BTN_BONUS = 'BONUS'
BTN_TASKS = 'TASKS'
BTN_MY_SLOT = 'MY GIFTS'
BTN_REFERRALS = 'REFERRALS'
BTN_WITHDRAW = 'WITHDRAW'
BTN_REFERRAL_LINK = 'REFERRAL LINK'
BTN_SETTINGS = 'SETTINGS'
BTN_PROFILE = 'MY PROFILE'
BTN_DEPOSIT = 'DEPOSIT'


# settings
BTN_EDIT_NAME = 'EDIT NAME'
BTN_EDIT_EMAIL = 'EDIT EMAIL'
BTN_EDIT_WALLET = 'EDIT WALLET ADDRESS'
BTN_MAIN_MENU = 'BACK TO MENU'

#Tasks
BTN_CLAIM_CODE = 'CLAIM CODE'
BTN_JOIN_CHANNEL = 'JOIN OUR CHANNEL'
class WithdrawCondition:
    def __init__(self, slots_min, referral_min, withdraw, deposit):
        self.slots_min = slots_min
        self.referral_min = referral_min
        self.withdraw = withdraw
        self.deposit = deposit


def load_settings():
    with open("settings.json", "r") as f:
        d = f.read()
    return json.loads(d)


def save_settings(settings):
    with open("settings.json", "w") as f:
        d = json.dumps(settings)
        f.write(d)
