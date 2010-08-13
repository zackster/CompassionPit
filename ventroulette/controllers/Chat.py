try:
	import json
except:
	import simplejson as json
import cgi, logging, time

from cogen.core import queue, events
from cogen.core.coroutines import coro
from cogen.core.pubsub import PublishSubscribeQueue

from pylons import request, response, session, tmpl_context as c
from pylons.controllers.util import abort, redirect_to
from pylons.decorators import jsonify

from ventroulette.lib.base import BaseController, render

log = logging.getLogger(__name__)

curId = 0
ventListenQueues = queue.Queue(), queue.Queue()
queues = {}

class DeadTimer(object):
	"""
	Simple timer used to determine whether or not a queue is active.
	- started -- Enables the timer
	- update() -- Updates the timer
	- isDead() -- Determines whether the timer has elapsed, if started == True
	"""
	
	def __init__(self):
		self.started = False
		self.update()
	
	def update(self):
		self.time = time.clock()
	
	def isDead(self):
		if not self.started:
			return False
		return time.clock() - self.time > 60

class ChatController(BaseController):
	def index(self):
		return render('Index.mako')
	
	def chat(self):
		type = request.params.get('type', None)
		if type not in (u'listener', u'venter'):
			return 'Invalid type.'
		return render('Chat.mako', dict(type=type))
	
	def getChatId(self):
		global curId
		type = request.params.get('type', None)
		if type == u'listener':
			type = 0
		elif type == u'venter':
			type = 1
		else:
			yield '-1'
			return
		
		while True:
			# Attempt to find a waiting user.
			yield request.environ['cogen.call'](ventListenQueues[type ^ 1].get_nowait)()
			if isinstance(request.environ['cogen.wsgi'].result, events.OperationTimeout):
				break
			elif isinstance(request.environ['cogen.wsgi'].result, Exception):
				break
			else:
				ret = request.environ['cogen.wsgi'].result
				if ret != None:
					# Got a user.  Check to make sure the queue is still there and not taken.
					if not ret in queues or queues[ret][type][1].started:
						continue
					# Check to make sure the queue hasn't died.  Delete it if it has.
					if queues[ret][type ^ 1][1].isDead():
						del queues[ret]
						continue
					# Start new user's dead timer, push True onto both sides of the queue to start.
					queues[ret][type][1].started = True
					yield request.environ['cogen.call'](queues[ret][type][0].put)(True)
					yield request.environ['cogen.call'](queues[ret][type ^ 1][0].put)(True)
					# Send back chat ID
					yield json.dumps((ret << 1) | type)
					return
				break
		
		# No waiting user found.  Create a new queue.
		id = curId
		curId += 1
		queues[id] = ((queue.Queue(), DeadTimer()), (queue.Queue(), DeadTimer()))
		# Start dead timer.
		queues[id][type][1].started = True
		# Add id to the waiting user queue.
		yield request.environ['cogen.call'](ventListenQueues[type].put)(id)
		val = request.environ['cogen.wsgi'].result
		# Send back chat ID
		yield json.dumps((id << 1) | type)
	
	def send(self):
		try:
			chatId = int(request.params.get('chatId', u''))
		except:
			chatId = u''
		msg = request.params.get('msg', u'')
		if u'' in (chatId, msg):
			yield 'false'
		
		# Split up chat ID
		a, b = chatId >> 1, (chatId & 1) ^ 1
		# If queue is missing, return false.
		if not a in queues:
			yield 'false'
			return
		
		# Escape message and add it to the queue.
		yield request.environ['cogen.call'](queues[a][b][0].put)(cgi.escape(msg))
		val = request.environ['cogen.wsgi'].result
		yield 'true'
	
	def recv(self):
		try:
			chatId = int(request.params.get('chatId', u''))
		except:
			yield 'false'
			return
		
		# Split up chat ID
		a, b = chatId >> 1, chatId & 1
		# If queue is missing, return false.
		if not a in queues:
			yield 'false'
			return
		
		# Update dead timer.
		queues[a][b][1].update()
		# Check other user's dead timer, killing queue and returning false if dead.
		if queues[a][b^1][1].isDead():
			del queues[a]
			yield 'false'
			return
		# Get message from queue, returning null if it doesn't exist.
		yield request.environ['cogen.call'](queues[a][b][0].get)(timeout=10)
		if isinstance(request.environ['cogen.wsgi'].result, events.OperationTimeout):
			yield 'null'
		elif isinstance(request.environ['cogen.wsgi'].result, Exception):
			import traceback
			traceback.print_exception(*request.environ['cogen.wsgi'].exception)
		else:
			ret = request.environ['cogen.wsgi'].result
			if ret == None:
				yield 'null'
			else:
				yield json.dumps(ret)
	
	def newPartner(self):
		try:
			chatId = int(request.params.get('chatId', u''))
		except:
			yield 'false'
			return
		
		# Split up chat ID
		a, b = chatId >> 1, (chatId & 1) ^ 1
		# If queue exists, put False in it (to save a round trip, if the user is 
		# waiting for a message) and delete it.
		if a in queues:
			yield request.environ['cogen.call'](queues[a][b][0].put)(False)
			val = request.environ['cogen.wsgi'].result
			del queues[a]
		yield 'true'
