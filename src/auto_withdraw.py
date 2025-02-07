import time

from telegram import Bot

from src.config import load_settings, WithdrawCondition, OWNER, TOKEN
from src.models.db import Matrix
from src.payment import pay


def withdraw_logic(matrix, user):
    slots = user.total_slots
    referrals = 0
    for referral in user.referrals:
        if referral.slots:
            referrals += 1

    if user.balance < 1:
        return None

    if wdc1.slots_min <= slots < wdc2.slots_min:
        withdraw = wdc1.withdraw
        deposit = wdc1.deposit
        if not wdc1.referral_min <= referrals:
            withdraw = 0

    elif wdc2.slots_min <= slots < wdc3.slots_min:
        withdraw = wdc2.withdraw
        deposit = wdc2.deposit
        if not wdc2.referral_min <= referrals:
            withdraw = 0

    elif wdc3.slots_min <= slots < wdc4.slots_min:
        withdraw = wdc3.withdraw
        deposit = wdc3.deposit
        if not wdc3.referral_min <= referrals:
            withdraw = 0

    elif wdc4.slots_min <= slots:
        withdraw = wdc4.withdraw
        deposit = wdc4.deposit
        if not wdc4.referral_min <= referrals:
            withdraw = 0
    else:
        deposit = settings['slot_fee']
        withdraw = 0

    if user.wallet is None or user.user_id == OWNER:
        withdraw = 0

    if user.balance >= withdraw + deposit and withdraw > 0:
        try:
            success, tx_id = pay(user.wallet, withdraw)
            if success:
                user.withdrawn += withdraw
                user.balance -= withdraw
                bot.sendMessage(chat_id=user.user_id, text=f"Successfully sent {withdraw} TRX to your wallet.\n\n"
                f"Transaction ID : <pre>{tx_id}</pre>", parse_mode='HTML')
            else:
                bot.sendMessage(chat_id=user.user_id, text=f"Failed to send TRX to your wallet.\n\nError happened\n{tx_id}")
        except Exception as e:
            pass
        finally:
            matrix.commit()

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

    if slots_to_buy > 0:
        bot.sendMessage(chat_id=user.user_id, text=f"Successfully bought {slots_to_buy} slots from the balance amount.")


def auto_withdraw():
    matrix = Matrix()
    users = matrix.get_users()
    for user in users:
        withdraw_logic(matrix, user)


if __name__ == '__main__':
    bot = Bot(TOKEN)
    while True:
        settings = load_settings()
        wdc1 = WithdrawCondition(*settings['wdc1'])
        wdc2 = WithdrawCondition(*settings['wdc2'])
        wdc3 = WithdrawCondition(*settings['wdc3'])
        wdc4 = WithdrawCondition(*settings['wdc4'])

        if settings['auto_withdraw_on']:
            auto_withdraw()

        time.sleep(settings['auto_withdraw_delay'])
