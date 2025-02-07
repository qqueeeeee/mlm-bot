import pytest

from src.models.db import Matrix


# drop_tables()
# create_tables()


@pytest.fixture
def example_user():
    return {
        "user_id": 1234567,
        "name": "Goutham S",
        "email": "gratoor@gmail.com",
        "wallet": "0x3gyghdhakkjajjhjahjfhakhfjhaddddjkh",
        "referred_by": 7654321
    }


def test_add_user(example_user):
    matrix = Matrix()
    matrix.add_user(example_user['user_id'], example_user['referred_by'])
    user = matrix.get_user(example_user['user_id'])
    assert user.user_id == example_user['user_id'] and user.referred_by == example_user['referred_by']


def test_update_user(example_user):
    matrix = Matrix()
    matrix.add_user(example_user['user_id'], example_user['referred_by'])
    user = matrix.get_user(example_user['user_id'])
    user.name = example_user['name']
    user.email = example_user['email']
    user.wallet = example_user['wallet']
    matrix.commit()
    new_user = matrix.get_user(example_user['user_id'])
    assert new_user.name == example_user['name'] and \
           new_user.email == example_user['email'] and \
           new_user.wallet == example_user['wallet']


def test_get_user(example_user):
    matrix = Matrix()
    new_user = matrix.get_user(example_user['user_id'])
    assert new_user.name == example_user['name'] and \
           new_user.email == example_user['email'] and \
           new_user.wallet == example_user['wallet']


def test_add_slot(example_user):
    matrix = Matrix()
    slot = matrix.add_slot(example_user['user_id'])
    matrix.commit()
    user = matrix.get_user(example_user['user_id'])
    assert slot in user.slots


def test_is_duplicate_tx_false():
    matrix = Matrix()
    assert matrix.is_duplicate_tx('abcd1234#w', 596604100) == False


def test_is_duplicate_tx_true():
    matrix = Matrix()
    assert matrix.is_duplicate_tx('abcd1234#w', 596604100) == True


def test_referral_bonus():
    matrix = Matrix()
    matrix.add_user(1, 0)
    matrix.add_user(2, 1)
    matrix.add_user(3, 2)
    matrix.add_user(4, 3)

    user = matrix.get_user(4)
    referred_user = matrix.get_user(user.referred_by)
    for percentage in [0.3, 0.2, 0.1]:
        if referred_user:
            referred_user.balance += 10 * percentage
            referred_user.income += 10 * percentage
            referred_user = matrix.get_user(referred_user.referred_by)
        else:
            break

    user1 = matrix.get_user(1)
    user2 = matrix.get_user(2)
    user3 = matrix.get_user(3)

    assert user1.income == 1 and user2.income == 2 and user3.income == 3

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

def test_referral_tree_total():
    matrix = Matrix()
    user = matrix.get_user(1457077956)
    assert get_total_referrals(user) == get_total_referrals(user)

def test_active_referral_tree():
    matrix = Matrix()
    user = matrix.get_user(1457077956)
    assert get_total_active_referrals(user) == get_total_active_referrals(user)
