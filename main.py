from telegram.ext import Application, CommandHandler, ChatMemberHandler, MessageHandler, ContextTypes
from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext.filters import TEXT, PHOTO, VIDEO, Document, ANIMATION, Sticker, VIA_BOT
import os
import mysql.connector
from mysql.connector import MySQLConnection
from dotenv import load_dotenv
from datetime import datetime, timezone
import re


load_dotenv()

class Bot:
    db: MySQLConnection
    app: Application
    admin_id: int
    bot_username: str

    pattern_url = re.compile(r"https?://\S+")
    pattern_word = re.compile(r"[-'\d]*[^\W\d]+[-'\d]*")

    def __init__(self):
        print(datetime.now(), 'Starting bot')

        self.admin_id = int(os.getenv('words_stats_bot_admin_id'))
        self.bot_username = os.getenv('words_stats_bot_username')

        self.db = mysql.connector.connect(
                host=os.getenv('words_stats_bot_mysql_database_host'),
                port=int(os.getenv('words_stats_bot_mysql_database_port')),
                database=os.getenv('words_stats_bot_mysql_database'),
                user=os.getenv('words_stats_bot_mysql_username'),
                password=os.getenv('words_stats_bot_mysql_password')
            )

        self.app = Application.builder().token(os.getenv('words_stats_bot_token')).build()

        self.app.add_error_handler(self.error)
        self.app.add_handler(CommandHandler('start', self.start_command))
        self.app.add_handler(CommandHandler('help', self.help_command))
        self.app.add_handler(CommandHandler('shutdown', self.shutdown_command))
        self.app.add_handler(ChatMemberHandler(self.process_new_group_members, Update.chat_member))
        self.app.add_handler(MessageHandler(TEXT | VIA_BOT, self.process_text))
        self.app.add_handler(MessageHandler(ANIMATION, self.process_gif))
        self.app.add_handler(MessageHandler(Sticker.ALL, self.process_sticker))
        self.app.add_handler(MessageHandler(PHOTO | VIDEO | Document.ALL, self.process_photo_video_document))
        
        
        #TODO: write command to show stats for group
        #TODO: write command to show stats for user
        #TODO: write command to show stats for particular word(s)
        #TODO: write command to show tracked users
        #TODO: write command to remove users from tracking
        #TODO: add setting to show first names while getting statistics instead of nicknames
        #TODO: add setting to count characters
        #TODO: add achievements (obtained by request/by stats/everyday/right after achievement (?)/check each hour)

        #TODO: remove deleted messages

        #TODO: add support to count unique gifs - https://docs.python-telegram-bot.org/en/stable/telegram.animation.html#telegram.Animation
        #TODO: add support to count unique stickers - https://docs.python-telegram-bot.org/en/stable/telegram.message.html#telegram.Message.sticker


    def start(self):
        print(datetime.now(), 'Running bot')
        self.app.run_polling(poll_interval=int(os.getenv('words_stats_bot_update_interval')))


    def split_message(self, message: str) -> list:
        # lower message and remove all links
        message_no_url = re.sub(self.pattern_url, '', message.lower())
        # split into words
        return re.findall(self.pattern_word, message_no_url)

    # region database
    def create_settings(self, chat_id: int):
        try:
            cursor = self.db.cursor()
            cursor.execute("INSERT IGNORE INTO Settings(ChatID,IgnoreTextFromPhoto,IgnoreTextFromVideo,IgnoreTextFromDocument,IgnoreGif,IgnoreStickers,IgnoreChannelPosts)VALUE(%s,0,0,0,0,0,1);", (chat_id,))
            self.db.commit()
            print(datetime.now(), f'Added to chat {chat_id}')
            return True
        except Exception as e:
            print(datetime.now(), f'Cannot create settings for chat {chat_id}: {e}')
            return False

    def delete_settings(self, chat_id: int):
        try:
            cursor = self.db.cursor()
            cursor.execute("DELETE IGNORE FROM Settings WHERE ChatID=%s;", (chat_id,))
            self.db.commit()
            print(datetime.now(), f'Deleted from chat {chat_id}')
            return True
        except Exception as e:
            print(datetime.now(), f'Cannot delete settings for chat {chat_id}: {e}')
            return False

    def add_user(self, user_id: int, nickname: str, first_name: str) -> bool:
        try:
            cursor = self.db.cursor()
            cursor.execute("INSERT IGNORE INTO Users(UserID,Nickname,FirstName)VALUE(%s,%s,%s);", (user_id, nickname, first_name))
            self.db.commit()
            return True
        except Exception as e:
            print(datetime.now(), f'Cannot add user {user_id} with nickname {nickname} and first name {first_name}: {e}')
            return False

    def add_words(self, words: list) -> bool:
        try:
            cursor = self.db.cursor()
            values = ','.join([f"({hash(word)},'{word}')" for word in words])
            cursor.execute(f"INSERT INTO Words(WordID,Word)VALUES{values} ON DUPLICATE KEY UPDATE WordID=WordID;")
            self.db.commit()
            return True
        except Exception as e:
            print(datetime.now(), f'Cannot add words {words}: {e}')
            return False

    def add_message(self, message_id: int, date: datetime, chat_id: int, user_id: int) -> bool:
        try:
            cursor = self.db.cursor()
            # insert message
            cursor.execute("INSERT INTO Messages(MessageID,Date,ChatID,UserID)VALUE(%s,%s,%s,%s);", (message_id, date, chat_id, user_id))
            self.db.commit()
            return True
        except Exception as e:
            print(datetime.now(), f'Cannot add message on {date} for chat {chat_id} for user {user_id}: {e}')
            return False

    def add_message_with_words(self, message_id: int, date: datetime, chat_id: int, user_id: int, message: str) -> bool:
        # split message to words
        words = self.split_message(message)
        if (len(words) == 0):
            return False

        if (not self.add_message(message_id, date, chat_id, user_id)):
            return False

        # try adding words to database
        self.add_words(words)

        # add words to message
        try:
            cursor = self.db.cursor()
            values = ','.join([f'({message_id},{hash(word)})' for word in words])
            cursor.execute(f"INSERT INTO Messages_Words(MessageID,WordID)VALUES{values};")
            self.db.commit()
            return True
        except Exception as e:
            print(datetime.now(), f'Cannot add message {message_id} on {date} for chat {chat_id}, user {user_id} and words {words}: {e}')
            return False

    def add_message_with_gif(self, message_id: int, date: datetime, chat_id: int, user_id: int, gif_id: str, gif_unique_id: str) -> bool:
        if (not self.add_message(message_id, date, chat_id, user_id)):
            return False
        try:
            cursor = self.db.cursor()
            # insert message
            cursor.execute("INSERT IGNORE INTO Gifs(GifUniqueID,GifID,MessageID)VALUE(%s,%s,%s);", (gif_unique_id, gif_id, message_id))
            self.db.commit()
            return True
        except Exception as e:
            print(datetime.now(), f'Cannot add message {message_id} on {date} for chat {chat_id} for user {user_id} with gif {gif_id}: {e}')
            return False

    def add_message_with_sticker(self, message_id: int, date: datetime, chat_id: int, user_id: int, sticker_id: str, sticker_unique_id: str) -> bool:
        if (not self.add_message(message_id, date, chat_id, user_id)):
            return False
        try:
            cursor = self.db.cursor()
            # insert message
            cursor.execute("INSERT IGNORE INTO Stickers(StickerUniqueID,StickerID,MessageID)VALUE(%s,%s,%s);", (sticker_unique_id, sticker_id, message_id))
            self.db.commit()
            return True
        except Exception as e:
            print(datetime.now(), f'Cannot add message {message_id} on {date} for chat {chat_id} for user {user_id} with sticker {sticker_id}: {e}')
            return False

    def get_settings(self, chat_id: int):
        try:
            cursor = self.db.cursor()
            cursor.execute('SELECT IgnoreTextFromPhoto,IgnoreTextFromVideo,IgnoreTextFromDocument,IgnoreGif,IgnoreStickers,IgnoreChannelPosts FROM Settings WHERE ChatID=%s;', (chat_id,))
            result = cursor.fetchall()
            return result
        except Exception as e:
            print(datetime.now(), f'Cannot get settings for chat {chat_id}: {e}')
            return None
    # endregion


    # region default commands
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text('Hello')


    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text('Help')


    async def error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        print(datetime.now(), f'Update {update} caused error {context.error}')
    # endregion


    # region commands
    async def shutdown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        a = datetime.now(timezone.utc) - update.message.date
        if update.message.from_user.id == self.admin_id and a.total_seconds() / 60 < 1:
            await update.message.reply_text('Shutting down')
            print(datetime.now(), 'Shutting down')
            os.kill(os.getpid(), 15)

    async def process_new_group_members(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # get new user
        chat_member = update.chat_member if update.chat_member else update.my_chat_member
        # check if username of new user is bot and it 
        if self.bot_username == chat_member.new_chat_member.user.username:
            if chat_member.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR or chat_member.new_chat_member.status == ChatMemberStatus.MEMBER:
                self.create_settings(update._effective_chat.id)
            elif chat_member.new_chat_member.status == ChatMemberStatus.LEFT or chat_member.new_chat_member.status == ChatMemberStatus.BANNED:
                self.delete_settings(update._effective_chat.id)

    def validate_settings(self, update: Update) -> bool:
        # get settings
        settings = self.get_settings(update.message.chat_id)
        if (settings is None):
            return False
        settings = settings[0]

        # ignore commands
        if (update.message.text and update.message.text.startswith('/')):
            return False

        # check if ignore photo captions
        if (settings[0] and len(update.message.photo) > 0):
            return False
        
        # check if ignore video captions
        if (settings[1] and update.message.video):
            return False
        
        # check if ignore video captions
        if (settings[2] and update.message.document):
            return False
        
        # check if ignore gifs
        if (settings[3] and update.message.animation):
            return False
        
        # check if ignore stickers
        if (settings[4] and update.message.sticker):
            return False

        # check if ignore channel posts
        if (settings[5] and update.message.forward_from_chat):
            return False

        return True

    async def process_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if (not self.validate_settings(update)):
            return

        if (update.message):
            # try adding user
            self.add_user(update.message.from_user.id, update.message.from_user.username, update.message.from_user.first_name)

            # save words in message to database
            self.add_message_with_words(update.message.id, update.message.date, update.message.chat_id, update.message.from_user.id, update.message.text)
        elif (update.edited_message):
            pass

    async def process_photo_video_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if (not self.validate_settings(update)):
            return

        # try adding user
        self.add_user(update.message.from_user.id, update.message.from_user.username, update.message.from_user.first_name)

        # save words in message to database
        self.add_message_with_words(update.message.id, update.message.date, update.message.chat_id, update.message.from_user.id, update.message.caption)

    async def process_gif(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if (not self.validate_settings(update)):
            return

        # try adding user
        self.add_user(update.message.from_user.id, update.message.from_user.username, update.message.from_user.first_name)

        # save gif in message to database
        self.add_message_with_gif(update.message.id, update.message.date, update.message.chat_id, update.message.from_user.id, update.message.animation.file_id, update.message.animation.file_unique_id)

    async def process_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if (not self.validate_settings(update)):
            return

        # try adding user
        self.add_user(update.message.from_user.id, update.message.from_user.username, update.message.from_user.first_name)

        # save words in message to database
        self.add_message_with_sticker(update.message.id, update.message.date, update.message.chat_id, update.message.from_user.id, update.message.sticker.file_id, update.message.sticker.file_unique_id)
    # endregion


if __name__ == '__main__':
    bot = Bot()
    bot.start()

