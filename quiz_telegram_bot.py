import html
import requests
import random
import os
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler,filters, CallbackQueryHandler

api_key = os.getenv("API_KEY")

class Fetch:
    def __init__(self, url: str, response:str, update: Update):
        self.url = url
        self.response = response
        self.update = update

    def fetch_response(self):
        try:
            response = requests.get(self.url, timeout=10)
            data = response.json()
            return data[self.response]
        except requests.RequestException:
            self.update.message.reply_text('Error fetching the data')
            return None

CHOOSE_CATEGORY = 1
SET_DIFFICULTY = 2
QUESTION_TYPE = 3
GAME_START = 4

class UserChoice:
    def __init__(self):
        self.category = ''
        self.difficulty = ''
        self.type = ''
        self.question_type = ['multiple', 'boolean']
        self.difficulty_type = ['easy', 'medium', 'hard']

    # Fetching Category

    def fetch_category(self, update: Update):
        fetch_category = Fetch('https://opentdb.com/api_category.php', 'trivia_categories', update)
        return fetch_category.fetch_response()
    # ----------------------------
    
    # Showing Category and Selecting user Choice
    async def show_categories(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        category = self.fetch_category(update)
        context.user_data['categories'] = category

        keyboard = [[InlineKeyboardButton(cat['name'], callback_data=str(i))] for i, cat in enumerate(category)]


        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Choose a category", reply_markup=reply_markup)

        return CHOOSE_CATEGORY
    # -------------------------
    

    # Handling Category selection
    async def handle_category_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        category_answer = query.data


        try:
            category = context.user_data.get('categories')
            selected_index = int(category_answer)

            if not (0<= selected_index < len(category)):
                await update.callback_query.message.reply_text("Invalid category number.")
                return CHOOSE_CATEGORY
            
            selected_category = category[selected_index]
            context.user_data['category_id'] = selected_category['id']
            context.user_data['category_name'] = selected_category['name']
            self.category = selected_category['id']
                
            await update.callback_query.message.reply_text(f"You chose: {selected_category['name']}")
            return await self.ask_difficulty(update, context)
            
        except ValueError:
            await update.callback_query.message.reply_text('unexpected error has occured')
            return CHOOSE_CATEGORY
        
    #------------------------- 


    # Setting Difficulty
    async def ask_difficulty(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        difficulty_type = ['easy', 'medium', 'hard']
        message = "Select a difficulty:\n"
        keyboard = [
            [InlineKeyboardButton(diff, callback_data=str(i)) for i, diff in enumerate(difficulty_type)],
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text(message, reply_markup=reply_markup)

        return SET_DIFFICULTY
    # -------------------------
    
    async def handle_difficulty(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_input = int(query.data)

        try:
            if 0 <= user_input < len(self.difficulty_type):
                chosen = self.difficulty_type[user_input]

                context.user_data['difficulty'] = chosen
                await update.callback_query.message.reply_text(f'You chose: {chosen}')
                self.difficulty = chosen

                return await self.ask_question_type(update, context)
            else:
                await update.callback_query.message.reply_text('Invalid selection. Please enter 1, 2, or 3.')
                return SET_DIFFICULTY
            
        except ValueError:
            await update.callback_query.message.reply_text('Please enter a valid number.')
            return SET_DIFFICULTY

    # -------------------------------

    # Setting Question Type
    async def ask_question_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        
        keyboard = [
            [InlineKeyboardButton(qt, callback_data=str(i))for i, qt in enumerate(self.question_type)]
        ]

        message = "Select question type\n"
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text(message, reply_markup=reply_markup)
        return QUESTION_TYPE
    
    async def handle_question_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_input = update.message.text.strip()
        try:
            index = int(user_input) - 1
            if 0 <= index < len(self.question_type):
                chosen = self.question_type[index]
                context.user_data['question_type'] = chosen

                self.type = chosen
                await update.message.reply_text(f'You chose: {chosen}')

                game = Game()
                game.category = self.category
                game.difficulty = self.difficulty
                game.type = self.type

                return await game.handle_game(update=update, context=context)
            
            else:
                await update.message.reply_text('Please choose 1 or 2 ')
                return QUESTION_TYPE
        except ValueError:
            await update.message.reply_text('Invalid Input. ')
            return QUESTION_TYPE


class Game(UserChoice):
    def __init__(self):
        super().__init__()
        self.score = 0

    # Fetch Questions 
    def fetch_questions(self, update: Update):
        questions = Fetch(f'https://opentdb.com/api.php?amount=10&category={self.category}&difficulty={self.difficulty}&type={self.type}', 'results', update)
        return questions.fetch_response()
    # ---------------------------------

    async def handle_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        result = self.fetch_questions(update)
        
       
        if not result:
            await update.message.reply_text("Sorry, couldn't fetch questions. refetching...")
            return ConversationHandler.END
        

        context.user_data['questions'] = result
        context.user_data['current'] = 0
        context.user_data['score'] = 0       
        
        return await self.ask_question(update, context)
    
    async def ask_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        index = context.user_data['current']
        questions = context.user_data['questions']

        
        if index >= len(questions):
            await update.callback_query.message.reply_text(f"Game Over! Your score: {context.user_data['score']}")
            return ConversationHandler.entry_points
        
        q = questions[index]
        correct_answer = html.unescape(q['correct_answer'])
        options = q['incorrect_answers'] + [correct_answer]
        random.shuffle(options)

        context.user_data['correct'] = correct_answer
        context.user_data['options'] = options

        if context.user_data['question_type'] == 'multiple':
            keyboard = [
                [
                    InlineKeyboardButton(("A"),callback_data= 0),
                    InlineKeyboardButton(("B"),callback_data= 1)
                ],

                [
                    InlineKeyboardButton(("C"),callback_data= 2),
                    InlineKeyboardButton(("D"),callback_data= 3)
                ],
            ]
        else:
            keyboard = [
                [InlineKeyboardButton(option, callback_data=str(i)) for i, option in enumerate(options)]
            ]


        choose_letter = ['a', 'b', 'c', 'd']
        msg = f'{index + 1 }) {html.unescape(q['question'])}\n'+'\n'+'\n'.join(f'{choose_letter[i]}. {option}' for i, option in enumerate(options))

        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.answer()  # optional, for better UX
            await update.callback_query.message.reply_text(msg, reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, reply_markup=reply_markup)


        return GAME_START
    


    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        choice = {
            'a': 0,
            'b': 1,
            'c': 2,
            'd': 3
        }

        user_input = query.data

        options = context.user_data['options']
        correct_answer = context.user_data['correct']

        user_choice = options[int(user_input)]

        if user_choice.lower() == correct_answer.lower():
            context.user_data['score'] += 1
            await update.callback_query.message.reply_text('Correct!')
        else: 
            await update.callback_query.message.reply_text(f'Wrong! the answe is {correct_answer}')

        context.user_data['current'] += 1
        return await self.ask_question(update, context)
    
        




async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('hello ' + update.effective_user.first_name)

async def go(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('You clicked go')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('You clicked Start')

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Game stooped. use /start to play again")
    return ConversationHandler.END


async def set_commands(applicaton: Application):
    await applicaton.bot.set_my_commands([
        BotCommand('start', 'starts the bot'),
        BotCommand('stop', 'stops the bot'),
        BotCommand('go', 'Triggers go'),
        BotCommand('hello', 'say hello')
    ])





app = ApplicationBuilder().token(api_key).post_init(set_commands).build()

CHOOSE_CATEGORY, SET_DIFFICULTY, QUESTION_TYPE, GAME_START = range(4)

user_choice = Game()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', user_choice.show_categories),
    ],
    states={
        CHOOSE_CATEGORY: [CallbackQueryHandler(user_choice.handle_category_selection)],
        SET_DIFFICULTY: [CallbackQueryHandler(user_choice.handle_difficulty)],
        QUESTION_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, user_choice.handle_question_type)],
        GAME_START: [CallbackQueryHandler(user_choice.handle_answer)],
    },
    fallbacks=[
        CommandHandler('stop', stop)
    ]
)

app.add_handler(CommandHandler('hello', hello))
app.add_handler(CommandHandler('go', go))
app.add_handler(conv_handler)

app.run_polling()