$.extend({
	getUrlVars: function(){
		var vars = [], hash;
		var hashes = window.location.href.slice(window.location.href.indexOf('?') + 1).split('&');
		for(var i = 0; i < hashes.length; i++)
		{
			hash = hashes[i].split('=');
			vars.push(hash[0]);
			vars[hash[0]] = hash[1];
		}
		return vars;
	},
	getUrlVar: function(name){
		return $.getUrlVars()[name];
	}
});

function info(msg) {
	status(msg, 'infoMessage')
}

function error(msg) {
	status(msg, 'errorMessage')
}

function status(msg, class) {
	
	
	if(msg == '') {
		msg = '<form id="msgForm"><input id="chatInput" type="text" size=90 /><input type="submit" value="Send Chat"  /></form>';
		msgform = true;
	}
	else {
		msgform = false;
	}
	
	var status = $('#status');
	status.removeClass('errorMessage infoMessage');
	status.addClass(class);
	status.html(msg);
	if(msgform) {
		$('#msgForm').submit(
				function() {
					sendMessage();
					return false;
				}
			);
	}
	
}

var chatId = -1;
var other;
var hasPartner = false;

$(document).ready(
	function() {
		info('Initializing');
		
		$('#msgForm').submit(
				function() {
					sendMessage();
					return false;
				}
			);
		
		$('#newPartner').click(
				function() {
					if(hasPartner) {
						var oldChatId = chatId;
						chatId = -1;
						hasPartner = false;
						$.getJSON(
								'/Chat/newPartner', {chatId: oldChatId}, 
								function(data) {
									addMessage('System', 'Please wait while we find you a new chat partner.');
									getPartner()
								}
							);
					}
				}
			);
		
		other = ($.getUrlVar('type') == 'listener') ? 'Venter' : 'Listener';
		
		getPartner();
	}
);

function getPartner() {
	hasPartner = false;
	$.getJSON(
			'/Chat/getChatId?type=' + $.getUrlVar('type'), 
			function(data) {
				initChat(data);
			}
		);
	info('Waiting for a chat partner... ');
}

function initChat(id) {
	chatId = id;
	
	getMessages();
}

var count = 0;

function addMessage(from, msg) {
	var cls = ((count++ & 1) == 0) ? 'chatMessageEven' : 'chatMessageOdd';
	var row = $('#chatWindow > tbody:last').append('<tr class="' + cls + '"><td>' + from + ': ' + msg + '</td></tr>');
}

function getMessages() {
	var curChatId = chatId;
	$.getJSON(
			'/Chat/recv', {chatId: chatId}, 
			function(data) {
				if(curChatId != chatId)
					return;
				if(data == false) {
					addMessage('System', 'Your chat partner got disconnected. Please wait while we find you a new listener.');
					return getPartner();
				}
				else if(data == true) {
					info('');
					addMessage('System', 'A new chat partner has entered your chat (#' + (chatId >> 1) + ').');
					hasPartner = true;
				}
				else if(data != null)
					addMessage(other, data);
				getMessages();
			}
		)
}

function sendMessage() {
	var msg = $('#chatInput').val();
	if(msg == '' || chatId == -1)
		return;
	info('Sending message...')
	$.getJSON(
			'/Chat/send', {chatId: chatId, msg: msg}, 
			function(data) {
				if(data == true) {
					addMessage('Me', msg);
					info('');
					$('#chatInput').val('')
				} else {
					error('Failed to send message.')
				}
			}
		);
}
