import openai 
import json

import os
from os.path import join,exists
from datetime import datetime

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    """Send a message when the command /start is issued."""

    user = update.effective_user
    path=join('users',str(user.id))
    os.makedirs(path,exist_ok=True)

    if(not exists(join(path,'init.json'))):
    	print('new user joined!')
    	with open(join(path,'init.json'),'w') as f:
    		json.dump({'name':user.name,'time':datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f)

    await update.message.reply_html(

        rf"Hi {user.mention_html()}!",

        reply_markup=ForceReply(selective=True),

    )

def get_current_weather(location, unit="fahrenheit"):
    """Get the current weather in a given location"""
    weather_info = {
        "location": location,
        "temperature": "72",
        "unit": unit,
        "forecast": ["sunny", "windy"],
    }
    return json.dumps(weather_info)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    """Echo the user message."""

    messages = [{"role": "user", "content": update.message.text}]
    functions = [
        {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    },
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            },
        }
    ]
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=messages,
        functions=functions,
        function_call="auto",
    )
    
    response_message = response["choices"][0]["message"]

    if response_message.get("function_call"):
        available_functions = {
            "get_current_weather": get_current_weather,
        }
        
        function_name = response_message["function_call"]["name"]
        function_to_call = available_functions[function_name]
        function_args = json.loads(response_message["function_call"]["arguments"])
        
        function_response = function_to_call(
            location=function_args.get("location"),
            unit=function_args.get("unit"),
        )

        messages.append(response_message)
        messages.append(
            {
                "role": "function",
                "name": function_name,
                "content": function_response,
            }
        )
        
        second_response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo-0613",
            messages=messages,
        )
        
        response_text = second_response['choices'][0]['message']['content']
    else:
        response_text = response_message['content']

    await update.message.reply_text(response_text)



def tel_main(tel) -> None:

    """Start the bot."""

    # Create the Application and pass it your bot's token.

    application = Application.builder().token(tel).build()


    # on different commands - answer in Telegram

    application.add_handler(CommandHandler("start", start))


    # on non command i.e message - echo the message on Telegram

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))


    # Run the bot until the user presses Ctrl-C

    application.run_polling(allowed_updates=Update.ALL_TYPES)



if __name__ == "__main__":
	print('started server')
	with open('secrets') as f:
		tel,ai=tuple(f.read().split('\n'))[:2]

	openai.api_key=ai
	tel_main(tel)