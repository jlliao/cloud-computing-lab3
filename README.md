### Cloud Computing Assignment III

Please check the GitHub link to the project: (https://github.com/jlliao/cloud-computing-lab3)
- [Task 1](#task-1)
  * [The Web Server](#the-web-server)
  * [The Web Frontend](#the-web-frontend)
  * [The Background Worker](#the-background-worker)
  * [The Notifier](#the-notifier)
  * [Dockerization and Final Result](#dockerization-and-final-result)
  * [Contextualization](#contextualization)


## Task 1
 ![Alt text](./images/workflow.png)

There are mainly four parts in my solution.

  - A web server - which will send a POST request to a background celery worker
  - A background worker - which will count all the pronouns in the tweets when triggered
  - A notifier - triggered when the counting task is finished and send the result back to the frontend
  - A minimalistic web frontend - in which the user can trigger a task and get a result and data visualization

### The Web Server

I built the server using `Flask`. It has two endpoints. Visiting the root renders some HTML. Sending a POST request to `/runtask` triggers a task (which we’ll define later). It also grabs the client ID from the POST request and pass it along to the worker.

```python
from urllib.parse import urlparse
from flask import Flask, render_template, request
from config import NOTIFIER_PORT
from worker import pronoun_in_tweet


app = Flask(__name__, template_folder='.')


@app.route('/')
def index():
    hostname = urlparse(request.url).hostname
    notifier_url = 'http://{}:{}'.format(hostname, NOTIFIER_PORT)
    return render_template('index.html', notifier_url=notifier_url)


@app.route('/runtask', methods=['POST'])
def runtask():
    clientid = request.form.get('clientid')
    pronoun_in_tweet.delay(clientid=clientid)
    return 'running task...', 202
```

###The Web Frontend
The index.html page contains three elements: a button that sends an AJAX request to `/runtask`, a div that displays the result of the task and a data visualization at the end using `chart-js`. The socket.io.js library (served by our Node.js app) is included for the notifier, so it will subscribe to two events, register and notify, and include the client ID in the POST request that the button click triggers.

```html
<!doctype html>
<html>
<head>
	<meta charset="utf-8">
	<title>Task Example</title>
</head>
<body>

    <button type="button">Run Task</button>
    <br>
    Result: <span id="result"></span>
    <br>
    <canvas id="bar-chart" width="800" height="450"></canvas>

    <script src="{{ notifier_url }}/socket.io/socket.io.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/2.7.2/Chart.js"></script>
    <script>
        var resultElement = document.getElementById('result'),
            client = io('{{ notifier_url }}'),
            labelName = ["han", "hon", "den", "det", "denna", "denne", "hen"]
            clientid = null;
		client.on('register', function(id) {
            clientid = id;
		});
		client.on('notify', function(result) {
            resultElement.textContent = result;
            var dataset = [];
            var dataObj = JSON.parse(result);
            for (var i = 0; i < labelName.length; i++) {
                datapoint = dataObj[labelName[i]] / dataObj['total'];
                dataset.push(datapoint);
            }
            // Bar chart
            new Chart(document.getElementById("bar-chart"), {
                type: 'bar',
                data: {
                labels: labelName,
                datasets: [
                    {
                    label: "Relative frequency of pronouns (normalized)",
                    backgroundColor: ["#3e95cd","#ba7e5c","#8e5ea2","#3cba9f","#7b4834","#e8c3b9","#c45850"],
                    data: dataset
                    }
                ]
                },
                options: {
                legend: { display: false },
                title: {
                    display: true,
                    text: 'Usage Frequency of Swedish Pronouns in Tweet'
                }
                }
            });
		});
        document.querySelector('button').onclick = function() {
            var request = new XMLHttpRequest();
            request.open('POST', '/runtask', true);
            request.setRequestHeader(
                'Content-Type',
                'application/x-www-form-urlencoded; charset=utf-8');
            request.onload = function() {
                resultElement.textContent = request.responseText;
            };
            request.send('clientid=' + clientid);
        };
    </script>

</body>
</html>
```
###The Background Worker 
For the background worker,  I employed the Celery. It defines a task that count the pronoun of all tweets in the data by scaning each .json file line by line. I used RabbitMQ as a message broker to transport jobs between the web server and the background worker. I also subclass the Celery’s Task class so that it calls our notifier service when the task completes.

```python
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
        'total': 0
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
            'total': 0,
        }

        for line in f:
            if len(line) > 1: # ignore empty lines
                tweet_obj = json.loads(line)
                if not tweet_obj['retweeted']: # ignore retweets
                    pronoun_line = count_pronoun(tweet_obj['text'])
                    pronoun_file['total'] += 1 # total plus one
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
```

###The Notifier
This is a minimal Node.js + Express + Socket.IO app with a single POST endpoint `/notify`. This is to notify the result when the task is finished.

```javascript
// notifier.js
var app = require('express')(),
    server = require('http').Server(app),
    io = require('socket.io')(server),
    bodyParser = require('body-parser');

// Accept URL-encoded body in POST request.
app.use(bodyParser.urlencoded({ extended: true }));

// Echo the client's ID back to them when they connect.
io.on('connection', function(client) {
	client.emit('register', client.id);
});

// Forward task results to the clients who initiated them.
app.post('/notify', function(request, response) {
    var client = io.sockets.connected[request.body.clientid];
    client.emit('notify', request.body.result);
	response.type('text/plain');
    response.send('Result broadcast to client.');
});

server.listen(3000);
```
When the client first connects to the notifier service, it echos their Socket.IO identifier back to them. The client later passes this string along with requests it makes to the server, which forwards it along to the background worker. When the background worker completes a task, it calls the `/notify` endpoint with the client ID as a POST parameter. The notifier service thens find the appropriate client to send the task result back to.

###Dockerization and Final Result

I have dockerized the solution for the future deployement. First I have immortalized the project’s dependencies in requirements.txt (for Python / pip) and package.json (for Node.js / npm) files.
```
celery==3.1.17
flask==0.10.1
gunicorn==19.2.1
requests==2.5.1
```
```
{
    "name": "notifier",
    "dependencies": {
      "body-parser": "^1.10.1",
      "express": "^4.10.7",
      "socket.io": "^1.3.4"
    }
}
```
With these in place, the three Dockerfiles (one for each service we built) are minimal.
```
# Dockerfile.notifier
FROM node:8.9-onbuild
EXPOSE 3000
CMD ["node", "notifier.js"]
```
```
# Dockerfile.server
FROM python:3.6-onbuild
EXPOSE 5000
CMD ["gunicorn", "--bind=0.0.0.0:5000", "server:app"]	
```
```
# Dockerfile.worker
FROM python:3.6-onbuild

# Create new user to keep Celery from complaining about being run as root.
RUN groupadd -r celery && useradd -r -g celery celery
USER celery

CMD ["celery", "-A", "worker:app", "worker", "--loglevel=INFO"]
```
I also need to tweak the code so that the services talk to each other using Docker linking, which provide the IP addresses and ports of the other services via environment variables.

Then build the Docker Container.
```
docker build --tag=mminer/myserver --file=dockerfiles/Dockerfile.server .
docker build --tag=mminer/myworker --file=dockerfiles/Dockerfile.worker .
docker build --tag=mminer/mynotifier --file=dockerfiles/Dockerfile.notifier .
```
And finally I employed Docker Compose to save us from manually running docker up.
```
server:
    image: mminer/myserver
    ports:
    - "5000:5000"
    links:
    - notifier
    - rabbitmq

worker:
    image: mminer/myworker
    links:
    - notifier
    - rabbitmq

notifier:
    image: mminer/mynotifier
    ports:
    - "3000:3000"

rabbitmq:
    image: rabbitmq:3.4
```

Now a single docker-compose up runs our four services in unison. Click the button on the web app and we can see the final result.
![Alt text](./images/result.png)
If we check our terminal, indeed the celery worker in our instance has processed the task.
![Alt text](./images/terminal-result.png)

### Contextualization
To automate the process of contextualizing the remote instance, I have coded a cloud-config.txt. Because I have already dockerized my solution in task 1, the cloud-config text document is much simpler. 

```
#cloud-config

apt_update: true
apt_upgrade: true
packages:
 - rabbitmq-server
 - python-pip
 - python-dev
 - build-essential
 - docker-ce
byobu_default: system 

runcmd:
 - echo "export PATH=$PATH:/usr/games" >> /home/ubuntu/.bashrc  
 - source /home/ubuntu/.bashrc
 - git clone https://github.com/jlliao/cloud-computing-lab3
 - docker build --tag=mminer/myserver --file=dockerfiles/Dockerfile.server .
 - docker build --tag=mminer/myworker --file=dockerfiles/Dockerfile.worker .
 - docker build --tag=mminer/mynotifier --file=dockerfiles/Dockerfile.notifier .
 - cd /home/ubuntu/cloud-computing-lab3
 - docker-compose up
```
We also added the flower as well to monitor the usage of our workers. Therefore, we need to edit the requirement.txt and add commend to launch flower in Dockerfile.worker.
```
celery==3.1.17
flask==0.10.1
gunicorn==19.2.1
requests==2.5.1
flower==1.0.0
```
```
# Dockerfile.worker
FROM python:3.6-onbuild

# Create new user to keep Celery from complaining about being run as root.
RUN groupadd -r celery && useradd -r -g celery celery
USER celery

# Add flower to monitor the usage of workers
CMD ["celery", "flower", "-A", "proj", "--broker=amqp://celery:celery@localhost:5672//"]

# Start one worker to execute calculation
CMD ["celery", "-A", "worker:app", "worker", "--loglevel=INFO"]
```
After contextualization, the remote instance is booted successfully and workflow has been streamlined.