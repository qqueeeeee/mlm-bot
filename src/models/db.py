import time

from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, create_engine, func, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref, sessionmaker

from src.config import SQLITE_FILE_PATH

Base = declarative_base()


class User(Base):
    __tablename__ = "member"
    user_id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)
    wallet = Column(String)
    income = Column(Float)
    balance = Column(Float)
    withdrawn = Column(Float)
    deposited = Column(Float)
    blocked = Column(Boolean)
    last_buy_time = Column(Float)
    last_withdraw_time = Column(Float)
    total_slots = Column(Integer, default=0)
    bonus = Column(Integer, default=0)
    claimed_daily_bonus = Column(Boolean, default=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    referred_by = Column(Integer, ForeignKey("member.user_id"))
    slots = relationship("Slot", backref=backref("member"))
    referrals = relationship("User")

    def __repr__(self):
        return f'''Name: {self.name}
Email: {self.email}
Wallet: {self.wallet}
Income: {self.income:.2f} TRX
Balance: {self.balance:.2f} TRX
Withdrawn: {self.withdrawn:.2f} TRX
Deposited: {self.deposited} TRX                  
Slots: {self.total_slots}
Bonus: {self.bonus}
Referrals: {len(self.referrals)}
Referred_by: {self.referred_by}
'''


class Slot(Base):
    __tablename__ = "slot"
    slot_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("member.user_id"))

    def __repr__(self):
        return f"{self.slot_id}"

    def parent(self):
        return round(self.slot_id / 3)

    def children(self):
        middle_child = self.slot_id * 3
        return middle_child - 1, middle_child, middle_child + 1

    def level(self):
        level = 1
        last_slot = 1
        while last_slot < self.slot_id:
            last_slot = last_slot + 3 ** level
            level += 1
        return level


class Transaction(Base):
    __tablename__ = "transactions"
    tx_id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("member.user_id"))

class Tasks(Base):
    __tablename__ = "tasks"
    task_code = Column(String, primary_key=True)
    task_name = Column(String)
    latest = Column(Boolean, default=True)

engine = create_engine(f"sqlite:///{SQLITE_FILE_PATH}")
Session = sessionmaker(bind=engine)


def create_tables():
    Base.metadata.create_all(engine)


def drop_tables():
    Base.metadata.drop_all(engine)



class Matrix:
    def __init__(self):
        self.session = Session()

    def commit(self):
        self.session.commit()

    def get_users(self):
        return self.session.query(User).order_by(User.name).all()

    def get_user(self, user_id) -> User:
        return self.session.query(User).filter(User.user_id == user_id).one_or_none()

    def get_top_referred(self) -> User:
        user_ids = self.session.query(User.referred_by).group_by(User.referred_by).order_by(
            func.count(User.referred_by).desc()).limit(11).all()
        if user_ids:
            return user_ids
        else:
            return []

    def get_slot(self, slot_id) -> Slot:
        return self.session.query(Slot).filter(Slot.slot_id == slot_id).one_or_none()

    def get_total_slots(self) -> int:
        return self.session.query(Slot).count()

    def get_total_users(self) -> int:
        return self.session.query(User).count()

    def add_slot(self, user_id) -> Slot:
        slot = Slot(user_id=user_id)

        # Get the user
        user = (
            self.session.query(User)
                .filter(User.user_id == user_id)
                .one_or_none()
        )
        # Initialize the slot relationships
        slot.user = user
        user.total_slots += 1
        self.session.add(slot)

        self.session.commit()

        return slot

    def add_user(self, user_id, referred_by, bonus=0) -> User:
        # Get the user
        user = (
            self.session.query(User)
                .filter(User.user_id == user_id)
                .one_or_none()
        )
        # Do we need to create the user?
        if user is None:
            user = User(user_id=user_id, income=0, balance=bonus, withdrawn=0, deposited=0, referred_by=referred_by,
                        last_buy_time=0, last_withdraw_time=0, bonus=bonus)
            self.session.add(user)

            # Commit to the database
            self.session.commit()
        return user

    def is_duplicate_tx(self, tx_id, user_id):
        res = self.session.query(Transaction).filter(Transaction.tx_id == tx_id).one_or_none()
        if res is None:
            tx = Transaction(tx_id=tx_id, user_id=user_id)
            self.session.add(tx)
            self.session.commit()
            return False
        else:
            return True

    def get_zero_income_users(self):
        zero_users = []
        users = self.session.query(User).filter(User.income == 0).all()
        for user in users:
            if len(user.slots) > 0:
                zero_users.append(user)
        print(zero_users)
        return zero_users
    
    def update_task(self, task_code, task_name) -> Tasks:
        task = Tasks(task_name=task_name, task_code=task_code)
        self.session.add(task)
        
        self.session.commit()
    
    def clear_latest(self):
        results = self.session.query(Tasks).filter(Tasks.latest == True).all()
        for result in results:
            result.latest = False
        self.session.commit()

    def check_task_code(self, task_code):
        task_code = self.session.query(Tasks).filter(Tasks.task_code == task_code, Tasks.latest == True).one_or_none()
        return task_code

    def return_task_code(self):
        task = self.session.query(Tasks).filter(Tasks.latest == True).one_or_none()
        if task is not None:
            return task.task_code
        else:
            return "No task active."
