import os
import json
import requests
from celery import Celery, Task
from config import NOTIFIER_HOST, NOTIFIER_PORT, RABBITMQ_HOST, RABBITMQ_PORT


class NotifierTask(Task):
    """Task that sends notification on completion."""
    abstract = True

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        url = 'http://{}:{}/notify'.format(NOTIFIER_HOST, NOTIFIER_PORT)
        data = {'clientid': kwargs['clientid'], 'result': retval}
        requests.post(url, data=data)


broker = 'amqp://{}:{}'.format(RABBITMQ_HOST, RABBITMQ_PORT)
app = Celery(__name__, broker=broker)


@app.task(base=NotifierTask)
def pronoun_in_tweet(clientid=None):

    # total number of pronoun
    total_pronoun = {
        'han': 0,
        'hon': 0,
        'den': 0,
        'det': 0,
        'denna': 0,
        'denne': 0,
        'hen': 0,
    }

    for filename in os.listdir('data'):
        pronoun_file = scan_data('data/' + filename)
        for key, value in pronoun_file.items():
            total_pronoun[key] += value
    
    return json.dumps(total_pronoun)

def scan_data(filename):

    with open(filename) as f:

        pronoun_file = {
            'han': 0,
            'hon': 0,
            'den': 0,
            'det': 0,
            'denna': 0,
            'denne': 0,
            'hen': 0,
        }

        for line in f:
            if len(line) > 1: # ignore empty lines
                tweet_obj = json.loads(line)
                if not tweet_obj['retweeted']: # ignore retweets
                    pronoun_line = count_pronoun(tweet_obj['text'])
                    for key, value in pronoun_line.items():
                        pronoun_file[key] += value
    
        return pronoun_file

def count_pronoun(json_obj):
    
    # number of pronoun
    num_of_pronoun = dict()
    pronoun = ['han', 'hon', 'den', 'det', 'denna', 'denne', 'hen']

    # store result in a dictionary
    for i in range(0, len(pronoun)):
        num_of_pronoun[pronoun[i]] = count_occurences(json_obj, pronoun[i])
    
    return num_of_pronoun

def count_occurences(str, word): 
      
    # split the string by spaces in a 
    a = str.split(' ') 
  
    # search for pattern in a 
    count = 0
    for i in range(0, len(a)): 
          
        # if match found increase count  
        if (word == a[i]): 
           count = count + 1
             
    return count