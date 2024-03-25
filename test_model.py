#!/usr/bin/env python
import accelerate
import logging
from transformers import (
    LlamaConfig,
    LlamaTokenizer,
    LlamaForCausalLM,
    BitsAndBytesConfig,
    set_seed
    )
import torch


# random seed for reproducibility
set_seed(42)
torch.manual_seed(42)
torch.cuda.manual_seed_all(42)

# Model names: "chrisyuan45/TimeLlama-7b-chat", "chrisyuan45/TimeLlama-13b-chat"
model_name = "chrisyuan45/TimeLlama-7b-chat"
quantization_config = BitsAndBytesConfig.from_dict({
    'load_in_4bit': True,
    'bnb_4bit_compute_dtype': torch.float16,
    'bnb_4bit_quant_type': 'nf4',
    'bnb_4bit_use_double_quant':True})

model = LlamaForCausalLM.from_pretrained(
        model_name,
        return_dict=True,
        #load_in_8bit=True,
        quantization_config = quantization_config,
        device_map="auto",
        low_cpu_mem_usage=True)
logging.info(f'Model {model} loaded.')
tokenizer = LlamaTokenizer.from_pretrained(model_name)
logging.info('Tokenizer loaded.')

def generate(model, tokenizer, prompt):
    input_ids = tokenizer.encode(prompt, return_tensors="pt")
    # inputs.input_ids = inputs.input_ids.to('meta')
    input_ids = input_ids.to('cuda')
    ids = model.generate(input_ids,
                        max_new_tokens=100,
                        num_return_sequences=5,
                        temperature=1.0,
                        top_p=1.0,
                        top_k=10,
                        repetition_penalty=1.0,
                        length_penalty=1,
                        no_repeat_ngram_size=2)
    output = [tokenizer.decode(ids[i], skip_special_tokens=True) for i in range(len(ids))]
    print(ids)
    print(output)
    logging.info('Generated.')
    return output


if __name__=='__main__':
    logging.basicConfig(filename='log/test.log', format=f'%(levelname)s: %(message)s', level=logging.INFO, filemode='w')
    # duration
    prompt = "How long did Cannes Film Festival 2019 last?"  # duration,12 days,Facts
    generate(model, tokenizer, prompt)
    prompt2 = "How often does Christmas occur? \nChoose from the answers: Every 2 years, once a year, or every 3 years?"  # frequency, Every 2 years,Once a year,Every 3 years,B,Facts
    generate(model, tokenizer, prompt2)
    prompt3 = "Sarah was born. Then Sarah started kindergarten. - Is this true or false?" # ordering, Sarah was born. Then Sarah started kindergarten. - True/False?,TRUE,FALSE,Undetermined,A,Commonsense
    generate(model, tokenizer, prompt3)
    prompt4 = "Arrange the following events in chronological order: (1) Mike opened a second bakery location. (2) Mike launched his online cake delivery service." # order, (1), (2)",Commonsense"
    generate(model, tokenizer, prompt4)
