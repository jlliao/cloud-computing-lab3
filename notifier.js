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