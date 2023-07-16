import openai 
import numpy as np

async def get_embedding(text, model="text-embedding-ada-002"):
   text = text.replace("\n", " ")
   x= await openai.Embedding.acreate(input = [text], model=model)
   return np.array(x['data'][0]['embedding'])


if __name__=='__main__':
	from embedding import Lazy_embed 
	from utills import un_async

	with open('secrets') as f:
	    tel,ai=tuple(f.read().split('\n'))[:2]

	openai.api_key=ai

	print(un_async(get_embedding('stuff')))
	embeder=Lazy_embed('embeddings/text-embedding-ada-002',func=get_embedding)
	print(un_async(embeder('five')))