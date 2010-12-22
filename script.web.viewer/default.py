from htmltoxbmc import HTMLConverter
import re, os, sys, time, urllib2, urlparse
import xbmc, xbmcgui, xbmcaddon #@UnresolvedImport
import mechanize, threading

__plugin__ = 'Web Viewer'
__author__ = 'ruuk (Rick Phillips)'
__url__ = 'http://code.google.com/p/webviewer-xbmc/'
__date__ = '12-12-2010'
__version__ = '0.7.1'
__addon__ = xbmcaddon.Addon(id='script.web.viewer')
__language__ = __addon__.getLocalizedString

THEME = 'Default'

ACTION_MOVE_LEFT      = 1
ACTION_MOVE_RIGHT     = 2
ACTION_MOVE_UP        = 3
ACTION_MOVE_DOWN      = 4
ACTION_PAGE_UP        = 5
ACTION_PAGE_DOWN      = 6
ACTION_SELECT_ITEM    = 7
ACTION_HIGHLIGHT_ITEM = 8
ACTION_PARENT_DIR     = 9
ACTION_PREVIOUS_MENU  = 10
ACTION_SHOW_INFO      = 11
ACTION_PAUSE          = 12
ACTION_STOP           = 13
ACTION_NEXT_ITEM      = 14
ACTION_PREV_ITEM      = 15
ACTION_SHOW_GUI       = 18
ACTION_PLAYER_PLAY    = 79
ACTION_MOUSE_LEFT_CLICK = 100
ACTION_CONTEXT_MENU   = 117

#Actually it's show codec info but I'm using in a threaded callback
ACTION_RUN_IN_MAIN = 27

def ERROR(message):
	errtext = sys.exc_info()[1]
	print 'WEBVIEWER - %s::%s (%d) - %s' % (message,sys.exc_info()[2].tb_frame.f_code.co_name, sys.exc_info()[2].tb_lineno, errtext)
	return str(errtext)
	
def LOG(message):
	print 'WEBVIEWER: %s' % message

def clearDirFiles(filepath):
	if not os.path.exists(filepath): return
	for f in os.listdir(filepath):
		f = os.path.join(filepath,f)
		if os.path.isfile(f): os.remove(f)
		
class WebReader:
	def __init__(self):
		self.browser = mechanize.Browser()
		self.browser.set_handle_robots(False)
		self.browser.set_handle_redirect(True)
		self.browser.set_handle_refresh(True, honor_time=False)
		self.browser.set_handle_equiv(True)
		self.browser.set_debug_redirects(True)
		self.browser.addheaders = [('User-agent', 'Mozilla/3.0 (compatible)')]
		#self.browser.addheaders = [('User-agent','Mozilla/5.0 (X11; Linux i686; rv:2.0.1) Gecko/20100101 Firefox/4.0.1')]
		
	def getWebPage(self,url,callback=None):
		print url
		if not callback: callback = self.fakeCallback
		html = ''
		id = ''
		urlsplit = url.split('#',1)
		if len(urlsplit) > 1: url,id = urlsplit
		try:
			html = self.readURL(url, callback)
		except:
			err = ERROR('ERROR READING PAGE')
			LOG('URL: %s' % url)
			xbmcgui.Dialog().ok('ERROR','Error loading page.',err)
		url,html = self.checkRedirect(html,url,callback)
		if not callback(80,'Processing Data'): return None
		return WebPage(html,url,id=id,forms=self.browser.forms())
	
	def checkRedirect(self,html,url=None,callback=None):
		if not callback: callback = self.fakeCallback
		match = re.search('<meta[^>]+?http-equiv="Refresh"[^>]*?URL=(?P<url>[^>"]+?)"[^>]*?/>',html)
		#print html
		if match:
			LOG('REDIRECTING TO %s' % match.group('url'))
			if not callback(3,'Redirecting'): return None
			try:
				url = match.group('url')
				html = self.readURL(url, callback)
			except:
				#err = 
				ERROR('ERROR READING PAGE REDIRECT')
				LOG('URL: %s' % url)
				return url,html
				#xbmcgui.Dialog().ok('ERROR','Error loading page.',err)
		return url,html
	
	def readURL(self,url,callback):
		if not callback(5,'Opening Page'): return ''
		response = self.browser.open(url)
		if not callback(30,'Reading Data'): return ''
		return response.read()
		
	def submitForm(self,form,submit_control):
		self.browser.form = form
		ct = 0
		for c in form.controls:
			if c.type == 'submit':
				if c == submit_control: break
				ct += 1 
		res = self.browser.submit(nr=ct)
		html = res.read()
		url,html = self.checkRedirect(html) #@UnusedVariable
		return WebPage(html,self.browser.geturl(),forms=self.browser.forms())
		
	def getForm(self,html,action,name=None):
		if not action: return None
		try:
			forms = self.mechanize.ParseString(''.join(re.findall('<form\saction="%s.+?</form>' % re.escape(action),html,re.S)),self._url)
			if name:
				for f in forms:
					if f.name == name:
						return f
			for f in forms:
				if action in f.action:
					return f
			LOG('NO FORM 2')
		except:
			ERROR('PARSE ERROR')
		
	def fakeCallback(self,pct,message=''): return True
						
	def doForm(self,url,form_name=None,action_match=None,field_dict={},controls=None,submit_name=None,submit_value=None,wait='1',callback=None):
		if not callback: callback = self.fakeCallback
		if not self.checkLogin(callback=callback): return False
		res = self.browser.open(url)
		html = res.read()
		selected = False
		try:
			if form_name:
				self.browser.select_form(form_name)
				LOG('FORM SELECTED BY NAME')
			else:
				predicate = lambda formobj: action_match in formobj.action
				self.browser.select_form(predicate=predicate)
				LOG('FORM SELECTED BY ACTION')
			selected = True
		except:
			ERROR('NO FORM 1')
			
		if not selected:
			form = self.getForm(html,action_match,form_name)
			if form:
				self.browser.form = form
			else:
				return False
		try:
			for k in field_dict.keys():
				if field_dict[k]: self.browser[k] = field_dict[k]
			self.setControls(controls)
			wait = int(wait)
			time.sleep(wait) #or this will fail on some forums. I went round and round to find this out.
			res = self.browser.submit(name=submit_name,label=submit_value)
		except:
			ERROR('FORM ERROR')
			return False
			
		return True
		
	def setControls(self,controls):
		if not controls: return
		x=1
		for control in controls:
			ctype,rest = control.split(':',1)
			ftype,rest = rest.split('.',1)
			name,value = rest.split('=')
			control = self.browser.find_control(**{ftype:name})
			if ctype == 'radio':
				control.value = [value]
			elif ctype == 'checkbox':
				control.items[0].selected = value == 'True'
			x+=1

################################################################################
# Web Page
################################################################################
class WebPage:
	def __init__(self,html,url,id='',forms=[]):
		self.url = url
		self.html = html
		self.id = id
		self.forms = []
		self._labels = None
		self._headers = None
		for f in forms: self.forms.append(f)
		
	def isDisplayable(self):
		return bool(self.html)
	
	def forDisplay(self):
		return HC.htmlToDisplay(self.html)
	
	def forDisplayWithIDs(self):
		return HC.htmlToDisplayWithIDs(self.html)
		
	def imageURLs(self):
		urls = []
		for url in HC.imageFilter.findall(self.html,re.S):
			for u in urls:
				if u == url: break
			else:
				urls.append(url)
		return urls
		
	def linkImageURLs(self):
		return re.findall('<a.+?href="(http://.+?\.(?:jpg|png|gif|bmp))".+?</a>',self.html,re.S)
		
	def linkURLs(self):
		html = unicode(self.html,'utf8','replace')
		return HC.linkFilter.finditer(HC.cleanHTML(html))
		
	def links(self):
		links = []
		for m in self.linkURLs(): links.append(Link(m,self.url))
		return links
	
	def labels(self):
		if self._labels: return self._labels, self._headers
		self._labels = {}
		self._headers = {}
		for m in HC.labelFilter.finditer(self.html,re.S):
			self._labels[m.group('inputid')] = HC.convertHTMLCodes(HC.tagFilter.sub('',m.group('label')))
		for m in HC.altLabelFilter.finditer(HC.lineFilter.sub('',self.html)):
			if not m.group('inputid') in self._labels:
				self._labels[m.group('inputid')] = HC.convertHTMLCodes(m.group('label'))
				header = m.group('header')
				if header: header = header.strip()
				if header: self._headers[m.group('inputid')] = HC.convertHTMLCodes(header)
		for k in self._labels.keys():
			if self._labels[k].endswith(':'):
				self._labels[k] = self._labels[k][:-1]
		return self._labels, self._headers
	
	def getForm(self,name=None,action=None,index=None):
		if name:
			for f in self.forms:
				if name == f.name: return f
		if action:
			for f in self.forms:
				if action in f.action: return f
		if index:
			ct = 0
			for f in self.forms:
				if ct == index: return f
		return None
		

class Link:
	def __init__(self,match=None,url=''):
		self.baseUrl = url
		self.url = ''
		self.text = ''
		self._isImage = False
		
		if match:
			self.url = match.group('url')
			text = match.group('text') 
			text = HC.tagFilter.sub('',text).strip()
			self.text = HC.convertHTMLCodes(text)
		self.processURL()
			
	def processURL(self):
		if not self.url: return
		self.url = self.url.replace('&amp;','&')
		self._isImage = re.search('http://.+?\.(?:jpg|png|gif|bmp)',self.url) and True or False
		if self._isImage: return
			
	def urlShow(self):
		return self.fullURL()
		
	def isImage(self):
		return self._isImage
	
	def fullURL(self):
		return fullURL(self.baseUrl,self.url)

def fullURL(baseUrl,url):
		if not url.startswith('http://'):
			base = baseUrl.split('://',1)[-1]
			base = base.rsplit('/',1)[0]
			domain = base.split('/',1)[0]
			if url.startswith('/'):
				if url.startswith('//'):
					return 'http:' + url
				else:
					return 'http://' + domain + url
			else:
				if not base.endswith('/'): base += '/'
				return 'http://' + base + url
		return url

class URLHistory:
	def __init__(self,url=''):
		self.index = 0
		self.urls = [url]
		self.lines = [0]
		
	def addURL(self,url,line=0,old_line=None):
		if old_line: self.lines[self.index] = old_line
		self.urls.append(url)
		self.lines.append(line)
		self.index += 1
		
	def goBack(self):
		self.index -= 1
		if self.index < 0: self.index = 0
		return self.urls[self.index],self.lines[self.index]
		
######################################################################################
# Base Window Classes
######################################################################################
class StoppableThread(threading.Thread):
	def __init__(self,group=None, target=None, name=None, args=(), kwargs={}):
		self._stop = threading.Event()
		threading.Thread.__init__(self,group=group, target=target, name=name, args=args, kwargs=kwargs)
		
	def stop(self):
		self._stop.set()
		
	def stopped(self):
		return self._stop.isSet()
		
class StoppableCallbackThread(StoppableThread):
	def __init__(self,target=None, name=None):
		self._target = target
		self._stop = threading.Event()
		self._finishedHelper = None
		self._finishedCallback = None
		self._progressHelper = None
		self._progressCallback = None
		StoppableThread.__init__(self,name=name)
		
	def setArgs(self,*args,**kwargs):
		self.args = args
		self.kwargs = kwargs
		
	def run(self):
		self._target(*self.args,**self.kwargs)
		
	def setFinishedCallback(self,helper,callback):
		self._finishedHelper = helper
		self._finishedCallback = callback
	
	def setProgressCallback(self,helper,callback):
		self._progressHelper = helper
		self._progressCallback = callback
		
	def stop(self):
		self._stop.set()
		
	def stopped(self):
		return self._stop.isSet()
		
	def progressCallback(self,*args,**kwargs):
		if self.stopped(): return False
		if self._progressCallback: self._progressHelper(self._progressCallback,*args,**kwargs)
		return True
		
	def finishedCallback(self,*args,**kwargs):
		if self.stopped(): return False
		if self._finishedCallback: self._finishedHelper(self._finishedCallback,*args,**kwargs)
		return True
	
class ThreadWindow:
	def __init__(self):
		self._currentThread = None
		self._stopControl = None
		self._startCommand = None
		self._progressCommand = None
		self._endCommand = None
		self._isMain = False
		self._resetFunction()
			
	def setAsMain(self):
		self._isMain = True
		
	def setStopControl(self,control):
		self._stopControl = control
		control.setVisible(False)
		
	def setProgressCommands(self,start=None,progress=None,end=None):
		self._startCommand = start
		self._progressCommand = progress
		self._endCommand = end
		
	def onAction(self,action):
		if action == ACTION_RUN_IN_MAIN:
			if self._function:
				self._function(*self._functionArgs,**self._functionKwargs)
				self._resetFunction()
				return True
		elif action == ACTION_PREVIOUS_MENU:
			if self._currentThread and self._currentThread.isAlive():
				self._currentThread.stop()
				if self._endCommand: self._endCommand()
				if self._stopControl: self._stopControl.setVisible(False)
			if self._isMain and len(threading.enumerate()) > 1:
				d = xbmcgui.DialogProgress()
				d.create('Waiting','Waiting for threads to close...')
				d.update(0)
				self.stopThreads()
				if d.iscanceled():
					d.close()
					return True
				d.close()
			return False
		return False
	
	def stopThreads(self):
		for t in threading.enumerate():
			if isinstance(t,StoppableThread): t.stop()
		for t in threading.enumerate():
			if t != threading.currentThread(): t.join()
			
	def _resetFunction(self):
		self._function = None
		self._functionArgs = []
		self._functionKwargs = {}
		
	def runInMain(self,function,*args,**kwargs):
		self._function = function
		self._functionArgs = args
		self._functionKwargs = kwargs
		xbmc.executebuiltin('Action(codecinfo)')
		
	def endInMain(self,function,*args,**kwargs):
		if self._endCommand: self._endCommand()
		if self._stopControl: self._stopControl.setVisible(False)
		self.runInMain(function,*args,**kwargs)
		
	def getThread(self,function,finishedCallback=None,progressCallback=None):
		if self._currentThread: self._currentThread.stop()
		if not progressCallback: progressCallback = self._progressCommand
		t = StoppableCallbackThread(target=function)
		t.setFinishedCallback(self.endInMain,finishedCallback)
		t.setProgressCallback(self.runInMain,progressCallback)
		self._currentThread = t
		if self._stopControl: self._stopControl.setVisible(True)
		if self._startCommand: self._startCommand()
		return t
		
	def stopThread(self):
		if self._stopControl: self._stopControl.setVisible(False)
		if self._currentThread:
			self._currentThread.stop()
			self._currentThread = None
			if self._endCommand: self._endCommand()
		
class BaseWindow(xbmcgui.WindowXMLDialog,ThreadWindow):
	def __init__( self, *args, **kwargs ):
		self._progMessageSave = ''
		ThreadWindow.__init__(self)
		xbmcgui.WindowXMLDialog.__init__( self, *args, **kwargs )
	
	def onClick( self, controlID ):
		return False
			
	def onAction(self,action):
		if action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		if ThreadWindow.onAction(self,action): return
		xbmcgui.WindowXMLDialog.onAction(self,action)
	
	def startProgress(self):
		self._progMessageSave = self.getControl(104).getLabel()
		self.getControl(310).setWidth(1)
		self.getControl(310).setVisible(True)
	
	def setProgress(self,pct,message=''):
		w = int((pct/100.0)*self.getControl(300).getWidth())
		self.getControl(310).setWidth(w)
		self.getControl(104).setLabel(message)
		return True
		
	def endProgress(self):
		self.getControl(310).setVisible(False)
		self.getControl(104).setLabel(self._progMessageSave)

class FormDialog(xbmcgui.WindowXMLDialog):
	def __init__( self, *args, **kwargs ):
		self.form = kwargs.get('form')
		self.labels = kwargs.get('labels')
		self.headers = kwargs.get('headers')
		self.submit = None
		xbmcgui.WindowXMLDialog.__init__( self, *args, **kwargs )
	
	def onInit(self):
		self.controlList = self.getControl(120)
		self.createForm()
	
	def addLabel(self,text):
		item = xbmcgui.ListItem(label=text)
		item.setInfo('video',{'Genre':'label'})
		self.controlList.addItem(item)
		
	def createForm(self):
		form = self.form
		labels = self.labels
		idx = 0
		trail = False
		notrail = True
		for c in form.controls:
			if c.type != 'hidden':
				label = labels.get(c.id) or labels.get(c.name) or c.name or c.type.title()
				header = self.headers.get(c.id) or self.headers.get(c.name)
				if header and not c.type == 'submit': self.addLabel(header)
				if trail and notrail:
					notrail = False
				elif trail:
					trail = False
				notrail = True
				if c.type == 'checkbox' or c.type == 'radio':
					multiple = len(c.items) > 1
					if multiple and not trail and not header: self.controlList.addItem(xbmcgui.ListItem())
					cidx = 0
					for i in c.items:
						if multiple:
							label = i.name or labels.get(i.id) or labels.get(i.name) or i.id
						else:
							label = labels.get(i.id) or labels.get(i.name) or i.id
						value = i.selected
						item = xbmcgui.ListItem(label=label)
						item.setInfo('video',{'Genre':'checkbox'})
						item.setInfo('video',{'Director':value and 'checked' or 'unchecked'})
						item.setProperty('index',str(idx))
						item.setProperty('cindex',str(cidx))
						self.controlList.addItem(item)
						cidx += 1
					if len(c.items) > 1:
						trail = True
						self.controlList.addItem(xbmcgui.ListItem())
				elif c.type == 'submit' or c.type == 'image':
					a = c.attrs
					#value = a.get('title','')
					item = xbmcgui.ListItem(label=a.get('alt') or c.value or label)
					item.setInfo('video',{'Genre':'submit'})
					item.setProperty('index',str(idx))
					self.controlList.addItem(item)
				elif c.type == 'text' or c.type == 'password' or c.type == 'textarea':
					a = c.attrs
					label = labels.get(c.id) or labels.get(c.name) or a.get('title') or a.get('value') or a.get('type')
					if c.type == 'password':
						value = '*' * len(c.value or '')
					else:
						value = c.value or ''
					#label = label + ': ' + value
					item = xbmcgui.ListItem(label=label,label2=value)
					item.setInfo('video',{'Genre':'text'})
					item.setProperty('index',str(idx))
					self.controlList.addItem(item)
				elif c.type == 'select':
					pre = labels.get(c.id,labels.get(c.name,''))
					if pre: self.addLabel(pre)
					if c.value:
						value = c.value[0]
						citem = c.get(value)
						label = citem.attrs.get('label',value)
					else:
						label = 'Multi-Select'
					item = xbmcgui.ListItem(label=label)
					item.setInfo('video',{'Genre':'select'})
					item.setProperty('index',str(idx))
					self.controlList.addItem(item)
				elif c.type == 'file':
					if label: self.addLabel(label)
					label = ''
					if c._upload_data:
						try:
							label = c._upload_data[0][0].name
						except:
							ERROR('Error setting file control label')
							pass
					item = xbmcgui.ListItem(label=label)
					item.setInfo('video',{'Genre':'file'})
					item.setProperty('index',str(idx))
					self.controlList.addItem(item)
			idx+=1
					
	def onFocus( self, controlId ):
		self.controlId = controlId
	
	def onClick( self, controlID ):
		if controlID == 120:
			self.doControl()
			
	def getFormControl(self,item):
		idx = item.getProperty('index')
		if not idx.isdigit():
			print 'error',idx
			return None
		idx = int(idx)
		return self.form.controls[idx]
			
	def doControl(self):
		item = self.controlList.getSelectedItem()
		control = self.getFormControl(item)
		if not control: return
		ctype = control.type
		if ctype == 'text' or ctype == 'password' or ctype == 'textarea':
			text = doKeyboard(item.getLabel(),item.getLabel2(),hidden=bool(ctype == 'password'))
			if text == None: return
			control.value = text
			if ctype == 'password':
				text = '*' * len(text)
			item.setLabel2(text)
		elif ctype == 'checkbox' or ctype == 'radio':
			cidx = int(item.getProperty('cindex'))
			value = control.items[cidx].selected
			value = not value
			control.items[cidx].selected = value
			if type == 'checkbox':
				item.setInfo('video',{'Director':value and 'checked' or 'unchecked'})
			else:
				pos = self.controlList.getSelectedPosition() - cidx
				for i,ci in zip(range(0,len(control.items)),control.items):
					value = ci.selected
					it = self.controlList.getListItem(pos + i)
					it.setInfo('video',{'Director':value and 'checked' or 'unchecked'})
		elif ctype == 'select':
			if control.multiple:
				while self.doSelect(control,item): pass
			else:
				self.doSelect(control,item)
		elif ctype == 'submit' or ctype == 'image':
			self.submit = control
			self.close()
		elif ctype == 'file':
			fname = xbmcgui.Dialog().browse(1,'Select File','files')
			control.add_file(open(fname,'r'),filename=os.path.basename(fname))
			item.setLabel(fname)
			
	
	def doSelect(self,control,item):
		options = []
		for i in control.items:
			cb = i.selected and unichr(0x2611) or unichr(0x2610)
			options.append(cb + ' ' + (i.attrs.get('label',i.name) or i.name))
			#options.append(i.attrs.get('label',i.name) or i.name)
		dialog = xbmcgui.Dialog()
		idx = dialog.select('Select',options)
		if idx < 0: return False
		i = control.items[idx]
		i.selected = not i.selected
		if control.multiple:
			ct = 0
			for i in control.items:
				if i.selected: ct += 1
			if ct:
				label = '%s Selected' % ct
			else:
				label = 'Multi-Select'
		else:
			value = control.value[0]
			citem = control.get(value)
			label = citem.attrs.get('label',value)
		item.setLabel(label)
		return True
			
	def onAction(self,action):
		if action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		xbmcgui.WindowXMLDialog.onAction(self,action)
		
######################################################################################
# Image Dialog
######################################################################################
class ImagesDialog(BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.images = kwargs.get('images')
		self.index = 0
		xbmcgui.WindowXML.__init__( self, *args, **kwargs )
	
	def onInit(self):
		self.getControl(200).setEnabled(len(self.images) > 1)
		self.getControl(202).setEnabled(len(self.images) > 1)
		self.showImage()

	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def showImage(self):
		self.getControl(102).setImage(self.images[self.index])
		
	def nextImage(self):
		self.index += 1
		if self.index >= len(self.images): self.index = 0
		self.showImage()
		
	def prevImage(self):
		self.index -= 1
		if self.index < 0: self.index = len(self.images) - 1
		self.showImage()
	
	def onClick( self, controlID ):
		if BaseWindow.onClick(self, controlID): return
		if controlID == 200:
			self.nextImage()
		elif controlID == 202:
			self.prevImage()
	
	def onAction(self,action):
		if action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		elif action == ACTION_NEXT_ITEM:
			self.nextImage()
		elif action == ACTION_PREV_ITEM:
			self.prevImage()
		xbmcgui.WindowXMLDialog.onAction(self,action)
			
######################################################################################
# Viewer Window
######################################################################################
class ViewerWindow(BaseWindow):
	def __init__( self, *args, **kwargs):
		self.url = kwargs.get('url')
		self.imageReplace = 'IMG #%s'
		self.page = None
		self.history = URLHistory(self.url)
		self.idFilter = re.compile('\[\{(.+?)\}\]',re.S)
		self.linkCTag = '[COLOR %s]' % HC.linkColor
		self.formCTag = '[COLOR %s]' % HC.formColorB
		self.selectedCTag = '[COLOR %s]' % 'FF871203'
		self.selected = None
		self.lastPos = 0
		self.saveDisp = ''
		BaseWindow.__init__( self, *args, **kwargs )
		
	def onInit(self):
		self.pageList = self.getControl(122)
		self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
		self.refresh()
		
	def endProgress(self):
		self.getControl(310).setVisible(False)
		
	def back(self):
		self.url,line = self.history.goBack()
		self.refresh()
		self.pageList.selectItem(line)
		
	def gotoURL(self,url=None):
		if not url:
			url = doKeyboard('Enter URL')
			if not url: return
			if not url.startswith('http://'): url = 'http://' + url
		self.history.addURL(url,old_line=self.pageList.getSelectedPosition())
		self.url = url
		self.refresh()
		
	def refresh(self):
		t = self.getThread(self.getRefreshData,finishedCallback=self.refreshDo)
		t.setArgs(callback=t.progressCallback,donecallback=t.finishedCallback)
		t.start()
		
	def getRefreshData(self,callback=None,donecallback=None):
		page = WR.getWebPage(self.url,callback=callback)
		if not page or not page.isDisplayable():
			callback(100,'Done')
		donecallback(page)
		
	def refreshDo(self,page):
		if not page or not page.isDisplayable():
			return
		self.selected = None
		self.lastPos = 0
		self.saveDisp = ''
		self.page = page
		self.getImages()
		self.getLinks()
		self.displayPage() 
		#self.endProgress()
		
	def selectedType(self,prefix,item):
		if not self.linkCTag in prefix and not self.formCTag in prefix:
			self.selected = item.getProperty('selected')
		return self.selected
		
	def nextLink(self):
		item = self.pageList.getSelectedItem()
		disp = item.getLabel()
		disp_split = disp.split(self.selectedCTag,1)
		if len(disp_split) < 2: return
		if not self.linkCTag in disp_split[1] and not self.formCTag in disp_split[1]: return
		fi = (disp_split[1].find(self.formCTag) + 1) or 999999
		li = (disp_split[1].find(self.linkCTag) + 1) or 999999
		oldtag = self.linkCTag
		if self.selectedType(disp_split[0],item) == 'FORM': oldtag = self.formCTag
		if fi < li:
			self.selected = 'FORM'
			disp = disp_split[0] + oldtag + disp_split[1].replace(self.formCTag,self.selectedCTag,1)
		else:
			self.selected = 'LINK'
			disp = disp_split[0] + oldtag + disp_split[1].replace(self.linkCTag,self.selectedCTag,1)
			
		item.setLabel(disp)
		
	def prevLink(self):
		item = self.pageList.getSelectedItem()
		disp = item.getLabel()
		disp_split = disp.split(self.selectedCTag,1)
		if len(disp_split) < 2: return
		if not self.linkCTag in disp_split[0] and not self.formCTag in disp_split[0]: return
		fi = disp_split[0].rfind(self.formCTag)
		li = disp_split[0].rfind(self.linkCTag)
		oldtag = self.linkCTag
		if self.selectedType(disp_split[0],item) == 'FORM': oldtag = self.formCTag
		if fi > li:
			self.selected = 'FORM'
			disp = self.selectedCTag.join(disp_split[0].rsplit(self.formCTag,1)) +  oldtag + disp_split[1]
		else:
			self.selected = 'LINK'
			disp = self.selectedCTag.join(disp_split[0].rsplit(self.linkCTag,1)) +  oldtag + disp_split[1] 
		item.setLabel(disp)
		
	def currentLink(self):
		item = self.pageList.getSelectedItem()
		disp = item.getLabel()
		tag = self.linkCTag 
		if not self.selectedCTag in disp: return
		prefix,rest = disp.split(self.selectedCTag,1)
		if self.selectedType(prefix,item) == 'FORM': tag = self.formCTag
		count = len(rest.split(tag))
		#ignore, count = re.subn(re.escape(tag),'',rest) #@UnusedVariable
		#count += 1
		if self.selected == 'FORM':
			items = self.page.forms
		else:
			items = self.page.links()
		idx = len(items) - count
		print '%s %s %s' % (idx,count,len(items))
		if count < 0 or count > len(items): return None
		return items[idx]
		
	def displayPage(self):
		disp, title = self.page.forDisplayWithIDs()
		xbmcgui.lock()
		try:
			#import codecs
			#codecs.open('/home/ruuk/test.txt','w',encoding='utf-8').write(disp)
			self.getControl(104).setLabel(title or self.url)
			plist = self.pageList
			plist.reset()
			first = True
			while disp:
				ids = ','.join(self.idFilter.findall(disp))
				fi = (disp.find(self.formCTag) + 1) or 999999
				li = (disp.find(self.linkCTag) + 1) or 999999
				if fi < li:
					selected = 'FORM'
					label = '[CR]' + self.idFilter.sub('',disp).replace(self.formCTag,self.selectedCTag,1)
				else:
					selected = 'LINK'
					label = '[CR]' + self.idFilter.sub('',disp).replace(self.linkCTag,self.selectedCTag,1) 
				if first:
					self.saveDisp = label
					first = False
				item = xbmcgui.ListItem(label=label)
				item.setProperty('selected',selected)
				item.setProperty('ids',ids)
				#re.sub('\[COLOR FF015602\]\[B\](.+?)\[/B\]\[/COLOR\]',r'[COLOR FF871203][B]\1[/B][/COLOR]',disp,1))
				plist.addItem(item)
				if not '[CR]' in disp: break
				disp = disp.split('[CR]',1)[-1]
		finally:
			xbmcgui.unlock()
		if self.page.id: self.gotoID(self.page.id)
		
		
	def getLinks(self):
		ulist = self.getControl(148)
		ulist.reset()
		for link in self.page.links():
			item = xbmcgui.ListItem(link.text or link.url,link.urlShow())
			if link.isImage():
				item.setIconImage(link.fullURL())
			else:
				item.setIconImage('link.png')
			ulist.addItem(item)

	def getImages(self):
		self.getControl(150).reset()
		i=0
		for url in self.page.imageURLs():
			url = fullURL(self.url,url)
			i+=1
			item = xbmcgui.ListItem(self.imageReplace % i,iconImage=url)
			item.setProperty('url',url)
			self.getControl(150).addItem(item)
			
	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onClick( self, controlID ):
		if BaseWindow.onClick(self, controlID): return
		if controlID == 122:
			self.itemSelected()
		elif controlID == 105:
			self.refresh()
		elif controlID == 200:
			self.back()
		elif controlID == 148:
			self.linkSelected()
		elif controlID == 150:
			self.showImage(self.getControl(150).getSelectedItem().getProperty('url'))
			
	def gotoID(self,id):
		id = id.replace('#','')
		plist = self.pageList
		bottom = plist.size()-1
		for i in range((bottom)*-1,1):
			i = abs(i)
			item = plist.getListItem(i)
			ids = item.getProperty('ids')
			#print id,ids
			if id in ids:
				plist.selectItem(i)
				return
			
	def itemSelected(self):
		item = self.currentLink()
		if not item:
			LOG('itemSelected() - No Link')
			return
		if isinstance(item,Link):
			self.linkSelected(item)
		else:
			self.doForm(form=item)
		
	def linkSelected(self,link=None):
		if not link:
			idx = self.getControl(148).getSelectedPosition()
			if idx < 0: return
			links = self.page.links()
			if idx >= len(links): return
			link = links[idx]
		if link.url.startswith('#'):
			self.gotoID(link.url)
			return
		url = link.fullURL()
		if link.isImage():
			self.showImage(url)
		else:
			self.gotoURL(url)
			#base = xbmcgui.Dialog().browse(3,__language__(30144),'files')
			#if not base: return
			#fname,ftype = Downloader(message=__language__(30145)).downloadURL(base,link.url)
			#if not fname: return
			#xbmcgui.Dialog().ok(__language__(30052),__language__(30146),fname,__language__(30147) % ftype)
		
	def showImage(self,url):
		base = os.path.join(__addon__.getAddonInfo('profile'),'imageviewer')
		if not os.path.exists(base): os.makedirs(base)
		clearDirFiles(base)
		image_files = Downloader().downloadURLs(base,[url],'.jpg')
		if not image_files: return
		w = ImagesDialog("script-webviewer-imageviewer.xml" ,__addon__.getAddonInfo('path'),THEME,images=image_files,parent=self)
		w.doModal()
		del w
			
	def selectionChanged(self,pos,last_pos):
		#print last_pos
		if self.saveDisp and self.lastPos > -1: self.pageList.getListItem(last_pos).setLabel(self.saveDisp)
		if pos > -1:
			item = self.pageList.getListItem(pos)
			self.selected = item.getProperty('selected')
			self.saveDisp = item.getLabel()
	
	def onAction(self,action):
		bc = action.getButtonCode()
		#print 'Action: %s  BC: %s' % (action.getId(),bc)
		if self.getFocusId() == 122:
			pos = self.pageList.getSelectedPosition()
			if pos != self.lastPos:
				self.selectionChanged(pos,self.lastPos)
				self.lastPos = pos
		if bc == 61472:
			self.nextLink()
			return
		elif bc == 192544 or action == 61728:
			self.prevLink()
			return
		elif action == ACTION_PARENT_DIR:
			self.back()
			return
		elif action == ACTION_CONTEXT_MENU:
			self.doMenu()
		BaseWindow.onAction(self,action)
		
	def doMenu(self):
		dialog = xbmcgui.Dialog()
		idx = dialog.select('Options',['Forms','Go To URL'])
		if idx == 0: self.doForms()
		elif idx == 1: self.gotoURL()
		
	def doForms(self):
		options = []
		ct = 1
		for f in self.page.forms:
			options.append('Form #%s: %s' % (ct,f.name or f.attrs.get('id')))
			ct += 1
		dialog = xbmcgui.Dialog()
		idx = dialog.select('Forms',options)
		if idx < 0: return
		self.doForm(idx)
		
	def doForm(self,idx=0,form=None):
		if not form:
			ct=0
			for form in self.page.forms:
				if ct == idx: break
				ct += 1
			else:
				return
		
		labels, headers = self.page.labels()
		w = FormDialog("script-webviewer-form.xml" ,__addon__.getAddonInfo('path'),THEME,form=form,labels=labels,headers=headers)
		w.doModal()
		if not w.submit: return
		page = WR.submitForm(w.form,w.submit)
		self.refreshDo(page)
		del w
				
def doKeyboard(prompt,default='',hidden=False):
	keyboard = xbmc.Keyboard(default,prompt)
	keyboard.setHiddenInput(hidden)
	keyboard.doModal()
	if not keyboard.isConfirmed(): return None
	return keyboard.getText()
		
class Downloader:
	def __init__(self,header=__language__(30205),message=''):
		self.message = message
		self.prog = xbmcgui.DialogProgress()
		self.prog.create(header,message)
		self.current = 0
		self.display = ''
		self.file_pct = 0
		
	def progCallback(self,read,total):
		if self.prog.iscanceled(): return False
		pct = ((float(read)/total) * (self.file_pct)) + (self.file_pct * self.current)
		self.prog.update(pct)
		return True
		
	def downloadURLs(self,targetdir,urllist,ext=''):
		file_list = []
		self.total = len(urllist)
		self.file_pct = (100.0/self.total)
		try:
			for url,i in zip(urllist,range(0,self.total)):
				self.current = i
				if self.prog.iscanceled(): break
				self.display = 'File %s of %s' % (i+1,self.total)
				self.prog.update(int((i/float(self.total))*100),self.message,self.display)
				fname = os.path.join(targetdir,str(i) + ext)
				file_list.append(fname)
				self.getUrlFile(url,fname,callback=self.progCallback)
		except:
			ERROR('DOWNLOAD URLS ERROR')
			self.prog.close()
			return None
		self.prog.close()
		return file_list
	
	def downloadURL(self,targetdir,url,fname=None):
		if not fname:
			fname = os.path.basename(urlparse.urlsplit(url)[2])
			if not fname: fname = 'file'
		f,e = os.path.splitext(fname)
		fn = f
		ct=0
		while ct < 1000:
			ct += 1
			path = os.path.join(targetdir,fn + e)
			if not os.path.exists(path): break
			fn = f + str(ct)
		else:
			raise Exception
		
		try:
			self.current = 0
			self.display = __language__(30206) % os.path.basename(path)
			self.prog.update(0,self.message,self.display)
			t,ftype = self.getUrlFile(url,path,callback=self.progCallback) #@UnusedVariable
		except:
			ERROR('DOWNLOAD URL ERROR')
			self.prog.close()
			return (None,'')
		self.prog.close()
		return (os.path.basename(path),ftype)
		
		
			
	def fakeCallback(self,read,total): return True

	def getUrlFile(self,url,target=None,callback=None):
		if not target: return #do something else eventually if we need to
		if not callback: callback = self.fakeCallback
		urlObj = urllib2.urlopen(url)
		size = int(urlObj.info().get("content-length",-1))
		ftype = urlObj.info().get("content-type",'')
		outfile = open(target, 'wb')
		read = 0
		bs = 1024 * 8
		while 1:
			block = urlObj.read(bs)
			if block == "": break
			read += len(block)
			outfile.write(block)
			if not callback(read, size): raise Exception
		outfile.close()
		urlObj.close()
		return (target,ftype)
	
def getWebResult(self,url):
	w = ViewerWindow("script-webviewer-page.xml" , __addon__.getAddonInfo('path'), THEME,url=url)
	w.doModal()
	url = w.page.url
	html = w.page.html
	del w
	return url,html
	
WR = WebReader()
HC = HTMLConverter()

if __name__ == '__main__':
	#start_url = 'http://examples.codecharge.com/ExamplePack/MultiSelectSearch/MultiSelectSearch.php'
	#start_url = 'http://www.tizag.com/phpT/examples/formex.php'
	#start_url = 'http://wiki.xbmc.org'
	start_url='http://www.cs.tut.fi/~jkorpela/forms/file.html'
	w = ViewerWindow("script-webviewer-page.xml" , __addon__.getAddonInfo('path'), THEME,url=start_url)
	w.doModal()
	del w
	sys.modules.clear()
	