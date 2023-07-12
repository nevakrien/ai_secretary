import openai 
import json

import os
from os.path import join,exists
from datetime import datetime

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import asyncio


async def send_message(bot,user_id,message):
    path=join('users',str(user_id))
    with open(join(path,'init.json'),'r') as f:
        user_info = json.load(f)
    chat_id=user_info['chat_id']
    
    t=datetime.now().strftime('%Y-%m-%d %H:%M:%S')+'.json'

    await bot.send_message(chat_id, message)
    with open(join(path,'send_messages',t), 'w') as f:
            json.dump({'chat_id': chat_id, 'message': message}, f)
    
    with open(join(path,'respond.json'), mode='r') as f:
        d = json.load(f)
    d['time'] = t  
    with open(join(path,'respond.json'), mode='w') as f:
        json.dump(d, f)

async def gpt_response(bot,user_id,message):
    await send_message(bot,user_id,message)

async def gpt_reminder(bot,user_id,message):
    await send_message(bot,user_id,message)

async def gpt_delayed_reminder(bot,user_id,message):
    await send_message(bot,user_id,'server error delayed response:\n'+message)


async def log_update(user_id,update):
    path=join('users',str(user_id))
    with open(join(path,'init.json'),'r') as f:
        user_info = json.load(f)
    chat_id=user_info['chat_id']
    
    t=datetime.now().strftime('%Y-%m-%d %H:%M:%S')+'.json'

    with open(join(path,'recived_messages',t), 'w') as f:
            json.dump({'chat_id': chat_id, 'message': update.message.text}, f) 

class WaitingToCheckOnUser:
    def __init__(self, bot,user_id, message, delay):
        self.bot = bot
        self.user_id=user_id
        self.message = message
        self.delay = delay

        self.path=join('users',str(self.user_id),'scedualed_respond.json')
        with open(self.path, 'w') as f:
            json.dump({'message': self.message,'delay': delay,'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f)
        self.task = asyncio.create_task(self.run())

    async def run(self):
        await asyncio.sleep(self.delay)
        await gpt_reminder(self.bot,self.user_id, self.message)
        os.remove(self.path)
        #with open(self.path, 'w') as f:
         #   json.dump({'chat_id': self.chat_id, 'message': self.message, 'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f)
        

    def cancel(self):
        if not self.task.done():
            self.task.cancel()
            os.remove(self.path)


async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """main response function"""
    user = update.effective_user
    path=join('users',str(user.id))

    try:
        user_threads[user.id].cancel()
    except KeyError:
        pass

    asyncio.create_task(log_update(user.id,update))
    response_text='got message'#await gpt_logic(update)
    await gpt_response(context.bot,user.id,response_text)

    w=WaitingToCheckOnUser(context.bot,user.id,'wait event trihggered',10)
    user_threads[user.id]=w

    #await w.task


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    path=join('users',str(user.id))
    os.makedirs(path,exist_ok=True)
    
    if(not exists(join(path,'init.json'))):
        print('new user joined!')
        with open(join(path,'init.json'),'w') as f:
            json.dump({'name':user.name,'time':datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f)
        
        os.makedirs(join(path,'send_messages'))
        os.makedirs(join(path,'recived_messages'))

        with open(join(path,'respond.json'),'w') as f:
            json.dump({'time':None,'delay':10}, f)
        
    # Update chat_id
    with open(join(path,'init.json'),'r') as f:
        user_info = json.load(f)
    user_info['chat_id'] = update.message.chat_id
    with open(join(path,'init.json'),'w') as f:
        json.dump(user_info, f)
    
    #await update.message.reply_html(rf"Hi {user.mention_html()}!", reply_markup=ForceReply(selective=True))
    await send_message(context.bot,user.id,rf"Hi {user.name}!")


async def initialize_tasks(application):
    print('looking for callbacks')
    bot=application.bot
    user_directories = [d for d in os.listdir('users') if os.path.isdir(join('users', d))]
    for user_dir in user_directories:
        path = join('users', user_dir)
        if exists(join(path, 'scedualed_respond.json')):
            with open(join(path, 'scedualed_respond.json'), 'r') as f:
                respond_info = json.load(f)
            time_sent = datetime.strptime(respond_info['time'], '%Y-%m-%d %H:%M:%S')
            time_now = datetime.now()
            if time_sent > time_now:
                delay = (time_sent - time_now).total_seconds()
                w = WaitingToCheckOnUser(bot, user_dir, respond_info['message'], delay)
                user_threads[int(user_dir)] = w
            else:
                asyncio.create_task(gpt_delayed_reminder(bot, user_dir, respond_info['message']))
        
    print('resolved callbacks. runing as usual')


def tel_main(tel) -> None:
    """Start the bot."""
    application = Application.builder().token(tel).post_init(initialize_tasks).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, respond))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    print('started server')
    with open('secrets') as f:
        tel,ai=tuple(f.read().split('\n'))[:2]

    openai.api_key=ai
    user_threads = {}  # this stores the callback threads 

    tel_main(tel)