from telegram.ext import Application, CommandHandler, ChatMemberHandler, MessageHandler, ContextTypes, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Message, Animation
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

        self.app.add_handler(CommandHandler("stats", self.get_stats_command))
        self.app.add_handler(CallbackQueryHandler(self.get_stats_buttons))

        self.app.add_handler(CommandHandler('stats_gif', self.get_stats_for_gif_command))
        self.app.add_handler(CommandHandler('stats_sticker', self.get_stats_for_sticker_command))

        self.app.add_handler(ChatMemberHandler(self.process_new_group_members, Update.chat_member))
        self.app.add_handler(MessageHandler(TEXT | VIA_BOT, self.process_text))
        self.app.add_handler(MessageHandler(ANIMATION, self.process_gif))
        self.app.add_handler(MessageHandler(Sticker.ALL, self.process_sticker))
        self.app.add_handler(MessageHandler(PHOTO | VIDEO | Document.ALL, self.process_photo_video_document))


        #TODO: write command to show stats for group
        #TODO: write command to show stats for user
        #TODO: write command to show stats for particular word(s)
        #TODO: write command to show tracked users
        #TODO: add setting to show first names while getting statistics instead of nicknames
        #TODO: add setting to count characters
        #TODO: add achievements (obtained by request/by stats/everyday/right after achievement (?)/check each hour)
        #TODO: add statistics for number of voice messages
        #TODO: save queries to get stats as functions in MySQL
        #TODO: add 1 minute limit between requests to prevent time out
        #TODO: choose how much top words to show
        #TODO: count replies


    def start(self):
        print(datetime.now(), 'Running bot')
        self.app.run_polling(poll_interval=int(os.getenv('words_stats_bot_update_interval')))


    def split_message(self, message: str) -> list:
        # lower message and remove all links
        message_no_url = re.sub(self.pattern_url, '', message.lower())
        # split into words
        return re.findall(self.pattern_word, message_no_url)


    # region database settings and adding messages
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

    def delete_message(self, message_id: int):
        try:
            cursor = self.db.cursor()
            cursor.execute("DELETE IGNORE FROM Messages WHERE MessageID=%s;", (message_id,))
            self.db.commit()
            return True
        except Exception as e:
            print(datetime.now(), f'Cannot delete message {message_id}: {e}')
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

    def add_message_with_gif(self, message_id: int, date: datetime, chat_id: int, user_id: int, gif_unique_id: str, gif_id: str, duration: int, height: int, width: int) -> bool:
        if (not self.add_message(message_id, date, chat_id, user_id)):
            return False
        try:
            cursor = self.db.cursor()
            # insert message
            cursor.execute("INSERT IGNORE INTO Gifs(GifUniqueID,MessageID,GifID,Duration,Height,Width)VALUE(%s,%s,%s,%s,%s,%s);", (gif_unique_id, message_id, gif_id, duration, height, width))
            self.db.commit()
            return True
        except Exception as e:
            print(datetime.now(), f'Cannot add message {message_id} on {date} for chat {chat_id} for user {user_id} with gif {gif_unique_id}: {e}')
            return False

    def add_message_with_sticker(self, message_id: int, date: datetime, chat_id: int, user_id: int, sticker_unique_id: str, sticker_set_name: str) -> bool:
        if (not self.add_message(message_id, date, chat_id, user_id)):
            return False
        try:
            cursor = self.db.cursor()
            # insert message
            cursor.execute("INSERT IGNORE INTO Stickers(StickerUniqueID,MessageID,StickerSetName)VALUE(%s,%s,%s);", (sticker_unique_id, message_id, sticker_set_name))
            self.db.commit()
            return True
        except Exception as e:
            print(datetime.now(), f'Cannot add message {message_id} on {date} for chat {chat_id} for user {user_id} with sticker {sticker_unique_id}: {e}')
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

    def get_user_num(self, chat_id: int):
        try:
            cursor = self.db.cursor()
            cursor.execute('SELECT COUNT(DISTINCT UserID) FROM Messages WHERE ChatID=%s;', (chat_id,))
            result = cursor.fetchone()
            return result[0]
        except Exception as e:
            print(datetime.now(), f'Cannot get users num for chat {chat_id}: {e}')
            return None

    def get_users(self, chat_id: int, num: int, offset: int):
        try:
            cursor = self.db.cursor()
            cursor.execute('SELECT u.UserID,u.Nickname,u.FirstName FROM Users u JOIN(SELECT DISTINCT UserID FROM Messages WHERE ChatID=%s) t ON t.UserId=u.UserID ORDER BY u.FirstName DESC LIMIT %s OFFSET %s;', (chat_id,num, offset))
            result = cursor.fetchall()
            return result
        except Exception as e:
            print(datetime.now(), f'Cannot get {num} users for chat {chat_id} with offset {offset}: {e}')
            return None
    # endregion

    # region statistics
    def get_stats_for_gif(self, chat_id: int):
        try:
            cursor = self.db.cursor()
            cursor.execute('SELECT GifCount,GifUniqueID,GifID,Duration,Height,Width FROM(SELECT g.*,ROW_NUMBER()OVER(PARTITION BY GifUniqueID ORDER BY MessageID) AS row_num,GifCount FROM Gifs g INNER JOIN(SELECT GifUniqueID,COUNT(*) AS GifCount FROM Gifs g JOIN Messages m ON g.MessageID=m.MessageID WHERE m.ChatID=%s GROUP BY GifUniqueID ORDER BY GifCount DESC LIMIT 5)TopGifs ON G.GifUniqueID=TopGifs.GifUniqueID)g WHERE g.row_num=1 ORDER BY GifCount DESC;', (chat_id,))
            result = cursor.fetchall()
            return result
        except Exception as e:
            print(datetime.now(), f'Cannot get stats for gifs for chat {chat_id}: {e}')
            return None

    def get_stats_for_sticker(self, chat_id: int):
        try:
            cursor = self.db.cursor()
            cursor.execute('SELECT StickerUniqueID,StickerSetName,COUNT(*) FROM Stickers JOIN Messages ON Stickers.MessageID=Messages.MessageID WHERE Messages.ChatID=%s GROUP BY StickerUniqueID,StickerSetName ORDER BY 3 DESC LIMIT 5;', (chat_id,))
            result = cursor.fetchall()
            return result
        except Exception as e:
            print(datetime.now(), f'Cannot get stats for stickers for chat {chat_id}: {e}')
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

    def validate_settings(self, message: Message) -> bool:
        # get settings
        settings = self.get_settings(message.chat_id)
        if (settings is None):
            return False
        settings = settings[0]

        # ignore commands
        if (message.text and message.text.startswith('/')):
            return False

        # check if ignore photo captions
        if (settings[0] and len(message.photo) > 0):
            return False
        
        # check if ignore video captions
        if (settings[1] and message.video):
            return False
        
        # check if ignore video captions
        if (settings[2] and message.document):
            return False
        
        # check if ignore gifs
        if (settings[3] and message.animation):
            return False
        
        # check if ignore stickers
        if (settings[4] and message.sticker):
            return False

        # check if ignore channel posts
        if (settings[5] and message.forward_from_chat):
            return False

        return True

    async def process_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if (update.message):
            if (not self.validate_settings(update.message)):
                return

            # try adding user
            self.add_user(update.message.from_user.id, update.message.from_user.username, update.message.from_user.first_name)

            # save words in message to database
            self.add_message_with_words(update.message.id, update.message.date, update.message.chat_id, update.message.from_user.id, update.message.text)
        elif (update.edited_message):
            if (not self.validate_settings(update.edited_message)):
                return

            # try adding user
            self.add_user(update.edited_message.from_user.id, update.edited_message.from_user.username, update.edited_message.from_user.first_name)
            
            # delete message
            self.delete_message(update.edited_message.message_id)
            # save words in message to database
            self.add_message_with_words(update.edited_message.message_id, update.edited_message.edit_date, update.edited_message.chat_id, update.edited_message.from_user.id, update.edited_message.text)

    async def process_photo_video_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if (not self.validate_settings(update.message)):
            return

        # try adding user
        self.add_user(update.message.from_user.id, update.message.from_user.username, update.message.from_user.first_name)

        # save words in message to database
        self.add_message_with_words(update.message.id, update.message.date, update.message.chat_id, update.message.from_user.id, update.message.caption)

    async def process_gif(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if (not self.validate_settings(update.message)):
            return

        # try adding user
        self.add_user(update.message.from_user.id, update.message.from_user.username, update.message.from_user.first_name)

        # save gif in message to database
        self.add_message_with_gif(update.message.id, update.message.date, update.message.chat_id, update.message.from_user.id, update.message.animation.file_unique_id,
                                  update.message.animation.file_id, update.message.animation.duration, update.message.animation.height, update.message.animation.width)

        # await self.download_gif(update.message.animation.file_id, update.message.animation.file_unique_id)

    async def process_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if (not self.validate_settings(update.message)):
            return

        # try adding user
        self.add_user(update.message.from_user.id, update.message.from_user.username, update.message.from_user.first_name)

        # save words in message to database
        self.add_message_with_sticker(update.message.id, update.message.date, update.message.chat_id, update.message.from_user.id, update.message.sticker.file_unique_id, update.message.sticker.set_name)
    # endregion

    # region stat commands
    async def get_stats_for_gif_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        gifs = self.get_stats_for_gif(update.message.chat_id)
        if gifs is None:
            await update.message.reply_text('No gifs sent')
        else:
            message = await update.message.reply_text('Top 5 gifs:')
            for gif in gifs:
                gif_id = await self.app.bot.get_file(gif[2])
                anim = Animation(file_unique_id=gif[1], file_id=gif_id.file_id, duration=gif[3], height=gif[4], width=gif[5])
                await message.reply_animation(anim, caption=f'Used {gif[0]} times')

    async def get_stats_for_sticker_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        stickers = self.get_stats_for_sticker(update.message.chat_id)
        if stickers is None:
            await update.message.reply_text('No stickers sent')
        else:
            message = await update.message.reply_text('Top 5 stickers:\n\n' + '\n'.join([f'Used {stk[2]} times' for stk in stickers]))
            for sticker in stickers:
                sticker_set = await self.app.bot.get_sticker_set(sticker[1])
                real_sticker = [stk for stk in sticker_set.stickers if stk.file_unique_id == sticker[0]][0]
                await message.reply_sticker(real_sticker)

    def split_stats(self, s: str) -> list:
        return s.split('|')

    def get_desc_type(self, type: str) -> str:
        return type

    def get_desc_time(self, time: str) -> str:
        #TODO: prettify time
        return time


    async def get_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        keyboard = [
            [
                InlineKeyboardButton("Words", callback_data="words"),
                InlineKeyboardButton("Gifs", callback_data="gifs"),
                InlineKeyboardButton("Stickers", callback_data="stickers")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Get stats for:", reply_markup=reply_markup)

    async def get_stats_buttons(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        response = query.data
        responses = self.split_stats(response)

        if len(responses) >= 1: # if type chosen
            type = responses[0]
            if len(responses) >= 2: # if time chosen
                time = responses[1]
                if len(responses) >= 3: # if entity chosen
                    user = responses[2]
                    if user == 'all': # if all users chosen
                        await self.show_statistics(update, type, time, None)
                    elif user.startswith('user_'): # if particular user chosen
                        await self.show_statistics(update, type, time, int(user[5:])) # remove 'user_' to extract id
                    else:
                        await self.show_buttons_for_user_selection(update, type, time, user)
                else:
                    await self.show_buttons_for_entity_selection(update, type, time)
            else:
                await self.show_buttons_for_time_selection(update, type)

    async def show_buttons_for_time_selection(self, update: Update, type: str) -> None:
        #TODO: add buttons back
        state_time = [
            [InlineKeyboardButton("All time", callback_data=type + "|all")],
            [InlineKeyboardButton("Last year", callback_data=type + "|last-year")],
            [InlineKeyboardButton("Last month", callback_data=type + "|last-month")],
            [InlineKeyboardButton("Last week", callback_data=type + "|last-week")],
            [InlineKeyboardButton("Last day", callback_data=type + "|last-day")]
        ]
        await update.callback_query.edit_message_text(text=f"Get top {self.get_desc_type(type)} for:", reply_markup=InlineKeyboardMarkup(state_time))

    async def show_buttons_for_entity_selection(self, update: Update, type: str, time: str) -> None:
        #TODO: add buttons back
        state_entity = [
            [InlineKeyboardButton("All", callback_data=f"{type}|{time}|all")],
            [InlineKeyboardButton("User", callback_data=f"{type}|{time}|page_0")]
        ]
        await update.callback_query.edit_message_text(text=f"Get top {self.get_desc_type(type)} for {self.get_desc_time(time)} for:", reply_markup=InlineKeyboardMarkup(state_entity))

    async def show_buttons_for_user_selection(self, update: Update, type: str, time: str, user: str) -> None:
        users_per_page = 10
        page = int(user.split('_')[1])
        offset = page * users_per_page

        users = self.get_users(update.callback_query.message.chat_id, users_per_page, offset)
        users_num = self.get_user_num(update.callback_query.message.chat_id)

        #TODO: add buttons back
        state_user = [
            [InlineKeyboardButton(user[2], callback_data=f"{type}|{time}|user_{user[0]}")] for user in users
        ]

        state_user_pages = []
        if page != 0:
            state_user_pages.append(InlineKeyboardButton("<", callback_data=f"{type}|{time}|page_{page - 1}"))
        if offset + users_per_page < users_num:
            state_user_pages.append(InlineKeyboardButton(">", callback_data=f"{type}|{time}|page_{page + 1}"))

        if len(state_user_pages) > 0:
            state_user.append(state_user_pages)
        await update.callback_query.edit_message_text(text=f"Get top {self.get_desc_type(type)} for {self.get_desc_time(time)} for:", reply_markup=InlineKeyboardMarkup(state_user))

    async def show_statistics(self, update: Update, type: str, time: str, user) -> None:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(f"type {type}, time {time}, user {user}")
    # endregion



if __name__ == '__main__':
    bot = Bot()
    bot.start()
