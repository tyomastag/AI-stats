import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import sqlite3
from functools import partial
 
ASKING_NAME, ASKING_LEVEL, ASKING_RARITY = range(3)
 
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
 
logger = logging.getLogger(__name__)
 
TOKEN = "YOUR TOKEN"
 
def text_handler(update: Update, context: CallbackContext):
    update.message.reply_text("Я не понимаю эту команду. Пожалуйста, используйте /start для начала работы.")
 
 
def get_conn():
    return sqlite3.connect("catlets.db")
 
def create_table():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS catlets
                            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            name TEXT NOT NULL,
                            level INTEGER NOT NULL,
                            wins INTEGER NOT NULL,
                            losses INTEGER NOT NULL,
                            daily_wins INTEGER NOT NULL,
                            daily_losses INTEGER NOT NULL);''')
        conn.commit()
 
def start(update: Update, context: CallbackContext):
    update.message.reply_text('Привет! Я бот для учета статистики КАТлетов.')
    main_menu(update, context)
 
def main_menu(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🏆 Общая", callback_data='show_stats'),
         InlineKeyboardButton("🏆 Сегодня", callback_data='show_daily_stats')],  # добавьте эту кнопку
        [InlineKeyboardButton("❌ Закрыть день", callback_data='reset_daily_stats')],  # добавьте эту кнопку
        [InlineKeyboardButton("⚔️ Соревнования", callback_data='competitions')],
        [InlineKeyboardButton("🐱 КАТлеты", callback_data='catlets')],
    ]
 
    reply_markup = InlineKeyboardMarkup(keyboard)
 
    if update.message:
        update.message.reply_text('Выберите действие:', reply_markup=reply_markup)
    else:
        update.callback_query.message.reply_text('Выберите действие:', reply_markup=reply_markup)
 
def catlets_menu(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Добавить КАТлета", callback_data='add_catlet')],
        [InlineKeyboardButton("Удалить КАТлета", callback_data='delete_catlet')],
        [InlineKeyboardButton("Назад", callback_data='back_to_competitions')],
    ]
 
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.callback_query.message.reply_text('Выберите действие:', reply_markup=reply_markup)
 
def competitions_menu(update: Update, context: CallbackContext):
    keyboard = []
 
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM catlets WHERE user_id=?", (update.callback_query.from_user.id,))
        result = cursor.fetchall()
        sorted_result = sorted(result, key=lambda x: x[0])  # добавьте эту строку для сортировки
        for row in sorted_result:
            catlet_name = row[0]
            keyboard.append([
                InlineKeyboardButton(f"✅ {catlet_name}", callback_data=f"win_{catlet_name}"),
                InlineKeyboardButton(f"💢 {catlet_name}", callback_data=f"lose_{catlet_name}")
            ])
 
    keyboard.append([InlineKeyboardButton("⏪ Главный экран", callback_data='main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.callback_query.message.reply_text('Выберите действие:', reply_markup=reply_markup)
 
def menu_actions(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
 
    stats = None
 
    if query.data == 'reset_daily_stats':
        reset_daily_stats(update, context)
 
    if query.data == 'show_daily_stats':
        update_daily_stats(update, context)
 
    if query.data == 'main_menu':
        main_menu(update, context)
    elif query.data == 'show_stats':
        update_stats(update, context)
    elif query.data == 'competitions':
        competitions_menu(update, context)
    elif query.data == 'catlets':
        catlets_menu(update, context)
    elif query.data == 'delete_catlet':
        delete_catlet_menu(update, context)
    elif query.data.startswith("win_"):
        catlet_name = query.data.split("_", 1)[1]
        increment_wins(update, context, catlet_name)
    elif query.data.startswith("lose_"):
        catlet_name = query.data.split("_", 1)[1]
        increment_losses(update, context, catlet_name)
    elif query.data == 'back_to_competitions':
        competitions_menu(update, context)
    elif query.data == 'back_to_catlets':
        catlets_menu(update, context)
    elif query.data.startswith("delete_"):
        catlet_name = query.data.split("_", 1)[1]
        remove_catlet(update, context, catlet_name)
 
 
def update_stats(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    stats = []
    total_wins = 0
    total_losses = 0
 
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, wins, losses FROM catlets WHERE user_id=? ORDER BY name ASC", (user_id,))
        result = cursor.fetchall()
        for row in result:
            name, wins, losses = row
            winrate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
            stats.append(f"{name} (уровень {level}): {wins}W / {losses}L ({winrate:.2f}%)")
            total_wins += wins
            total_losses += losses
 
    total_winrate = (total_wins / (total_wins + total_losses)) * 100 if (total_wins + total_losses) > 0 else 0
    stats.append(f"\nОбщий винрейт: {total_winrate:.2f}%")
 
    keyboard = [
        [InlineKeyboardButton("⏪ Главный экран", callback_data='main_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
 
    if stats:
        query = update.callback_query
        query.answer()
        query.message.reply_text("\n".join(stats), reply_markup=reply_markup)
    else:
        query = update.callback_query
        query.answer()
        query.message.reply_text('Статистика отсутствует.', reply_markup=reply_markup)
 
def reset_daily_stats(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
 
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE catlets SET daily_wins=0, daily_losses=0 WHERE user_id=?", (user_id,))
        conn.commit()
 
    update.callback_query.message.reply_text("Статистика 'За сегодня' сброшена!")
    main_menu(update, context)
 
def update_daily_stats(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    stats = []
    total_daily_wins = 0
    total_daily_losses = 0
 
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, level, daily_wins, daily_losses FROM catlets WHERE user_id=? ORDER BY name ASC", (user_id,))
        result = cursor.fetchall()
        for row in result:
            name, daily_wins, daily_losses, level = row
            winrate = (daily_wins / (daily_wins + daily_losses)) * 100 if (daily_wins + daily_losses) > 0 else 0
            stats.append(f"{name} (уровень {level}): {daily_wins}W / {daily_losses}L ({winrate:.2f}%)")
            total_daily_wins += daily_wins
            total_daily_losses += daily_losses
 
    total_daily_winrate = (total_daily_wins / (total_daily_wins + total_daily_losses)) * 100 if (total_daily_wins + total_daily_losses) > 0 else 0
    stats.append(f"\nОбщий винрейт за сегодня: {total_daily_winrate:.2f}%")
 
    keyboard = [
        [InlineKeyboardButton("⏪ Главный экран", callback_data='main_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
 
    if stats:
        query = update.callback_query
        query.answer()
        query.message.reply_text("\n".join(stats), reply_markup=reply_markup)
    else:
        query = update.callback_query
        query.answer()
        query.message.reply_text('Статистика отсутствует.', reply_markup=reply_markup)
 
def ask_name(update: Update, context: CallbackContext):
    name = update.message.text
    context.user_data['name'] = name
    update.message.reply_text('Введите уровень катлета:')
    return ASKING_LEVEL
 
def ask_level(update: Update, context: CallbackContext):
    level = int(update.message.text)
    name = context.user_data['name']
    user_id = update.message.from_user.id
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO catlets(user_id, name, level, wins, losses, daily_wins, daily_losses) VALUES (?, ?, ?, 0, 0, 0, 0)",
                       (user_id, name, level))
        conn.commit()
    update.message.reply_text(f'Катлет {name} (уровень {level}) добавлен!')
    main_menu(update, context)
    return ConversationHandler.END
 
def delete_catlet_menu(update: Update, context: CallbackContext):
    keyboard = []
 
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM catlets WHERE user_id=?", (update.callback_query.from_user.id,))
        result = cursor.fetchall()
        for row in result:
            catlet_name = row[0]
            keyboard.append([InlineKeyboardButton(f"{catlet_name}", callback_data=f"delete_{catlet_name}")])
 
    keyboard.append([InlineKeyboardButton("Назад", callback_data='catlets')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.callback_query.message.reply_text('Выберите КАТлета для удаления:', reply_markup=reply_markup)
 
def remove_catlet(update: Update, context: CallbackContext, catlet_name: str):
    user_id = update.callback_query.from_user.id
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM catlets WHERE user_id=? AND name=?", (user_id, catlet_name))
        conn.commit()
 
    update.callback_query.message.reply_text(f"КАТлет '{catlet_name}' удален!")
    catlets_menu(update, context)
 
def increment_wins(update: Update, context: CallbackContext, catlet_name: str):
    user_id = update.callback_query.from_user.id
 
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE catlets SET wins=wins+1, daily_wins=daily_wins+1 WHERE user_id=? AND name=?", (user_id, catlet_name))
        conn.commit()

        # Запрашиваем уровень и статистику за день
        cursor.execute("SELECT level, daily_wins, daily_losses FROM catlets WHERE user_id=? AND name=?", (user_id, catlet_name))
        level, daily_wins, daily_losses = cursor.fetchone()
        winrate = (daily_wins / (daily_wins + daily_losses)) * 100 if (daily_wins + daily_losses) > 0 else 0
 
    update.callback_query.message.reply_text(f"✅ Победа за {catlet_name} (уровень {level})\nСтатистика за сегодня: {daily_wins}W / {daily_losses}L ({winrate:.2f}%)")
    competitions_menu(update, context)

def increment_losses(update: Update, context: CallbackContext, catlet_name: str):
    user_id = update.callback_query.from_user.id
 
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE catlets SET losses=losses+1, daily_losses=daily_losses+1 WHERE user_id=? AND name=?", (user_id, catlet_name))
        conn.commit()
 
        cursor.execute("SELECT level, daily_wins, daily_losses FROM catlets WHERE user_id=? AND name=?", (user_id, catlet_name))
        level, daily_wins, daily_losses = cursor.fetchone()
        winrate = (daily_wins / (daily_wins + daily_losses)) * 100 if (daily_wins + daily_losses) > 0 else 0
 
    update.callback_query.message.reply_text(f"💢 Поражение для {catlet_name} (уровень {level})\nСтатистика за сегодня: {daily_wins}W / {daily_losses}L ({winrate:.2f}%)")
    competitions_menu(update, context)
 
def add_catlet(update: Update, context: CallbackContext):
    update.callback_query.answer()
    update.callback_query.message.reply_text('Введите имя катлета:')
 
    return ASKING_NAME
 
def cancel_add_catlet(update: Update, context: CallbackContext):
    update.message.reply_text('Добавление катлета отменено.')
    main_menu(update, context)
    return ConversationHandler.END
 
conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(add_catlet, pattern='^add_catlet$')],
    states={
        ASKING_NAME: [MessageHandler(Filters.text & ~Filters.command, ask_name)],
        ASKING_LEVEL: [MessageHandler(Filters.regex(r'^\d+$'), ask_level)],
    },
    fallbacks=[CommandHandler('cancel_add_catlet', cancel_add_catlet)]
)
 
 
def main():
    create_table()
 
    updater = Updater(TOKEN, use_context=True)
 
    dp = updater.dispatcher
    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, text_handler))
    dp.add_handler(CallbackQueryHandler(menu_actions))
 
    updater.start_polling()
    updater.idle()
 
if __name__ == '__main__':
    main()
