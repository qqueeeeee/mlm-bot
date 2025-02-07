import html
import logging
import time
import traceback
from datetime import datetime
import schedule 
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
import threading 
import requests

from src import messages
from src.config import *
from src.models import db
from src.models.db import Matrix
from src.payment import is_wallet_valid, verify_transaction, pay, set_key, set_default_address
from src.bonus import claim_daily_bonus, check_eligible_for_daily_bonus, check_eligible_for_lifetime_bonus, check_joined, reset_daily_bonus, check_eligible_for_weekly_bonus, create_task, debug

GET_NAME, GET_EMAIL, GET_WALLET, EDIT_NAME, EDIT_EMAIL, EDIT_WALLET, PAYMENT_VERIFY = range(7)
GET_TASK_CODE = range(1)
SET_WELCOME, SET_SLOT_FEE, SET_REFERRAL_BONUS, SET_LEVEL_BONUS, SET_WALLET, SET_PRIVATE_KEY = range(10, 16)
WDC1, WDC2, WDC3, WDC4 = range(20, 24)
BROADCAST_MSG = 31


## change slot to daily bonus, 

MENU = [
    [BTN_BUY_SLOT, BTN_PROFILE],
    [BTN_REFERRAL_LINK, BTN_REFERRALS],
    [BTN_MY_SLOT, BTN_SETTINGS],
    [BTN_DEPOSIT, BTN_WITHDRAW],
    [BTN_BONUS, BTN_TASKS]
]

SETTINGS = [
    [BTN_EDIT_NAME],
    [BTN_EDIT_EMAIL],
    [BTN_EDIT_WALLET],
    [BTN_MAIN_MENU]
]

TASKS = [
    [BTN_CLAIM_CODE],
    [BTN_JOIN_CHANNEL],
    [BTN_MAIN_MENU]
]
UPDATES_COUNT = 0
UPDATES_COUNT_BEGIN_TIME = datetime.today()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

END = ConversationHandler.END


def admin_only(func):
    def inner1(update, context):
        if update.effective_user.id in ADMINS or update.effective_user.id == DEVELOPER:
            returned_value = func(update, context)
            return returned_value
        else:
            update.message.reply_text("Only Admins have access to this feature")
            return None

    return inner1


def count_updates():
    global UPDATES_COUNT, UPDATES_COUNT_BEGIN_TIME
    diff = datetime.today() - UPDATES_COUNT_BEGIN_TIME
    if diff.days >= 1:
        UPDATES_COUNT_BEGIN_TIME = datetime.today()
        UPDATES_COUNT = 0
    UPDATES_COUNT += 1


def start(update: Update, context):
    count_updates()
    matrix = Matrix()
    logger.info(f"{update.effective_user.first_name} started the bot")
    if settings['welcome_msg']:
        update.message.reply_text(settings['welcome_msg'])
    else:
        update.message.reply_text(messages.WELCOME)
    update.message.reply_text(f"Join our official group to talk with fellow investors \n{GROUP}")

    if matrix.get_user(update.effective_user.id) is None:
        try:
            referred_by = int(context.args[0])
        except Exception as e:
            matrix = Matrix()
            slot = matrix.get_slot(1)
            referred_by = slot.user_id if slot else 0

        # you can not refer yourself
        if referred_by == update.effective_user.id:
            matrix = Matrix()
            slot = matrix.get_slot(1)
            referred_by = slot.user_id if slot else 0
        bonus = settings['welcome_bonus']
        matrix.add_user(update.effective_user.id, referred_by, bonus=bonus)
        update.message.reply_text(
            f"Welcome to this program, congratulations you have got joining bonus of {bonus} TRX in your account"
            f" and refer 5 in 24 hrs and get another bonus for everyone who joined")
        return ask_name(update, context)
    else:
        update.message.reply_text(f'menu', reply_markup=ReplyKeyboardMarkup(MENU))
    return END


def ask_name(update: Update, context):
    count_updates()
    update.message.reply_text("Please enter your full name")
    return GET_NAME


def save_name(update: Update, context):
    count_updates()
    matrix = Matrix()
    user = matrix.get_user(update.effective_user.id)
    user.name = update.message.text
    matrix.commit()


def update_name(update: Update, context):
    count_updates()
    save_name(update, context)
    return ask_email(update, context)


def edit_name(update: Update, context):
    count_updates()
    save_name(update, context)
    update.message.reply_text(f'Name updated to {update.message.text}')
    return END


def ask_email(update: Update, context):
    count_updates()
    update.message.reply_text("Please enter your email")
    return GET_EMAIL


def save_email(update: Update, context):
    count_updates()
    matrix = Matrix()
    user = matrix.get_user(update.effective_user.id)
    user.email = update.message.text
    matrix.commit()


def update_email(update: Update, context):
    count_updates()
    save_email(update, context)
    return ask_wallet(update, context)


def edit_email(update: Update, context):
    count_updates()
    save_email(update, context)
    update.message.reply_text(f'Email updated to {update.message.text}')
    return END


def ask_wallet(update: Update, context):
    count_updates()
    update.message.reply_text("Please enter your TRX wallet address")
    return GET_WALLET



def save_wallet(update: Update, context):
    count_updates()
    matrix = Matrix()
    user = matrix.get_user(update.effective_user.id)
    user.wallet = update.message.text
    matrix.commit()


def update_wallet(update: Update, context):
    count_updates()
    if is_wallet_valid(update.message.text):
        save_wallet(update, context)
        update.message.reply_text(f'Click on {BTN_BUY_SLOT} button to buy slot.', reply_markup=ReplyKeyboardMarkup(MENU))
        return END
    else:
        update.message.reply_text(f'Invalid wallet address, '
                                  f'Please enter TRX wallet address that starts with T...')
        return GET_WALLET


def edit_wallet(update: Update, context):
    count_updates()
    if is_wallet_valid(update.message.text):
        save_wallet(update, context)
        update.message.reply_text(f'Wallet address updated to {update.message.text}')
        return END
    else:
        update.message.reply_text(f'Invalid wallet address, '
                                  f'Please enter TRX wallet address that starts with T...')
        return GET_WALLET

def handle_task_button(update: Update, context):
    """Handles Claiming tasks"""
    count_updates()
    update.message.reply_text("Enter the task code")
    return GET_TASK_CODE


def check_task_code(update: Update, context):
    """Processes the task code entered by the user."""
    count_updates()
    matrix = Matrix()
    task_code = update.message.text
    user = matrix.get_user(update.effective_user.id)
    ver = matrix.check_task_code(task_code=task_code)
    if ver is not None:
        if user.deposited != 0:
            amount = user.deposited/1000
        else:
            amount = 0.0001

        user.balance += amount
        update.message.reply_text(f"Successfully completed task! {amount} has been credited!")
        matrix.commit()

    else:
        update.message.reply_text("Invalid task code!")
    return END

def get_profile(update: Update, context):
    count_updates()
    matrix = Matrix()
    user = matrix.get_user(update.effective_user.id)
    update.message.reply_text(f"{user}")
    return END


def back_to_main_menu(update: Update, context):
    count_updates()
    update.message.reply_text('main menu', reply_markup=ReplyKeyboardMarkup(MENU))
    return END


def show_settings(update: Update, context):
    count_updates()
    update.message.reply_text('settings', reply_markup=ReplyKeyboardMarkup(SETTINGS))
    return END

def show_tasks(update: Update, contet):
    count_updates()
    update.message.reply_text('tasks',reply_markup=ReplyKeyboardMarkup(TASKS))
    return END

def my_slots(update: Update, context):
    count_updates()
    matrix = Matrix()
    user = matrix.get_user(update.effective_user.id)
    if user.slots:
        text = f'''You have purchased total {user.total_slots} slots '''  # at position {user.slots}'''
    else:
        text = f"You have not bought any slots yet, Please click on {BTN_BUY_SLOT}"
    update.message.reply_text(text)
    return END


def get_total_referrals(user):
    if len(user.referrals) == 0:
        return 1
    total = 1
    for u in user.referrals:
        total += get_total_referrals(u)
    return total


def get_total_active_referrals(user):
    total = 0
    current = user
    stack = []
    while True:
        if current is not None:
            if current.slots:
                total += 1
            if current.referrals:
                stack += current.referrals
            if stack:
                current = stack.pop()
            else:
                break
        else:
            break
    return total


def my_referrals(update: Update, context):
    count_updates()
    matrix = Matrix()
    user = matrix.get_user(update.effective_user.id)
    total = s_total = 0
    user_list = ""
    if user.referrals:
        total = len(user.referrals)
    for referral in user.referrals:
        if referral.slots:
            s_total += 1
            user_list += f"{referral.name} - ✅ - {referral.total_slots}\n"
        else:
            user_list += f"{referral.name} - ❌ - 0\n"

    tree_total = get_total_referrals(user)-1
    tree_active_total = get_total_active_referrals(user)

    text = f'''<b>Referral Summary</b>
Total Referrals In Tree: {tree_total}
Successful Referrals In Tree: {tree_active_total}

Referrals By You : {total}
Successful Referrals By You : {s_total}

<b>User List</b>
<b>Name    Status  Slots Bought</b>

{user_list}'''
    update.message.reply_text(text, parse_mode='HTML')
    return END


def referrals_tree(update: Update, context):
    # shows referrals of the user as a tree structure
    count_updates()
    matrix = Matrix()
    user = matrix.get_user(update.effective_user.id)
    if user.referrals:
        keyboard = []
        for referral in user.referrals:
            name = referral.name if referral.name else str(referral.user_id)
            keyboard.append([InlineKeyboardButton(name, callback_data=f'referral_{referral.user_id}')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(f"You have {len(user.referrals)} referrals", reply_markup=reply_markup)
    else:
        text = f"You have not referred anyone yet"
        update.message.reply_text(text)

def referral_tree_callback(update: Update, context):
    count_updates()
    matrix = Matrix()
    referral = matrix.get_user(int(update.callback_query.data.split('_')[1]))
    referral_name = referral.name if referral.name else referral.user_id
    if referral.referrals:
        keyboard = []
        for user in referral.referrals:
            name = user.name if user.name else str(user.user_id)
            keyboard.append([InlineKeyboardButton(name, callback_data=f'referral_{user.user_id}')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.callback_query.edit_message_text(f"{referral_name} has {len(referral.referrals)} referrals",
                                                reply_markup=reply_markup)
    else:
        update.callback_query.edit_message_text(f"{referral_name} has no referrals")
    


def my_referral_link(update: Update, context):
    count_updates()
    link = f"https://t.me/TRXflow_bot?start={update.effective_user.id}"
    text = f'''This is your referral link, share this with others and earn referral bonus of {
    settings['referral_percentage'][0] * 100}% ({settings['slot_fee'] * settings[
        'referral_percentage'][0]} TRXS per referral).

{link}

Note: Referral will be considered as successful only when user buys a slot and joins the matrix.'''
    update.message.reply_text(text)
    return END


def send_payment_instructions(update: Update, context):
    count_updates()
    text = f'''Please send TRX coin to below address and send me transaction ID/Hash of the payment
Cost of 1 slot = {settings['slot_fee']} TRX.

<pre>{settings['wallet']}</pre>

<b>Note: Please send from your registered wallet address only, so that we can verify it is coming from you.</b>
click /cancel to cancel the operation.'''
    update.message.reply_text(text, parse_mode='HTML')
    return PAYMENT_VERIFY


def get_transaction_id(update: Update, context):
    count_updates()
    update.message.reply_text(
        "Please send the transaction ID/Hash of the payment, click /cancel to cancel the operation.")
    return PAYMENT_VERIFY


#Convert from buying to claiming daily bonus

def buy_slot(update: Update, context):
    count_updates()
    matrix = Matrix()
    user = matrix.get_user(update.effective_user.id)

    if user.balance < settings['slot_fee']:
        update.message.reply_text(f"Not enough balance, please deposit TRX to buy slot.\n"
                                  f"Cost of 1 slot = {settings['slot_fee']} TRX")
        return END

    if user.last_buy_time:
        time_left = (user.last_buy_time + settings['buy_limit'] * 60 * 60) - time.time()
        if time_left > 0:
            update.message.reply_text(f"Buying limit reached.\nYou can buy after {(time_left / 60):.2f} minutes.")
            return END

    if user.total_slots % 2 == 1:
        slot = matrix.add_slot(OWNER)
        user.total_slots += 1
    else:
        slot = matrix.add_slot(update.effective_user.id)

    if slot:
        user.balance -= settings['slot_fee']
        user.last_buy_time = time.time()
        update.message.reply_text(f"Successfully bought slot")

    # disburse level income
    for percentage in settings['level_percentage']:
        slot = matrix.get_slot(slot.parent())
        if slot:
            parent_user = matrix.get_user(slot.user_id)
            parent_user.balance += settings['slot_fee'] * percentage
            parent_user.income += settings['slot_fee'] * percentage
        else:
            break

    # disburse referral bonus
    referred_user = matrix.get_user(user.referred_by)
    for percentage in settings['referral_percentage']:
        if referred_user:
            referred_user.balance += settings['slot_fee'] * percentage
            referred_user.income += settings['slot_fee'] * percentage
            referred_user = matrix.get_user(referred_user.referred_by)
        else:
            break

    matrix.commit()

    return END


def verify_payment(update: Update, context):
    count_updates()
    matrix = Matrix()
    user = matrix.get_user(update.effective_user.id)
    try:
        int(update.message.text, 16)
    except ValueError:
        update.message.reply_text("Invalid transaction ID")
        return END

    success, amount_received = verify_transaction(update.message.text, user.wallet, settings['wallet'])
    if not success:
        update.message.reply_text(amount_received)
        return END  # get_transaction_id(update, context)

    if matrix.is_duplicate_tx(update.message.text, update.effective_user.id):
        update.message.reply_text("Duplicate transaction ID, Please make a new payment.")
        return END  # get_transaction_id(update, context)

    user.balance += float(amount_received)
    user.deposited += float(amount_received)
    matrix.commit()
    update.message.reply_text("Payment received successfully")
    update.message.reply_text(f"Deposited {amount_received} TRX to wallet.\n\n"
                              f"Available balance : {user.balance}")

    return END



def withdraw_logic(update: Update, context):
    withdraw_condition = f'''<b>Condition for withdraw</b>

1. If you bought at least {wdc1.slots_min} gifts, 
you can withdraw {wdc1.withdraw} TRX and {wdc1.deposit} TRX will be used to buy gifts automatically.

2. If you bought at least {wdc2.slots_min} gifts and at least {wdc2.referral_min} referrals, 
you can withdraw {wdc2.withdraw} TRX and {wdc2.deposit} TRX will be used to buy gifts automatically.

3. If you bought at least {wdc3.slots_min} gifts and at least {wdc3.referral_min} referrals,
you can withdraw {wdc3.withdraw} TRX and {wdc3.deposit} TRX will be used to buy gifts automatically.

4. If you bought at least {wdc4.slots_min} gifts and at least {wdc4.referral_min} referrals, 
you can withdraw {wdc4.withdraw} TRX and {wdc4.deposit} TRX will be used to buy gifts automatically.
'''
    count_updates()
    update.message.reply_text(withdraw_condition, parse_mode='HTML')
    matrix = Matrix()
    user = matrix.get_user(update.effective_user.id)
    slots = user.total_slots
    referrals = len(user.referrals)

    if user.last_withdraw_time:
        time_left = (user.last_withdraw_time + settings['withdraw_limit'] * 60 * 60) - time.time()
        if time_left > 0:
            update.message.reply_text(f"Withdraw limit reached.\nYou can withdraw after {(time_left / 60):.2f} minutes.")
            return END

    if user.balance < 1:
        update.message.reply_text("You need to have at least 1 TRX balance.")
        return END

    if wdc1.referral_min <= referrals < wdc2.referral_min and slots > 0:
        withdraw = wdc1.withdraw
        deposit = wdc1.deposit
    elif wdc2.referral_min <= referrals < wdc3.referral_min:
        if slots > wdc2.slots_min:
            withdraw = wdc2.withdraw
            deposit = wdc2.deposit
        else:
            withdraw = wdc1.withdraw
            deposit = wdc1.deposit
    elif wdc3.referral_min <= referrals < wdc4.referral_min:
        if slots > wdc3.slots_min:
            withdraw = wdc3.withdraw
            deposit = wdc3.deposit
        elif slots > wdc2.slots_min:
            withdraw = wdc2.withdraw
            deposit = wdc2.deposit
        else:
            withdraw = wdc1.withdraw
            deposit = wdc1.deposit
    elif wdc4.referral_min <= referrals:
        if slots > wdc4.slots_min:
            withdraw = wdc4.withdraw
            deposit = wdc4.deposit
        elif slots > wdc3.slots_min:
            withdraw = wdc3.withdraw
            deposit = wdc3.deposit
        elif slots > wdc2.slots_min:
            withdraw = wdc2.withdraw
            deposit = wdc2.deposit
        else:
            withdraw = wdc1.withdraw
            deposit = wdc1.deposit
    elif user.withdrawn == 0:
        withdraw = user.withdrawn
        deposit = 0
    else:
        update.message.reply_text("You need to buy at least 1 slot to withdraw.")
        return END

    if user.balance >= withdraw + deposit:
        success, tx_id = pay(user.wallet, withdraw)
        if success:
            user.withdrawn += withdraw
            user.balance -= withdraw
            user.last_withdraw_time = time.time()

            slots_to_buy = int(deposit // settings['slot_fee'])
            user.balance -= (slots_to_buy * settings['slot_fee'])

            for i in range(slots_to_buy):
                slot = matrix.add_slot(user.user_id)

                # disburse level income
                for percentage in settings['level_percentage']:
                    slot = matrix.get_slot(slot.parent())
                    if slot:
                        parent_user = matrix.get_user(slot.user_id)
                        parent_user.balance += settings['slot_fee'] * percentage
                        parent_user.income += settings['slot_fee'] * percentage
                    else:
                        break

                # disburse referral bonus
                referred_user = matrix.get_user(user.referred_by)
                for percentage in settings['referral_percentage']:
                    if referred_user:
                        referred_user.balance += settings['slot_fee'] * percentage
                        referred_user.income += settings['slot_fee'] * percentage
                        referred_user = matrix.get_user(referred_user.referred_by)
                    else:
                        break

            matrix.commit()

            update.message.reply_text(f"Successfully sent {withdraw} TRX to your wallet.\n\n"
                                      f"Transaction ID : <pre>{tx_id}</pre>", parse_mode='HTML')
            update.message.reply_text(f"Successfully bought {slots_to_buy} slots from the balance amount.")
        else:
            update.message.reply_text(tx_id)
    else:
        update.message.reply_text(f"""You need to have at least {withdraw + deposit} TRX to withdraw.
{withdraw} TRX will be sent to your wallet.
{deposit} TRX will be used to buy {deposit // settings['slot_fee']} slots""")
    return END


def withdraw_logic_new(update: Update, context):
    withdraw_condition = f'''<b>Condition for withdraw</b>

1. If you bought at least {wdc1.slots_min} slot and at least {wdc1.referral_min} referrals. 
you can withdraw {wdc1.withdraw} TRX and {wdc1.deposit} TRX will be used to buy slots automatically.

2. If you bought at least {wdc2.slots_min} slots and at least {wdc2.referral_min} referrals.
you can withdraw {wdc2.withdraw} TRX and {wdc2.deposit} TRX will be used to buy slots automatically.

3. If you bought at least {wdc3.slots_min} slots and at least {wdc3.referral_min} referrals.
you can withdraw {wdc3.withdraw} TRX and {wdc3.deposit} TRX will be used to buy slots automatically.

4. If you bought at least {wdc4.slots_min} slots and at least {wdc4.referral_min} referrals.
you can withdraw {wdc4.withdraw} TRX and {wdc4.deposit} TRX will be used to buy slots automatically.
'''
    count_updates()
    update.message.reply_text(withdraw_condition, parse_mode='HTML')
    matrix = Matrix()
    user = matrix.get_user(update.effective_user.id)
    slots = user.total_slots
    referrals = 0
    for referral in user.referrals:
        if referral.slots:
            referrals += 1

    if user.balance < 1:
        update.message.reply_text("You need to have at least 1 TRX balance.")
        return END

    if wdc1.slots_min <= slots < wdc2.slots_min:
        if not wdc1.referral_min <= referrals:
            msg = f"You need to refer at least {wdc1.referral_min} to withdraw."
            update.message.reply_text(msg)
            return END
        withdraw = wdc1.withdraw
        deposit = wdc1.deposit
    elif wdc2.slots_min <= slots < wdc3.slots_min:
        if not wdc2.referral_min <= referrals:
            msg = f"You need to refer at least {wdc2.referral_min} to withdraw."
            update.message.reply_text(msg)
            return END
        withdraw = wdc2.withdraw
        deposit = wdc2.deposit
    elif wdc3.slots_min <= slots < wdc4.slots_min:
        if not wdc3.referral_min <= referrals:
            msg = f"You need to refer at least {wdc3.referral_min} to withdraw."
            update.message.reply_text(msg)
            return END
        withdraw = wdc3.withdraw
        deposit = wdc3.deposit
    elif wdc4.slots_min <= slots:
        if not wdc4.referral_min <= referrals:
            msg = f"You need to refer at least {wdc4.referral_min} to withdraw."
            update.message.reply_text(msg)
            return END

        if user.last_withdraw_time:
            time_left = (user.last_withdraw_time + settings['withdraw_limit'] * 60 * 60) - time.time()
            if time_left > 0:
                update.message.reply_text(
                    f"Withdraw limit reached.\nYou can withdraw after {(time_left / 60):.2f} minutes.")
                return END

        withdraw = wdc4.withdraw
        deposit = wdc4.deposit

    elif user.withdrawn == 0:
        withdraw = user.balance
        deposit = 0
    else:
        update.message.reply_text("You need to buy at least 1 slot to withdraw.")
        return END

    if user.balance >= withdraw + deposit:
        success, tx_id = pay(user.wallet, withdraw)
        if success:
            user.withdrawn += withdraw
            user.balance -= withdraw
            user.last_withdraw_time = time.time()

            slots_to_buy = int(deposit // settings['slot_fee'])
            user.balance -= (slots_to_buy * settings['slot_fee'])

            for i in range(slots_to_buy):
                if user.total_slots % 2 == 1:
                    slot = matrix.add_slot(OWNER)
                    user.total_slots += 1
                else:
                    slot = matrix.add_slot(user.user_id)

                # disburse level income
                for percentage in settings['level_percentage']:
                    slot = matrix.get_slot(slot.parent())
                    if slot:
                        parent_user = matrix.get_user(slot.user_id)
                        parent_user.balance += settings['slot_fee'] * percentage
                        parent_user.income += settings['slot_fee'] * percentage
                    else:
                        break

                # disburse referral bonus
                referred_user = matrix.get_user(user.referred_by)
                for percentage in settings['referral_percentage']:
                    if referred_user:
                        referred_user.balance += settings['slot_fee'] * percentage
                        referred_user.income += settings['slot_fee'] * percentage
                        referred_user = matrix.get_user(referred_user.referred_by)
                    else:
                        break

            matrix.commit()

            update.message.reply_text(f"Successfully sent {withdraw} TRX to your wallet.\n\n"
                                      f"Transaction ID : <pre>{tx_id}</pre>", parse_mode='HTML')
            update.message.reply_text(f"Successfully bought {slots_to_buy} slots from the balance amount.")
        else:
            update.message.reply_text(tx_id)
    else:
        update.message.reply_text(f"""You need to have at least {withdraw + deposit} TRX to withdraw.
{withdraw} TRX will be sent to your wallet.
{deposit} TRX will be used to buy {deposit // settings['slot_fee']} slots""")
    return END

def handle_bonus_button(update: Update, context):
    """
    Handles the 'Claim Daily Bonus' button click.
    """
    count_updates()
    response = claim_daily_bonus(update.effective_user.id)
    update.message.reply_text(response)






@admin_only
def get_zero_income_users(update: Update, context):
    count_updates()
    matrix = Matrix()
    users = matrix.get_zero_income_users()
    msg = "<b>Users with 0 income</b>\n"
    for user in users:
        msg += f"<pre>{user.user_id} - {user.slots[0].slot_id}</pre>\n"
        if len(msg) > 4000:
            update.message.reply_text(msg, parse_mode='HTML')
            msg = ""
    if msg:
        update.message.reply_text(msg, parse_mode='HTML')
    return END


@admin_only
def get_user_profile(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        user_id = int(args[1])
        matrix = Matrix()
        user = matrix.get_user(user_id)
        if user:
            update.message.reply_text(f"{user}")
        else:
            update.message.reply_text("Invalid user id")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/get_user user_id")
    return END


@admin_only
def add_income(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        user_id, amount = int(args[1]), float(args[2])
        matrix = Matrix()
        user = matrix.get_user(user_id)
        if user:
            user.income += amount
            user.balance += amount
            matrix.commit()
            update.message.reply_text("Added income to user")
        else:
            update.message.reply_text("Invalid user id")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/add_income user_id amount")

    return END


@admin_only
def add_deposit(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        user_id, amount = int(args[1]), float(args[2])
        matrix = Matrix()
        user = matrix.get_user(user_id)
        if user:
            user.deposited += amount
            user.balance += amount
            matrix.commit()
            update.message.reply_text("Deposited to user balance.")
        else:
            update.message.reply_text("Invalid user id")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/add_deposit user_id amount")

    return END


@admin_only
def add_income_to_zero_income_users(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        amount = float(args[1])
        matrix = Matrix()
        users = matrix.get_zero_income_users()
        for user in users:
            user.income += amount
            user.balance += amount
        matrix.commit()
        update.message.reply_text("Added income to user")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/add_income_all amount")

    return END

@admin_only
def add_balance(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        user_id, amount = int(args[1]), float(args[2])
        matrix = Matrix()
        user = matrix.get_user(user_id)
        if user:
            user.balance += amount
            matrix.commit()
            update.message.reply_text("Added balance to user")
        else:
            update.message.reply_text("Invalid user id")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/add_balance user_id amount")

    return END

@admin_only
def deduct_balance(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        user_id, amount = int(args[1]), float(args[2])
        matrix = Matrix()
        user = matrix.get_user(user_id)
        if user:
            user.withdrawn -= amount
            user.balance -= amount
            matrix.commit()
            update.message.reply_text("Deducted balance from user")
        else:
            update.message.reply_text("Invalid user id")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/deduct_balance user_id amount")

    return END


@admin_only
def get_last_unfilled_slot(update: Update, context):
    count_updates()
    matrix = Matrix()
    last_slot_id = matrix.get_total_slots()
    last_slot = matrix.get_slot(last_slot_id)
    parent = last_slot.parent()
    unfilled_slot = matrix.get_slot(parent + 1)
    user = matrix.get_user(unfilled_slot.user_id)
    update.message.reply_text(f"Unfilled slot number : {unfilled_slot.slot_id}\n\n"
                              f"Owner details\n\n{user}")
    return END


def get_top_referred(update: Update, context):
    count_updates()
    matrix = Matrix()
    msg = "Top 10 referred users\n\n"
    msg += "<b>{:<30}{:<5}</b>\n".format("Name", "Total referrals")
    user_ids = matrix.get_top_referred()
    for user_id in user_ids:
        if user_id[0] != OWNER:
            user = matrix.get_user(user_id[0])
            if user:
                msg += "{}   {}\n".format(user.name, len(user.referrals))
    update.message.reply_text(msg, parse_mode='HTML')
    return END


def tree_view(update: Update, context):
    count_updates()
    matrix = Matrix()
    last_slot_id = matrix.get_total_slots()
    last_slot = matrix.get_slot(last_slot_id)
    current_level = last_slot.level()
    l1, l2, l3 = current_level - 3, current_level - 2, current_level - 1
    user = matrix.get_user(update.effective_user.id)
    l1_slots = l2_slots = l3_slots = 0
    for slot in user.slots:
        if slot.level() == l1:
            l1_slots += 1
        elif slot.level() == l2:
            l2_slots += 1
        elif slot.level() == l3:
            l3_slots += 1
    update.message.reply_text(f"Your slots in last 3 levels\n\n"
                              f"Level 1 :   {l1_slots}\n"
                              f"Level 2 :   {l2_slots}\n"
                              f"Level 3 :   {l3_slots}")
    return END


@admin_only
def exchange_owners(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        s1, s2 = int(args[1]), float(args[2])
        matrix = Matrix()
        slot1 = matrix.get_slot(s1)
        slot2 = matrix.get_slot(s2)
        if slot1 and slot2:
            slot1.user_id, slot2.user_id = slot2.user_id, slot1.user_id
            matrix.commit()
            update.message.reply_text("Exchanged slot owners")
        else:
            update.message.reply_text("Invalid slot id")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/exchange slot1 slot2")
    return END


@admin_only
def download_db(update: Update, context):
    with open(SQLITE_FILE_PATH, 'rb') as f:
        update.message.reply_document(document=f, filename='database.db')
    return END


def cancel(update: Update, context):
    count_updates()
    update.message.reply_text(messages.CANCEL)
    return END


def help(update: Update, context):
    count_updates()
    update.message.reply_text(messages.HELP)
    return END


@admin_only
def admin(update, context):
    count_updates()
    update.message.reply_text(messages.ADMIN_HELP)
    return END


@admin_only
def get_message_count(update: Update, context):
    count_updates()
    update.message.reply_text(f"Today's total no of incoming messages: {UPDATES_COUNT}")
    return END


@admin_only
def get_broadcast_msg(update: Update, context):
    count_updates()
    update.message.reply_text("""Now send me the message to broadcast

Note: Broadcast is time consuming task, broadcast in non busy hours.
Click /cancel to exit from broadcast""")
    return BROADCAST_MSG


@admin_only
def broadcast(update: Update, context):
    count_updates()
    matrix = Matrix()
    users = matrix.get_users()
    update.message.reply_text(f"""
Sending broadcast to : {len(users)} users
Approximate time required: {len(users) / 120} minutes """)
    for user in users:
        try:
            update.message.copy(chat_id=user.user_id)
        except Exception as e:
            pass
    update.message.reply_text("Broadcast Completed")
    return END


@admin_only
def cancel_broadcast(update: Update, context):
    count_updates()
    update.message.reply_text("Broadcast cancelled")
    return END


@admin_only
def get_settings(update: Update, context):
    count_updates()
    msg = f'''<b>Bot Settings</b>
<pre>
Slot Fee             : {settings['slot_fee']} TRX
Referral Bonus %     : {settings['referral_percentage']}
Level Bonus %        : {settings['level_percentage']}
Buy time limit       : {settings['buy_limit']} hour
Withdraw time limit  : {settings['withdraw_limit']} hour
Wallet Address       : {settings['wallet']}
Private Key          : {PRIVATE_KEY[:4]}********{PRIVATE_KEY[-4:]}
Auto withdraw delay  : {settings['auto_withdraw_delay']}
Auto withdraw on     : {settings['auto_withdraw_on']}
Daily bonus          : {settings['daily_bonus']} TRX
Weekly bonus         : {settings['weekly_bonus']} TRX
5 level bonus        : {settings['5_level_bonus']} TRX
Welcome bonus        : {settings['welcome_bonus']} TRX
</pre>
'''
    update.message.reply_text(msg, parse_mode='HTML')
    return END



@admin_only
def get_slot_count(update: Update, context):
    matrix = Matrix()
    slots = matrix.get_total_slots()
    update.message.reply_text(f"Total slots bought in matrix : {slots}")
    return END


@admin_only
def get_user_count(update: Update, context):
    matrix = Matrix()
    users = matrix.get_total_users()
    update.message.reply_text(f"Total users : {users}")
    return END


@admin_only
def set_settings(update: Update, context):
    count_updates()
    cmd = update.message.text

    if cmd == '/set_welcome_message':
        update.message.reply_text('Please send welcome message as a single message.')
        return SET_WELCOME
    elif cmd == '/set_slot_fee':
        update.message.reply_text('Please send slot fee in TRX')
        return SET_SLOT_FEE
    elif cmd == '/set_referral_bonus':
        update.message.reply_text('Please send referral bonus percentage separated by comma, Ex: 0.1, 0.2, 0.3')
        return SET_REFERRAL_BONUS
    elif cmd == '/set_level_bonus':
        update.message.reply_text('Please send level bonus percentage separated by comma, Ex: 0.1, 0.2, 0.3')
        return SET_LEVEL_BONUS
    elif cmd == '/set_wallet':
        update.message.reply_text('Please send wallet address')
        return SET_WALLET
    elif cmd == '/set_private_key':
        update.message.reply_text('Please send private key of wallet')
        return SET_PRIVATE_KEY
    elif cmd == '/set_wdc1':
        update.message.reply_text('Please send min_slots, min_referrals, withdraw, deposit separated by comma')
        return WDC1
    elif cmd == '/set_wdc2':
        update.message.reply_text('Please send min_slots, min_referrals, withdraw, deposit separated by comma')
        return WDC2
    elif cmd == '/set_wdc3':
        update.message.reply_text('Please send min_slots, min_referrals, withdraw, deposit separated by comma')
        return WDC3
    elif cmd == '/set_wdc4':
        update.message.reply_text('Please send min_slots, min_referrals, withdraw, deposit separated by comma')
        return WDC4
    else:
        update.message.reply_text(messages.ADMIN_HELP)
        return END


@admin_only
def set_welcome_msg(update: Update, context):
    settings['welcome_msg'] = update.message.text
    save_settings(settings)
    update.message.reply_text('Welcome message updated')
    return END


@admin_only
def set_slot_fee(update: Update, context):
    try:
        settings['slot_fee'] = float(update.message.text)
        save_settings(settings)
        update.message.reply_text("Slot fee updated")
    except Exception as e:
        update.message.reply_text(str(e))
    return END


@admin_only
def set_referral_bonus(update: Update, context):
    try:
        ref_per_str = update.message.text.split(',')
        settings['referral_percentage'] = [float(i) for i in ref_per_str]
        save_settings(settings)
        update.message.reply_text("Referral bonus updated.")
    except Exception as e:
        update.message.reply_text(str(e))
    return END


@admin_only
def set_level_bonus(update: Update, context):
    try:
        lvl_per_str = update.message.text.split(',')
        settings['level_percentage'] = [float(i) for i in lvl_per_str]
        save_settings(settings)
        update.message.reply_text("Level bonus updated.")
    except Exception as e:
        update.message.reply_text(str(e))
    return END


@admin_only
def set_wallet(update: Update, context):
    try:
        if is_wallet_valid(update.message.text):
            settings['wallet'] = update.message.text
            save_settings(settings)
            set_default_address(settings['wallet'])
            update.message.reply_text("Wallet address updated")
        else:
            update.message.reply_text('Invalid wallet address')
    except Exception as e:
        update.message.reply_text(str(e))
    return END


@admin_only
def set_private_key(update: Update, context):
    global PRIVATE_KEY
    try:
        PRIVATE_KEY = update.message.text
        set_key(PRIVATE_KEY)
        update.message.reply_text('Private key updated')
    except Exception as e:
        update.message.reply_text(str(e))
    return END


@admin_only
def set_wdc1(update: Update, context):
    global wdc1
    args = update.message.text.split(',')
    if len(args) == 4:
        slots_min, referral_min, withdraw, deposit = args
        wdc1 = WithdrawCondition(int(slots_min), int(referral_min), int(withdraw), int(deposit))
        settings['wdc1'] = [int(slots_min), int(referral_min), int(withdraw), int(deposit)]
        save_settings(settings)
        update.message.reply_text("Withdraw condition 1 set successfully.")
    else:
        update.message.reply_text("Invalid format, please check the command again.")
    return END


@admin_only
def set_wdc2(update: Update, context):
    global wdc2
    args = update.message.text.split(',')
    if len(args) == 4:
        slots_min, referral_min, withdraw, deposit = args
        wdc2 = WithdrawCondition(int(slots_min), int(referral_min), int(withdraw), int(deposit))
        settings['wdc2'] = [int(slots_min), int(referral_min), int(withdraw), int(deposit)]
        save_settings(settings)
        update.message.reply_text("Withdraw condition 2 set successfully.")
    else:
        update.message.reply_text("Invalid format, please check the command again.")
    return END


@admin_only
def set_wdc3(update: Update, context):
    global wdc3
    args = update.message.text.split(',')
    if len(args) == 4:
        slots_min, referral_min, withdraw, deposit = args
        wdc3 = WithdrawCondition(int(slots_min), int(referral_min), int(withdraw), int(deposit))
        settings['wdc3'] = [int(slots_min), int(referral_min), int(withdraw), int(deposit)]
        save_settings(settings)
        update.message.reply_text("Withdraw condition 3 set successfully.")
    else:
        update.message.reply_text("Invalid format, please check the command again.")
    return END


@admin_only
def set_wdc4(update: Update, context):
    global wdc4
    args = update.message.text.split(',')
    if len(args) == 4:
        slots_min, referral_min, withdraw, deposit = args
        wdc4 = WithdrawCondition(int(slots_min), int(referral_min), int(withdraw), int(deposit))
        settings['wdc4'] = [int(slots_min), int(referral_min), int(withdraw), int(deposit)]
        save_settings(settings)
        update.message.reply_text("Withdraw condition 4 set successfully.")
    else:
        update.message.reply_text("Invalid format, please check the command again.")
    return END


@admin_only
def set_buy_time_limit(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        limit = float(args[1])
        settings['buy_limit'] = limit
        save_settings(settings)
        update.message.reply_text(f"Set buy limit time to {limit} hours")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/set_buy_limit hour")

    return END


@admin_only
def set_withdraw_time_limit(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        limit = float(args[1])
        settings['withdraw_limit'] = limit
        save_settings(settings)
        update.message.reply_text(f"Set withdraw limit time to {limit} hours")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/set_withdraw_limit hour")

    return END


@admin_only
def set_aw_delay(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        limit = float(args[1])
        settings['auto_withdraw_delay'] = limit
        save_settings(settings)
        update.message.reply_text(f"Set auto withdraw delay time to {limit} seconds")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/set_aw_delay seconds")

    return END


@admin_only
def set_aw_mode(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        mode = args[1]
        if mode == 'on':
            settings['auto_withdraw_on'] = True
        elif mode == 'off':
            settings['auto_withdraw_on'] = False
        else:
            update.message.reply_text("Invalid format.\nsend like this \n/set_aw_mode on/off")
        save_settings(settings)
        update.message.reply_text(f"Set auto withdraw mode to {mode}")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/set_aw_mode on/off")
    return END


@admin_only
def set_daily_bonus(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        bonus = float(args[1])
        settings['daily_bonus'] = bonus
        save_settings(settings)
        update.message.reply_text(f"Set daily bonus to {bonus} TRX")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/set_daily_bonus amount")
    return END


@admin_only
def set_weekly_bonus(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        bonus = float(args[1])
        settings['weekly_bonus'] = bonus
        save_settings(settings)
        update.message.reply_text(f"Set weekly bonus to {bonus} TRX")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/set_weekly_bonus amount")
    return END


@admin_only
def set_5_level_bonus(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        bonus = float(args[1])
        settings['5_level_bonus'] = bonus
        save_settings(settings)
        update.message.reply_text(f"Set 5 level bonus to {bonus} TRX")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/set_5_level_bonus amount")
    return END

@admin_only
def set_welcome_bonus(update: Update, context):
    count_updates()
    args = update.message.text.split()
    try:
        bonus = float(args[1])
        settings['welcome_bonus'] = bonus
        save_settings(settings)
        update.message.reply_text(f"Set welcome bonus to {bonus} TRX")
    except Exception as e:
        update.message.reply_text("Invalid format.\nsend like this \n/set_welcome_bonus amount")
    return END

@admin_only
def get_task_code(update: Update, context):
    count_updates()
    matrix = Matrix()
    task_code = matrix.return_task_code()
    update.message.reply_text(f"{task_code}")

@admin_only
def create_new_task(update: Update, context):
    count_updates()
    create_task()
    update.message.reply_text("Successfully invalidated the old task and created new one!")


def error_handler(update: Update, context) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    context.bot.send_message(
        chat_id=DEVELOPER, text=message[:4095], parse_mode='HTML'
    )


def main() -> None:
    # Create the Updater and pass it your bot's token.
    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("profile", get_profile))
    dispatcher.add_handler(CommandHandler("top_referred", get_top_referred))
    dispatcher.add_handler(CommandHandler("tree_view", tree_view))
    dispatcher.add_handler(CommandHandler("my_referral_tree", referrals_tree))
    dispatcher.add_handler(CommandHandler("daily_bonus", handle_bonus_button))
    dispatcher.add_handler(CommandHandler("verify_join", check_joined))

    # admin commands
    dispatcher.add_handler(CommandHandler("admin", admin))
    dispatcher.add_handler(CommandHandler("messages", get_message_count))
    dispatcher.add_handler(CommandHandler("get", get_settings))
    dispatcher.add_handler(CommandHandler("get_slots", get_slot_count))
    dispatcher.add_handler(CommandHandler("get_users", get_user_count))
    dispatcher.add_handler(CommandHandler("get_zero_income_users", get_zero_income_users))
    dispatcher.add_handler(CommandHandler("get_user", get_user_profile))
    dispatcher.add_handler(CommandHandler("add_income", add_income))
    dispatcher.add_handler(CommandHandler("add_income_all", add_income_to_zero_income_users))
    dispatcher.add_handler(CommandHandler("add_balance", add_balance))
    dispatcher.add_handler(CommandHandler("deduct_balance", deduct_balance))
    dispatcher.add_handler(CommandHandler("get_last_slot", get_last_unfilled_slot))
    dispatcher.add_handler(CommandHandler("add_deposit", add_deposit))
    dispatcher.add_handler(CommandHandler("set_buy_limit", set_buy_time_limit))
    dispatcher.add_handler(CommandHandler("set_withdraw_limit", set_withdraw_time_limit))
    dispatcher.add_handler(CommandHandler("exchange", exchange_owners))
    dispatcher.add_handler(CommandHandler("download", download_db))
    dispatcher.add_handler(CommandHandler("set_aw_delay", set_aw_delay))
    dispatcher.add_handler(CommandHandler("set_aw_mode", set_aw_mode))
    dispatcher.add_handler(CommandHandler("set_daily_bonus", set_daily_bonus))
    dispatcher.add_handler(CommandHandler("set_weekly_bonus", set_weekly_bonus))
    dispatcher.add_handler(CommandHandler("set_5_level_bonus", set_5_level_bonus))
    dispatcher.add_handler(CommandHandler("set_welcome_bonus", set_welcome_bonus))
    dispatcher.add_handler(CommandHandler("get_task_code", get_task_code))
    dispatcher.add_handler(CommandHandler("create_new_task", create_new_task))

    dispatcher.add_handler(MessageHandler(Filters.regex(f'^({BTN_PROFILE})$'), get_profile))
    dispatcher.add_handler(MessageHandler(Filters.regex(f'^({BTN_WITHDRAW})$'), withdraw_logic_new))
    dispatcher.add_handler(MessageHandler(Filters.regex(f'^({BTN_MY_SLOT})$'), my_slots))
    dispatcher.add_handler(MessageHandler(Filters.regex(f'^({BTN_REFERRALS})$'), my_referrals))
    dispatcher.add_handler(MessageHandler(Filters.regex(f'^({BTN_REFERRAL_LINK})$'), my_referral_link))
    dispatcher.add_handler(MessageHandler(Filters.regex(f'^({BTN_SETTINGS})$'), show_settings))
    dispatcher.add_handler(MessageHandler(Filters.regex(f'^({BTN_MAIN_MENU})$'), back_to_main_menu))
    dispatcher.add_handler(MessageHandler(Filters.regex(f'^({BTN_BUY_SLOT})$'), buy_slot))
    dispatcher.add_handler(MessageHandler(Filters.regex(f'^({BTN_BONUS})$'), handle_bonus_button))
    dispatcher.add_handler(MessageHandler(Filters.regex(f'^({BTN_TASKS})$'), show_tasks))
    dispatcher.add_handler(MessageHandler(Filters.regex(f'^({BTN_JOIN_CHANNEL})$'), check_joined))

  
    #callback handler for referral tree
    dispatcher.add_handler(CallbackQueryHandler(referral_tree_callback))

    conv_handler1 = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            GET_NAME: [
                MessageHandler(Filters.text & ~Filters.command, update_name)],
            GET_EMAIL: [MessageHandler(Filters.text & ~Filters.command, update_email)],
            GET_WALLET: [MessageHandler(Filters.text & ~Filters.command, update_wallet)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    conv_handler2 = ConversationHandler(
        entry_points=[CommandHandler('broadcast', get_broadcast_msg)],
        states={
            BROADCAST_MSG: [MessageHandler(~Filters.command, broadcast)],
        },
        fallbacks=[CommandHandler('cancel', cancel_broadcast)]
    )

    conv_handler3 = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(f'^({BTN_EDIT_NAME})$'), ask_name)],
        states={
            GET_NAME: [MessageHandler(Filters.text & ~Filters.command, edit_name)]
        },
        fallbacks=[CommandHandler('cancel', cancel),
                   MessageHandler(Filters.regex(f'^({BTN_MAIN_MENU})$'), back_to_main_menu)]
    )

    conv_handler4 = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(f'^({BTN_EDIT_EMAIL})$'), ask_email)],
        states={
            GET_EMAIL: [MessageHandler(Filters.text & ~Filters.command, edit_email)]
        },
        fallbacks=[CommandHandler('cancel', cancel),
                   MessageHandler(Filters.regex(f'^({BTN_MAIN_MENU})$'), back_to_main_menu)],
    )

    conv_handler5 = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(f'^({BTN_EDIT_WALLET})$'), ask_wallet)],
        states={
            GET_WALLET: [MessageHandler(Filters.text & ~Filters.command, edit_wallet)]
        },
        fallbacks=[CommandHandler('cancel', cancel),
                   MessageHandler(Filters.regex(f'^({BTN_MAIN_MENU})$'), back_to_main_menu)],
    )

    conv_handler6 = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(f'^({BTN_DEPOSIT})$'), send_payment_instructions)],
        states={
            PAYMENT_VERIFY: [MessageHandler(Filters.text & ~Filters.command, verify_payment)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    conv_handler7 = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(f'^({BTN_CLAIM_CODE})$'), handle_task_button)],
        states={
            GET_TASK_CODE: [MessageHandler(Filters.text & ~Filters.command, check_task_code)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )


    conv_handler8 = ConversationHandler(
        entry_points=[CommandHandler('set_welcome_message', set_settings),
                      CommandHandler('set_slot_fee', set_settings),
                      CommandHandler('set_referral_bonus', set_settings),
                      CommandHandler('set_level_bonus', set_settings),
                      CommandHandler('set_wallet', set_settings),
                      CommandHandler('set_private_key', set_settings),
                      CommandHandler('set_wdc1', set_settings),
                      CommandHandler('set_wdc2', set_settings),
                      CommandHandler('set_wdc3', set_settings),
                      CommandHandler('set_wdc4', set_settings)
                      ],
        states={
            SET_WELCOME: [MessageHandler(~Filters.command, set_welcome_msg)],
            SET_SLOT_FEE: [MessageHandler(Filters.text & ~Filters.command, set_slot_fee)],
            SET_REFERRAL_BONUS: [MessageHandler(Filters.text & ~Filters.command, set_referral_bonus)],
            SET_LEVEL_BONUS: [MessageHandler(Filters.text & ~Filters.command, set_level_bonus)],
            SET_WALLET: [MessageHandler(Filters.text & ~Filters.command, set_wallet)],
            SET_PRIVATE_KEY: [MessageHandler(Filters.text & ~Filters.command, set_private_key)],
            WDC1: [MessageHandler(Filters.text & ~Filters.command, set_wdc1)],
            WDC2: [MessageHandler(Filters.text & ~Filters.command, set_wdc2)],
            WDC3: [MessageHandler(Filters.text & ~Filters.command, set_wdc3)],
            WDC4: [MessageHandler(Filters.text & ~Filters.command, set_wdc4)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )


    
    dispatcher.add_handler(conv_handler1)
    dispatcher.add_handler(conv_handler2)
    dispatcher.add_handler(conv_handler3)
    dispatcher.add_handler(conv_handler4)
    dispatcher.add_handler(conv_handler5)
    dispatcher.add_handler(conv_handler6)
    dispatcher.add_handler(conv_handler7)
    dispatcher.add_handler(conv_handler8)

    dispatcher.add_error_handler(error_handler)

    # Start the Bot
    updater.start_polling()

    updater.idle()

def error_handler(update: Update, context) -> None:
    """
    Handles exceptions raised during update handling.
    Sends a friendly message to the user and sends the exception details to the developer.
    """
    # Get the traceback as a string
    error_traceback = "".join(
        traceback.format_exception(None, context.error, context.error.__traceback__)
    )

    # Send a user-friendly error message to the user
    if update and update.effective_user:
        try:
            context.bot.send_message(
                chat_id=update.effective_user.id,
                text="Oops! Something went wrong. The issue has been reported, and we'll fix it soon!"
            )
        except Exception as e:
            print(f"Failed to send error message to user: {e}")

    # Send the detailed error traceback to the developer
    if DEVELOPER:
        try:
            context.bot.send_message(
                chat_id=DEVELOPER,
                text=(
                    f"An exception occurred while handling an update.\n\n"
                    f"<b>Exception:</b>\n<pre>{html.escape(error_traceback)}</pre>\n\n"
                    f"<b>Update:</b>\n<pre>{html.escape(json.dumps(update.to_dict(), indent=2, ensure_ascii=False))}</pre>"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"Failed to send error message to developer: {e}")

    # Log the error in the bot's log file (optional but recommended)
    context.bot.logger.error("Exception while handling an update:", exc_info=context.error)

def start_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    settings = load_settings()

    wdc1 = WithdrawCondition(*settings['wdc1'])
    wdc2 = WithdrawCondition(*settings['wdc2'])
    wdc3 = WithdrawCondition(*settings['wdc3'])
    wdc4 = WithdrawCondition(*settings['wdc4'])

    schedule.every(10).minutes.do(check_eligible_for_lifetime_bonus)
    schedule.every().day.at("00:00").do(check_eligible_for_daily_bonus)
    schedule.every().day.at("00:00").do(check_eligible_for_weekly_bonus)
    schedule.every().day.at("00:00").do(reset_daily_bonus)
    schedule.every().day.at("00:00").do(create_task)

    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()

    b = Bot(TOKEN)
    b.set_my_commands(COMMANDS)
    db.create_tables()
    main()

