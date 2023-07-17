import openai 
import numpy as np
import json
from datetime import datetime


async def get_embedding(text, model="text-embedding-ada-002"):
   text = text.replace("\n", " ")
   x= await openai.Embedding.acreate(input = [text], model=model)
   return np.array(x['data'][0]['embedding'])

async def gpt_response(messages,model='gpt-3.5-turbo'):
	#input validation
	for m in messages:
		assert m['role'] in alowed_roles
		if m['role']=='function':
			assert 'name' in m.keys()
		assert 'content' in m.keys()

	x=await openai.ChatCompletion.acreate(model=model,messages=messages,functions=functions)
	print(x)	
	x=x["choices"][0]["message"]
	return x.get('content'),x.get("function_call")

alowed_roles=('system','user','assistant','function')
'''
    {
        "name": "get_current_time",
        "description": "Get the current time",
        "parameters": {
        	"type": "object",
        	"properties": {
        	}

        }
    },
    {
    "name": "change_note",
        "description": "changes note idx to be text",
        "parameters": {
        	"type": "object",
        	"properties": {
        		"idx":{
        			"type":'integer',
        			"description": "index",
        		},
        		"text":{
        			"type":'string',
        			"description": "the desired text",
        		}
        	}

        }
    }
'''
functions = [
    {
    "name": "change_note",
        "description": '''changes note in folder idx in the feilds that are not None
        if all fields but the index are None remmoves note''',
        "parameters": {
        	"type": "object",
        	"properties": {
        		"idx":{
        			"type":'integer',
        			"description": "pass None to make new",
        		},
        		"folder":{
        			"type":'string',
        			"description": "one of your 4 folders ['user profile', 'goals', 'memories', 'reflections']",
        		},
        		"text":{
        			"type":'string',
        			"description": "the desired text",
        		},
        		"importance":{
        			"type":'int',
        			"description": 'a rank from 0 to 10',
        		}
        	}

        }
    },
    "name": "change_event",
        "description": "changes note idx in the feilds that are not None",
        "parameters": {
        	"type": "object",
        	"properties": {
        		"idx":{
        			"type":'integer',
        			"description": "pass None to make new",
        		},
        		"name":{
        			"type":'string',
        			"description": "the desired text",
        		},
        		"start":{
        			"type":'string',
        			"description": f"format {r'%Y-%m-%d %H:%M'}",
        		},
        		"end":{
        			"type":'string',
        			"description": f"format {r'%Y-%m-%d %H:%M'}",
        		},
        		"wakeup":{
        			"type":'string',
        			"description": 'if set to true will remind you of the time',
        		}
        	}

        }
    ]

def get_current_time():
    current_time = datetime.now().strftime("%H:%M:%S")
    return {'role':'function',
    	'name':'get_current_time',
    	'content':current_time}


if __name__=='__main__':
	from embedding import Lazy_embed 
	from utills import un_async

	with open('secrets') as f:
	    tel,ai=tuple(f.read().split('\n'))[:2]

	openai.api_key=ai
	'''
	print(un_async(get_embedding('stuff')))
	embeder=Lazy_embed('embeddings/text-embedding-ada-002',func=get_embedding)
	print(un_async(embeder('five')))
	'''

	'''
	messages=[{'role':'system','content':'the user is an alcoholic you need to get them to stop'},
	{'role':'user','content':'hey'},
	{'role':'assistant','content':'hey'},
	{'role':'user','content':'lets go see the game'},
	get_current_time()]

	x=un_async(gpt_response(messages)) 
	print(x)
	'''
	messages=[{'role':'system','content':'you are a robo asistent'},
	{'role':'user','content':'change note 5 to be on 8:00 in 16 july 2020'}]
	print(messages)
	print(functions)
	x=un_async(gpt_response(messages)) 
	print(x)
	print({k:type(v) for k,v in json.loads(x[1]['arguments']).items()})
	print(x[1]['arguments'])
	print(x[1]['arguments']['text'])