#!/usr/bin/env python
import accelerate
import json
import logging
import os
import pandas as pd
from transformers import (
    LlamaConfig,
    LlamaTokenizer,
    LlamaForCausalLM,
    BitsAndBytesConfig,
    set_seed
    )
import random
import torch

from prompting import read_data, few_shot, create_prompt


# random seed for reproducibility
set_seed(42)
torch.manual_seed(42)
torch.cuda.manual_seed_all(42)

logging.basicConfig(filename='log/test.log', format=f'%(levelname)s: %(message)s',
        level=logging.INFO, filemode='w')

def set_up_model(chat=False):
    if chat:
        model_name = "chrisyuan45/TimeLlama-7b-chat"
    else:
        model_name = "chrisyuan45/TimeLlama-7b"
    quantization_config = BitsAndBytesConfig.from_dict({
        'load_in_4bit': True,
        'bnb_4bit_compute_dtype': torch.float16,
        'bnb_4bit_quant_type': 'nf4',
        'bnb_4bit_use_double_quant':True})

    model = LlamaForCausalLM.from_pretrained(
            model_name,
            return_dict=True,
            quantization_config = quantization_config,
            device_map="auto",
            low_cpu_mem_usage=True)
    logging.info(f'Model {model} loaded.')
    tokenizer = LlamaTokenizer.from_pretrained(model_name)
    logging.info('Tokenizer loaded.')
    return model, tokenizer

def generate(model, tokenizer, prompt):
    """Generate 5 outputs from a prompt."""
    input_ids = tokenizer.encode(prompt, return_tensors="pt")
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
    output = [tokenizer.decode(ids[i], skip_special_tokens=True) 
                        for i in range(len(ids))]
    return output

def run_dataset(dir, model, tokenizer, shots=5, output_file='', num_instances=10):
    """
    Generate outputs for a given dataset directory.

    Parameters:
        dir (str): The directory containing the dataset files.
        shots (int, optional): The number of shots to generate for each prompt.
            Default is 5.
        output_file (str, optional): The path to the output file where the
            generated outputs will be saved in JSON format. Default is ''.
        num_instances (int, optional): The number of instances to sample from
            the dataset. Default is 10.

    Returns:
        None

    Generates outputs for a given dataset by sampling instances and generating
    outputs using a pre-trained model. Outputs are generated for each instance
    and stored in a dictionary, which is then saved to a JSON file if
    output_file is provided. Each output includes the prompt, generated outputs,
    and original question, answer, and category of the instance.
    """
    ds = read_data(dir)
    # sample from the dataset
    ds_sample = ds.sample(n=num_instances, random_state=42)
    outputs = dict()
    # check question type mcq or saq
    mcq = dir.endswith('_mcq.csv')
    for d in ds_sample.iterrows():
        prompt = create_prompt(d, shots=shots,
                        shot_dir=dir.replace('_', '_shots_'), mcq=mcq)
        try:
            output = generate(model, tokenizer, prompt)
        except Exception as e:  # runtime error
            logging.error(e)
            continue
        output_wo_prompt = [o.replace(prompt, '') for o in output]
        outputs[str(d[0])] = {"Question": d[1].Question,
            "Answer": d[1].Answer,
            "Category": d[1].Category,
            "Outputs": output_wo_prompt}
        if mcq:
            outputs[str(d[0])]["Options"] = list(d[1:4])
    print(prompt)
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as fp:
            json.dump(outputs, fp, indent=4)
        logging.INFO(f'Finished {output_file}.')

def run_dataset_all(d, model, tokenizer):
    """Generate outputs for a whole dataset, in 0- and 5-shot scenarios."""
    # mcq questions
    run_dataset(f'data/{d}/{d}_mcq.csv', shots=0,
        output_file=f'outputs/{d}_mcq_0shot_nc.json')
    run_dataset(f'data/{d}/{d}_mcq.csv', shots=5,
        output_file=f'outputs/{d}_mcq_5shot_nc.json')
    # saq questions, not in all subcorpora
    if os.path.exists(f'data/{d}/{d}_saq.csv'):
        run_dataset(f'data/{d}/{d}_saq.csv', shots=0,
            output_file=f'outputs/{d}_saq_0shot_nc.json')
        run_dataset(f'data/{d}/{d}_saq.csv', shots=5,
            output_file=f'outputs/{d}_saq_5shot_nc.json')

if __name__=='__main__':
    model, tokenizer = set_up_model()
    for d in os.listdir('data'):
        run_dataset_all(d)
