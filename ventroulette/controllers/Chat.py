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
			yield request.environ['cogen.call'](ventListenQueues[type ^ 1].get_nowait)()
			if isinstance(request.environ['cogen.wsgi'].result, events.OperationTimeout):
				break
			elif isinstance(request.environ['cogen.wsgi'].result, Exception):
				break
			else:
				ret = request.environ['cogen.wsgi'].result
				if ret != None:
					if queues[ret][type ^ 1][1].isDead():
						continue
					queues[ret][type][1].started = True
					queues[ret][type][1].started = True
					yield request.environ['cogen.call'](queues[ret][type][0].put)(True)
					yield request.environ['cogen.call'](queues[ret][type ^ 1][0].put)(True)
					yield json.dumps((ret << 1) | type)
					return
				break
		
		id = curId
		curId += 1
		queues[id] = ((queue.Queue(), DeadTimer()), (queue.Queue(), DeadTimer()))
		yield request.environ['cogen.call'](ventListenQueues[type].put)(id)
		val = request.environ['cogen.wsgi'].result
		yield json.dumps((id << 1) | type)
	
	def send(self):
		try:
			chatId = int(request.params.get('chatId', u''))
		except:
			chatId = u''
		msg = request.params.get('msg', u'')
		if u'' in (chatId, msg):
			yield json.dumps(False)
		
		a, b = chatId >> 1, (chatId & 1) ^ 1
		yield request.environ['cogen.call'](queues[a][b][0].put)(cgi.escape(msg))
		val = request.environ['cogen.wsgi'].result
		yield json.dumps(True)
	
	def recv(self):
		try:
			chatId = int(request.params.get('chatId', u''))
		except:
			yield json.dumps(False)
			return
		
		a, b = chatId >> 1, chatId & 1
		
		if not a in queues:
			yield 'false'
			return
		
		queues[a][b][1].update()
		if queues[a][b^1][1].isDead():
			del queues[a]
			yield 'false'
			return
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
			yield json.dumps(False)
			return
		
		a, b = chatId >> 1, (chatId & 1) ^ 1
		yield request.environ['cogen.call'](queues[a][b][0].put)(False)
		val = request.environ['cogen.wsgi'].result
		del queues[a]
		yield json.dumps(True)
