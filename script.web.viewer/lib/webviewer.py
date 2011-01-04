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
ACTION_PLAYER_FORWARD = 77
ACTION_PLAYER_REWIND  = 78 
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
		
class ResponseData:
	def __init__(self,url='',content='',data='',content_disp=''):
		self.url = url
		self.content = content
		self.contentDisp = content_disp
		self.data = data
		
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
		resData = ResponseData(url)
		id = ''
		urlsplit = url.split('#',1)
		if len(urlsplit) > 1: url,id = urlsplit
		try:
			resData = self.readURL(url, callback)
		except:
			err = ERROR('ERROR READING PAGE')
			LOG('URL: %s' % url)
			xbmcgui.Dialog().ok('ERROR',__language__(30100),err)
			return None
		resData = self.checkRedirect(resData,callback)
		if not callback(80,__language__(30101)): return None
		if not resData: return None
		return WebPage(resData,id=id,forms=resData.data and self.browser.forms() or [])
	
	def checkRedirect(self,resData,callback=None):
		if not callback: callback = self.fakeCallback
		match = re.search('<meta[^>]+?http-equiv="Refresh"[^>]*?URL=(?P<url>[^>"]+?)"[^>]*?/>',resData.data)
		#print html
		if match:
			LOG('REDIRECTING TO %s' % match.group('url'))
			if not callback(3,__language__(30102)): return None
			try:
				url = match.group('url')
				return self.readURL(url, callback)
			except:
				#err = 
				ERROR('ERROR READING PAGE REDIRECT')
				LOG('URL: %s' % url)
				#xbmcgui.Dialog().ok('ERROR','Error loading page.',err)
		return resData
	
	def readURL(self,url,callback):
		if not callback(5,__language__(30103)): return None
		response = self.browser.open(url)
		content = response.info().get('content-type','')
		contentDisp = response.info().get('content-disposition','')
		#print response.info()
		if not content.startswith('text'): return ResponseData(response.geturl(),content,content_disp=contentDisp) 
		if not callback(30,__language__(30104)): return None
		return ResponseData(response.geturl(),content,response.read())
		
	def submitForm(self,form,submit_control,callback):
		if not callback: callback = self.fakeCallback
		self.browser.form = form
		ct = 0
		if submit_control:
			for c in form.controls:
				if c.type == 'submit':
					if c == submit_control: break
					ct += 1 
		if not callback(5,__language__(30105)): return None
		res = self.browser.submit(nr=ct)
		if not callback(60,__language__(30106)): return None
		html = res.read()
		resData = self.checkRedirect(ResponseData(res.geturl(),data=html),callback=callback) #@UnusedVariable
		if not callback(80,__language__(30101)): return None
		if not resData: return None
		return WebPage(resData,self.browser.geturl(),forms=resData.data and self.browser.forms() or [])
		
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
	def __init__(self,resData,id='',forms=[]):
		self.url = resData.url
		self.html = resData.data
		self.content = resData.content
		self.contentDisp = resData.contentDisp
		self.id = id
		self.title = ''
		self.forms = []
		self.imageURLDict = {}
		self._imageCount = -1
		self._labels = None
		self._headers = None
		self._displayWithIDs = ''
		self._display = ''
		self.idFilter = re.compile('\[\{(.+?)\}\]',re.S)
		self.linkCTag = '[COLOR %s]' % HC.linkColor
		self.formCTag = '[COLOR %s]' % HC.formColorB
		self.imageTag = '[COLOR %s]' % HC.imageColor
		self._links = []
		self._images = []
		self.elements = []
		ct = 0
		for f in forms:
			self.forms.append(Form(f,ct))
			ct+=1
		if self.html: self.processPage()
		
	def getFileName(self):
		fn_m = re.search('filename="([^"]*)"',self.contentDisp)
		if not fn_m: return ''
		return fn_m.group(1)
	
	def isDisplayable(self):
		return bool(self.html)
	
	def processPage(self):
		disp = self.forDisplay()
		#import codecs
		#codecs.open('/home/ruuk/test.txt','w',encoding='utf-8').write(disp)
		alltags = '(%s|%s|%s)' % (re.escape(self.linkCTag),re.escape(self.imageTag),re.escape(self.formCTag))
		types = {self.linkCTag:PE_LINK,self.imageTag:PE_IMAGE,self.formCTag:PE_FORM}
		pre = None
		stack = ''
		ct=0
		fct=0
		lct=0
		ict=0
		self.links()
		self.images()
		self.elements = []
		for part in re.split(alltags,disp):
			if pre != None:
				stack += pre
				index = len(stack)
				lines = stack.count('[CR]')
				stack += part
				pre = None
				type = types[part]
				if type == PE_LINK:
					element = self._links[lct]
					lct += 1
				elif type == PE_IMAGE:
					element = self._images[ict]
					ict += 1
				elif type == PE_FORM:
					element = self.forms[fct]
					fct += 1
				element.elementIndex = ct
				element.displayPageIndex = index
				element.lineNumber = lines
				self.elements.append(element)
				ct+=1
			else:
				pre = part
		
	def getNextElementAfterPageIndex(self,index):
		for e in self.elements:
			if e.displayPageIndex >= index:
				return e
			
	def getElementByTypeIndex(self,type,index):
		for e in self.elements:
			if e.typeIndex == index:
				return e
	
	def forDisplay(self):
		if self._display: return self._display
		self.forDisplayWithIDs()
		return self._display
	
	def forDisplayWithIDs(self):
		if self._displayWithIDs: return self._displayWithIDs,self.title
		self._displayWithIDs,self.title = HC.htmlToDisplayWithIDs(self.html)
		self._display = self.idFilter.sub('',self._displayWithIDs)
		return self._displayWithIDs,self.title
		
	def imageCount(self):
		if self._imageCount >= 0: return self._imageCount
		self.imageUrls()
		return self._imageCount()
	
	def images(self):
		if self._images: return self._images
		self.getImageURLDict()
		ct=0
		for url in HC.imageFilter.findall(HC.linkFilter.sub('',self.html),re.S):
			shortIndex = self.imageURLDict.get(url)
			self._images.append(Image(url,ct,shortIndex,base_url=self.url))
			ct+=1
		return self._images
			
	def imageURLs(self):
		urls = []
		ct = 0
		for url in HC.imageFilter.findall(HC.linkFilter.sub('',self.html),re.S):
			for u in urls:
				if u == url: break
			else:
				urls.append(url)
			ct+=1
		self._imageCount = ct
		return urls
		
	def getImageURLDict(self):
		if self.imageURLDict: return self.imageURLDict
		urls = []
		ct=0
		for url in HC.imageFilter.findall(HC.linkFilter.sub('',self.html),re.S):
			urls.append(url)
			if not url in self.imageURLDict:
				self.imageURLDict[url] = ct
				ct+=1
		return self.imageURLDict
		
	def linkImageURLs(self):
		return re.findall('<a.+?href="(http://.+?\.(?:jpg|png|gif|bmp))".+?</a>',self.html,re.S)
		
	def linkURLs(self):
		html = unicode(self.html,'utf8','replace')
		return HC.linkFilter.finditer(HC.cleanHTML(html))
		
	def links(self):
		if self._links: return self._links
		ct = 0
		for m in self.linkURLs():
			self._links.append(Link(m,self.url,ct))
			ct+=1
		return self._links
	
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
				if name == f.form.name: return f
		if action:
			for f in self.forms:
				if action in f.form.action: return f
		if index:
			ct = 0
			for f in self.forms:
				if ct == index: return f
		return None
	
	def getTitle(self):
		return self.title or self.url
		
PE_LINK = 'LINK'
PE_IMAGE = 'IMAGE'
PE_FORM = 'FORM'

class PageElement:
	def __init__(self,type=0,type_index=-1):
		self.typeIndex = type_index
		self.elementIndex = -1
		self.displayPageIndex = -1
		self.lineNumber = -1
		
		self.type = type

class Image(PageElement):
	def __init__(self,url='',image_index=-1,short_index=-1,base_url=''):
		PageElement.__init__(self,PE_IMAGE,image_index)
		self.baseUrl = base_url
		self.url = url
		self.shortIndex = short_index
		
	def fullURL(self):
		return fullURL(self.baseUrl,self.url)
		
class Form(PageElement):
	def __init__(self,form=None,form_index=-1):
		PageElement.__init__(self,PE_FORM,form_index)
		self.form = form
		
class Link(PageElement):
	def __init__(self,match=None,url='',link_index=-1):
		PageElement.__init__(self,PE_LINK,link_index)
		self.baseUrl = url
		self.url = ''
		self.text = ''
		self.image = ''
		self._isImage = False
		
		if match:
			self.url = match.group('url')
			text = match.group('text')
			image_m = HC.imageFilter.search(text)
			if image_m:
				self.image = image_m.group('url')
				alt_m = re.search('alt="([^"]+?)"',image_m.group(0))
				if alt_m: text = alt_m.group(1)
			text = HC.tagFilter.sub('',text).strip()
			self.text = HC.convertHTMLCodes(text)
		self.processURL()
			
	def processURL(self):
		if not self.url: return
		self.url = self.url.replace('&amp;','&')
		self._isImage = bool(re.search('http://.+?\.(?:jpg|png|gif|bmp)',self.url))
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
	def __init__(self,first):
		self.index = 0
		self.history = [first]
		
	def addURL(self,old,new):
		self.history[self.index].copy(old) 
		self.history = self.history[0:self.index+1]
		self.history.append(new)
		self.index = len(self.history) - 1
		
	def gotoIndex(self,index):
		if index < 0 or index >= self.size(): return None
		self.index = index
		return self.history[self.index]
		
	def goBack(self,line):
		self.history[self.index].line = line
		self.index -= 1
		if self.index < 0: self.index = 0
		return self.history[self.index]
	
	def goForward(self,line):
		self.history[self.index].line = line
		self.index += 1
		if self.index >= self.size(): self.index = self.size() - 1
		return self.history[self.index]
		
	def canGoBack(self):
		return self.index > 0
	
	def canGoForward(self):
		return self.index < self.size() - 1
	
	def updateCurrent(self,url,title=None):
		self.history[self.index].url = url
		if title: self.history[self.index].title = title
		
	def size(self):
		return len(self.history)
	
class HistoryLocation:
	def __init__(self,url='',line=0,title=''):
		self.url = url
		self.line = line
		self.title = title
		
	def getTitle(self):
		return self.title or self.url
	
	def copy(self,other):
		if other.url: self.url = other.url
		if other.title: self.title = other.title
		self.line = other.line
		
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
		
	def onClick(self,controlID):
		if controlID == self._stopControl.getId():
			self.stopThread()
			return True
		return False
	
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
				d.create(__language__(30107),__language__(30108))
				d.update(0)
				self.stopThreads()
				if d.iscanceled():
					d.close()
					return True
				d.close()
			return False
		elif action == ACTION_STOP:
			self.stopThread()
			return True
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
		
class BaseWindow(ThreadWindow):
	def __init__( self, *args, **kwargs ):
		self._progMessageSave = ''
		ThreadWindow.__init__(self)
		xbmcgui.WindowXMLDialog.__init__( self, *args, **kwargs )
	
	def onClick( self, controlID ):
		return ThreadWindow.onClick(self,controlID)
			
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

######################################################################################
# Image Dialog
######################################################################################
class ImageDialog(BaseWindow,xbmcgui.WindowXMLDialog):
	def __init__( self, *args, **kwargs ):
		self.image = kwargs.get('image')
		xbmcgui.WindowXML.__init__( self, *args, **kwargs )
	
	def onInit(self):
		self.showImage()

	def onFocus( self, controlId ):
		pass
		
	def showImage(self):
		self.getControl(102).setImage(self.image)
	
	def onClick( self, controlID ):
		pass
	
	def onAction(self,action):
		if action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		xbmcgui.WindowXMLDialog.onAction(self,action)
	
class LineItem:
	def __init__(self,text='',ids='',index=''):
		self.text = text
		self.IDs = ids
		self.index = index
		
class LineView:
	def __init__(self,view,scrollbar=None):
		self.view = view
		self.scrollBar = scrollbar
		if scrollbar:
			self.scrollY = scrollbar.getPosition()[1]
			self.scrollX = scrollbar.getPosition()[0]
			self.scrollSpan = view.getHeight() - scrollbar.getHeight()
		self.items = []
		self.pos = 0
		
	def setScroll(self):
		if not self.scrollBar: return
		y = self.scrollY + int((self.pos / float(self.size())) * self.scrollSpan)
		self.scrollBar.setPosition(self.scrollX,y)
		
	def reset(self):
		self.pos = 0
		self.items = []
		
	def setDisplay(self,text=None):
		if not text: return self.update()
		self.display = text
		self.view.setText(text)
		
	def addItem(self,lineItem):
		self.items.append(lineItem)
		
	def currentItem(self):
		return self.items[self.pos]
	
	def getLineItem(self,pos):
		return self.items[pos]
	
	def setCurrentPos(self,pos):
		if pos < 0 or pos >= len(self.items): return
		self.pos = pos
		self.setScroll()
		
	def update(self):
		if not self.items:
			LOG('LineView update() - No Items')
			return
		self.view.setText(self.items[self.pos].text)
		self.setScroll()
		
	def getSelectedPosition(self):
		return self.pos
	
	def moveUp(self):
		self.pos -= 1
		if self.pos < 0: self.pos = 0
		self.setScroll()
		return self.pos
	
	def moveDown(self):
		self.pos += 1
		if self.pos >= self.size(): self.pos = self.size() - 1
		self.setScroll()
		return self.pos
	
	def size(self):
		return len(self.items)
	
	def selectItem(self,pos): return self.setCurrentPos(pos)
	def getListItem(self,pos): return self.getLineItem(pos)
			
######################################################################################
# Viewer Window
######################################################################################
class ViewerWindow(BaseWindow):
	IS_DIALOG = False
	def __init__( self, *args, **kwargs):
		self.url = kwargs.get('url')
		self.autoForms = kwargs.get('autoForms',[])
		
		self.first = True
		
		self.imageReplace = 'IMG #%s'
		self.page = None
		self.history = URLHistory(HistoryLocation(self.url))
		self.line = 0
		self.idFilter = re.compile('\[\{(.+?)\}\]',re.S)
		self.linkCTag = '[COLOR %s]' % HC.linkColor
		self.formCTag = '[COLOR %s]' % HC.formColorB
		self.imageTag = '[COLOR %s]' % HC.imageColor
		self.cTags = {PE_FORM:self.formCTag,PE_LINK:self.linkCTag,PE_IMAGE:self.imageTag}
		self.selectedCTag = '[COLOR %s]' % 'FFFE1203'
		self.preface = '[CR]'
		self.selected = None
		self.lastPos = 0
		self.linkLastPos = 0
		self.baseDisplay = ''
		self.form = None
		self.currentElementIndex = 0
		self.formFocused = False
		self.bmManger = BookmarksManager(os.path.join(xbmc.translatePath(__addon__.getAddonInfo('profile')),'bookmarks'))
		BaseWindow.__init__( self, *args, **kwargs )
		
	def onInit(self):
		if not self.first: return
		self.first = False
		#self.pageList = self.getControl(122)
		self.pageList = LineView(self.getControl(123),self.getControl(124))
		self.controlList = self.getControl(120)
		self.linkList = self.getControl(148)
		self.imageList = self.getControl(150)
		self.setStopControl(self.getControl(106))
		self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
		self.setHistoryControls()
		self.refresh()
		
	def endProgress(self):
		self.getControl(310).setVisible(False)
		
	def back(self):
		if not self.history.canGoBack(): return
		hloc = self.history.goBack(self.pageList.getSelectedPosition())
		self.gotoHistory(hloc)

	def forward(self):
		if not self.history.canGoForward(): return
		hloc = self.history.goForward(self.pageList.getSelectedPosition())
		self.gotoHistory(hloc)
		
	def gotoHistory(self,hloc):
		self.url = hloc.url
		self.line = hloc.line
		self.setHistoryControls()
		self.refresh()
		
	def gotoURL(self,url=None):
		if not url:
			url = doKeyboard(__language__(30111))
			if not url: return
			if not url.startswith('http://'): url = 'http://' + url
		old = HistoryLocation(self.page and self.page.url or self.url,self.pageList.getSelectedPosition())
		new = HistoryLocation(url)
		self.history.addURL(old,new)
		self.url = url
		self.line = 0
		self.setHistoryControls()
		self.refresh()
		
	def setHistoryControls(self):
		self.getControl(200).setVisible(self.history.canGoBack())
		self.getControl(202).setVisible(self.history.canGoForward())
		
	def viewHistory(self):
		options = []
		ct=0
		for h in self.history.history:
			t = h.getTitle()
			if ct == self.history.index: t = '[ %s ]' % t
			else: t = '  ' + t 
			options.append(t)
			ct+=1
		dialog = xbmcgui.Dialog()
		idx = dialog.select(__language__(30112),options)
		if idx < 0: return
		if idx == self.history.index: return
		hloc = self.history.gotoIndex(idx)
		if not hloc: return
		self.gotoHistory(hloc)
		
		
	def refresh(self):
		t = self.getThread(self.getRefreshData,finishedCallback=self.refreshDo)
		t.setArgs(callback=t.progressCallback,donecallback=t.finishedCallback)
		t.start()
		
	def getRefreshData(self,callback=None,donecallback=None):
		page = WR.getWebPage(self.url,callback=callback)
		if not page or not page.isDisplayable():
			callback(100,__language__(30109))
		donecallback(page)
		
	def refreshDo(self,page):
		if not page or not page.isDisplayable():
			if page and not page.isDisplayable():
				if xbmcgui.Dialog().yesno(__language__(30113),__language__(30114),page.getFileName(),__language__(30115) % page.content):
					self.downloadLink(page.url,page.getFileName())
			return
		self.selected = None
		self.lastPos = 0
		self.page = page
		xbmcgui.lock()
		try:
			self.hideLists()
			self.getImages()
			self.getLinks()
		finally:
			xbmcgui.unlock()
		self.displayPage() 
		#self.endProgress()
	
	LINE_COUNT = 28
	CHAR_PER_LINE = 70
	def pageUp(self):
		pos = self.pageList.getSelectedPosition()
		ct = 0
		i=-1
		for i in range(pos*-1,1):
			i = abs(i)
			item = self.pageList.getListItem(i)
			line = item.text.split('[CR]',1)[0]
			ct += (len(line) / self.CHAR_PER_LINE) or 1
			if ct >= self.LINE_COUNT: break
		if i: i+=1
		if i > pos: i=pos
		self.pageList.selectItem(i)
		self.refreshFocus()
	
	def pageDown(self):
		pos = self.pageList.getSelectedPosition()
		max = self.pageList.size()
		ct = 0
		for i in range(pos,max):
			item = self.pageList.getListItem(i)
			line = item.text.split('[CR]',1)[0]
			ct += (len(line) / self.CHAR_PER_LINE) or 1
			if ct >= self.LINE_COUNT: break
		else:
			return
		i-=1
		if i < 0: i=0
		if i > max: return
		self.pageList.selectItem(i)
		self.refreshFocus()
		
	def refreshFocus(self):
		xbmc.executebuiltin('ACTION(highlight)')
	
	def prevElement(self):
		self.currentElementIndex -= 1
		if self.currentElementIndex < 0: self.currentElementIndex = len(self.page.elements) - 1
		self.selectElement()
		
	def nextElement(self):
		self.currentElementIndex += 1
		if self.currentElementIndex >= len(self.page.elements): self.currentElementIndex = 0
		self.selectElement()
		
	def selectElement(self,element=None):
		if element: self.currentElementIndex = element.elementIndex
		xbmcgui.lock()
		try:
			element = self.currentElement()
			itemIndex = self.pageList.getSelectedPosition()
			if itemIndex != element.lineNumber:
				#index = self.currentElementIndex
				self.lastPos = element.lineNumber
				self.pageList.selectItem(element.lineNumber)
				#self.currentElementIndex = index
			item = self.pageList.getListItem(element.lineNumber)
			disp = item.text
			index = element.displayPageIndex+len(self.preface) - item.index
			#print self.currentElementIndex
			#print '%s %s %s' % (index,element.displayPageIndex,item.index)
			one = disp[0:index]
			two = disp[index:].replace(self.cTags[element.type],self.selectedCTag,1)
			# two[:100]
			self.pageList.setDisplay(one + two)
			#item.setProperty('selected',element.type)
			self.elementChanged()
		finally:
			xbmcgui.unlock()
	
	def currentElement(self):
		if not self.page: return None
		if self.currentElementIndex < 0 or self.currentElementIndex >= len(self.page.elements): return None
		return self.page.elements[self.currentElementIndex]
	
	def elementChanged(self):
		element = self.currentElement()
		if not element: return
		try:
			xbmcgui.lock()
			if element.type == PE_LINK:
				self.linkList.selectItem(element.typeIndex)
				self.controlList.setVisible(False)
				self.imageList.setVisible(False)
				self.linkList.setVisible(True)
			elif element.type == PE_IMAGE:
				self.imageList.selectItem(element.shortIndex)
				self.linkList.setVisible(False)
				self.controlList.setVisible(False)
				self.imageList.setVisible(True)
			else:
				self.showForm(element.form)
				self.linkList.setVisible(False)
				self.imageList.setVisible(False)
				self.controlList.setVisible(True)
		finally:
			xbmcgui.unlock()
	
	def hideLists(self):
		self.linkList.setVisible(False)
		self.imageList.setVisible(False)
		self.controlList.setVisible(False)
		
	def addLabel(self,text):
		item = xbmcgui.ListItem(label=text)
		item.setInfo('video',{'Genre':'label'})
		item.setProperty('index','-1')
		self.controlList.addItem(item)
		
	def showForm(self,form):
		self.form = form
		self.controlList.reset()
		labels, headers = self.page.labels()
		idx = 0
		trail = False
		notrail = True
		for c in form.controls:
			if c.type != 'hidden':
				label = labels.get(c.id) or labels.get(c.name) or c.name or c.type.title()
				header = headers.get(c.id) or headers.get(c.name)
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
						label = __language__(30116)
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
	
	def getFormControl(self,item):
		idx = item.getProperty('index')
		try:
			idx = int(idx)
		except:
			print 'error',idx
			return None
		if idx < 0: return None
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
			self.submitForm(control)
			return
		elif ctype == 'file':
			fname = xbmcgui.Dialog().browse(1,__language__(30117),'files')
			control.add_file(open(fname,'r'),filename=os.path.basename(fname))
			item.setLabel(fname)
			
	
	def doSelect(self,control,item):
		options = []
		for i in control.items:
			if i.disabled:
				cb = ''
			else:
				cb = i.selected and unichr(0x2611) or unichr(0x2610)
			options.append(cb + ' ' + unicode(i.attrs.get('label',i.name) or i.name,'utf8','replace'))
			#options.append(i.attrs.get('label',i.name) or i.name)
		dialog = xbmcgui.Dialog()
		idx = dialog.select(__language__(30118),options)
		if idx < 0: return False
		i = control.items[idx]
		if not i.disabled:
			i.selected = not i.selected
		if control.multiple:
			ct = 0
			for i in control.items:
				if i.selected: ct += 1
			if ct:
				label = __language__(30119) % ct
			else:
				label = __language__(30116)
		else:
			value = control.value[0]
			citem = control.get(value)
			label = citem.attrs.get('label',value)
		item.setLabel(label)
		return True
		
	def displayPage(self):
		disp, title = self.page.forDisplayWithIDs()
		self.baseDisplay = disp
		xbmcgui.lock()
		self.hideLists()
		self.history.updateCurrent(self.page.url,title)
		try:
			#import codecs
			#codecs.open('/home/ruuk/test.txt','w',encoding='utf-8').write(disp)
			self.getControl(104).setLabel(title or self.url)
			self.getControl(108).setLabel(self.page.url)
			favicon = 'http://' + urlparse.urlparse(self.page.url)[1] + '/favicon.ico'
			#print favicon
			self.getControl(102).setImage(favicon)
			plist = self.pageList
			plist.reset()
			index = 0
			while disp:
				ids = ','.join(self.idFilter.findall(disp))
				label = self.preface + '[CR]'.join(self.idFilter.sub('',disp).split('[CR]')[:35])
				item = LineItem(label,ids,index)
				plist.addItem(item)
				if not '[CR]' in disp: break
				old,disp = disp.split('[CR]',1)
				index += len(self.idFilter.sub('',old)) + 4
			plist.update()
		finally:
			xbmcgui.unlock()
		self.currentElementIndex = 0
		if self.line:
			self.pageList.selectItem(self.line)
		elif self.page.id:
			self.gotoID(self.page.id)
		
		self.selectionChanged(self.pageList.getSelectedPosition(), -1)
		for fd in self.autoForms:
			f = self.page.getForm(name=fd.get('name'),action=fd.get('action'),index=fd.get('index'))
			if f:
				self.selectElement(f)
				xbmc.executebuiltin('ACTION(select)')
				#self.setFocus(self.controlList)
				#self.showForm(f.form)
				break
		
		
	def getLinks(self):
		ulist = self.getControl(148)
		ulist.reset()
		for link in self.page.links():
			item = xbmcgui.ListItem(link.text or link.url,link.urlShow())
			if link.isImage():
				item.setIconImage(link.fullURL())
			elif link.image:
				item.setIconImage(link.image)
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
		elif controlID == 120:
			self.doControl()
		elif controlID == 105:
			self.refresh()
		elif controlID == 200:
			self.back()
		elif controlID == 202:
			self.forward()
		elif controlID == 148:
			self.linkSelected()
		elif controlID == 150:
			self.showImage(self.getControl(150).getSelectedItem().getProperty('url'))
		elif controlID == 109:
			self.gotoURL()
			
	def gotoID(self,id):
		id = id.replace('#','')
		plist = self.pageList
		bottom = plist.size()-1
		for i in range((bottom)*-1,1):
			i = abs(i)
			item = plist.getListItem(i)
			ids = item.IDs
			#print id,ids
			if id in ids:
				plist.selectItem(i)
				return
			
	def itemSelected(self):
		element = self.currentElement()
		if not element:
			LOG('elementSelected() - No Element')
			return
		if element.type == PE_LINK:
			self.linkSelected(element)
		elif element.type == PE_IMAGE:
			self.formFocused = True
			self.setFocusId(150)
		else:
			self.formFocused = True
			self.setFocusId(120)
			#self.doForm(form=item)
		
	def linkSelected(self,link=None):
		if not link:
			link = self.currentElement()
		if not link.type == PE_LINK: return
		
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
		base = os.path.join(xbmc.translatePath(__addon__.getAddonInfo('profile')),'imageviewer')
		if not os.path.exists(base): os.makedirs(base)
		clearDirFiles(base)
		image_files = Downloader().downloadURLs(base,[url],'.jpg',opener=WR.browser.open_novisit)
		if not image_files: return
		if self.IS_DIALOG:
			w = ImageDialog("script-webviewer-imageviewer.xml" ,__addon__.getAddonInfo('path'),THEME,image=image_files[0],parent=self)
			w.doModal()
			del w
		else:
			xbmc.executebuiltin('SlideShow(%s)' % base)
	
	def selectLinkByIndex(self,idx):
		element = self.page.getElementByTypeIndex(PE_LINK,idx)
		if not element: return
		self.currentElementIndex = element.elementIndex
		self.selectElement()
	
	def linkSelectionChanged(self,pos,last_pos):
		if pos < 0: return
		self.selectLinkByIndex(pos)
	
	def selectionChanged(self,pos,last_pos):
		#print '%s %s' % (pos,last_pos)
		if pos > -1 and pos < self.pageList.size():
			item = self.pageList.getListItem(pos)
			index = item.index
			element = self.page.getNextElementAfterPageIndex(index)
			if not element: return
			self.currentElementIndex = element.elementIndex
			self.selectItemFirstElement(item)
			
	def selectItemFirstElement(self,item):
		disp = item.text
		element = self.currentElement()
		index = element.displayPageIndex+len(self.preface) - item.index
		disp = disp[0:index] + disp[index:].replace(self.cTags[element.type],self.selectedCTag,1)
		try:
			xbmcgui.lock()
			self.pageList.setDisplay(disp)
			self.elementChanged()
		finally:
			xbmcgui.unlock()
	
	def bookmarks(self):
		options = [__language__(30120),__language__(30121),'-                         -']
		for bm in self.bmManger.bookmarks: options.append(bm.title)
		dialog = xbmcgui.Dialog()
		idx = dialog.select(__language__(30122),options)
		if idx < 0: return
		if idx == 0:
			title = doKeyboard(__language__(30123),default=self.page.title)
			if title == None: title = self.page.title
			self.bmManger.addBookmark(Bookmark(title,self.page.url))
		elif idx == 1: self.manageBookmarks()
		elif idx == 2: pass
		else:
			idx -= 3
			bm = self.bmManger.getBookmark(idx)
			self.gotoURL(bm.url)
	
	def manageBookmarks(self):
		while 1:
			options = []
			for bm in self.bmManger.bookmarks: options.append(bm.title)
			dialog = xbmcgui.Dialog()
			idx = dialog.select(__language__(30124),options)
			if idx < 0: return
			if xbmcgui.Dialog().yesno(__language__(30125),__language__(30126),__language__(30127) % self.bmManger.getBookmark(idx).title):
				self.bmManger.removeBookmark(idx)
	
	def onAction(self,action):
		#print action.getId()
		#check for exit so errors won't prevent it
		if action == ACTION_PREVIOUS_MENU:
			if self.getFocusId() == 122:
				if action.getButtonCode():
					#Escape was pressed
					BaseWindow.onAction(self,action)
					return
				else:
					#This was a mouse right click on our overlay button
					action = ACTION_CONTEXT_MENU
			else:
				BaseWindow.onAction(self,action)
				return
					
		#if self.getFocusId() == 122:	
		if self.getFocusId() == 148:
			pos = self.linkList.getSelectedPosition()
			if pos != self.linkLastPos:
				self.linkSelectionChanged(pos,self.linkLastPos)
				self.linkLastPos = pos
			elif action == ACTION_CONTEXT_MENU:
				self.doMenu(PE_LINK)
		elif self.getFocusId() == 150:
			if action == ACTION_CONTEXT_MENU:
				self.doMenu(PE_IMAGE)
		elif self.getFocusId() == 120:
			if action == ACTION_CONTEXT_MENU:
				self.doMenu(PE_FORM)
		else:
			pos = self.pageList.getSelectedPosition()
			if pos != self.lastPos:
				self.selectionChanged(pos,self.lastPos)
				self.lastPos = pos
			if action == ACTION_MOVE_RIGHT:
				if not self.formFocused: self.nextElement()
				self.formFocused = False
				#self.nextLink()
				return
			elif action == ACTION_MOVE_LEFT:
				if not self.formFocused:  self.prevElement()
				self.formFocused = False
				return
			if action == ACTION_MOVE_UP or action == 104:
				pos = self.pageList.moveUp()
				self.selectionChanged(pos,self.lastPos)
				self.lastPos = pos
				return
			elif action == ACTION_MOVE_DOWN  or action == 105:
				pos = self.pageList.moveDown()
				self.selectionChanged(pos,self.lastPos)
				self.lastPos = pos
				return
			elif action == ACTION_PAGE_UP or action == ACTION_PREV_ITEM:
				self.pageUp()
				return
			elif action == ACTION_PAGE_DOWN or action == ACTION_NEXT_ITEM:
				self.pageDown()
				return
			elif action == ACTION_CONTEXT_MENU:
				self.doMenu()
				return	
			
		if action == ACTION_PARENT_DIR or action == ACTION_PLAYER_REWIND:
			self.back()
			return
		elif action == ACTION_PLAYER_FORWARD:
			self.forward()
			return
		elif action == ACTION_PAUSE:
			self.viewHistory()
			return
		
		BaseWindow.onAction(self,action)
		
	def downloadLink(self,url,fname=None):
		base = xbmcgui.Dialog().browse(3,__language__(30128),'files')
		if not base: return
		fname,ftype = Downloader(message=__language__(30129)).downloadURL(base,url,fname,open=WR.browser.open)
		if not fname: return
		xbmcgui.Dialog().ok(__language__(30109),__language__(30130),fname,__language__(30115) % ftype)
		
	def doMenu(self,etype=None):
		element = self.currentElement()
		if element and not etype: etype = element.type
		
		#populate options
		options = [__language__(30131),__language__(30132),__language__(30133)]
		if etype == PE_LINK:
			options += [__language__(30134),__language__(30135)]
			if element.image: options.append(__language__(30136))
			if element.isImage(): options.append(__language__(30137))
		elif etype == PE_IMAGE: options += [__language__(30138),__language__(30139)]
		elif etype == PE_FORM: options.append(__language__(30140))
		
		#do dialog/handle common
		dialog = xbmcgui.Dialog()
		idx = dialog.select(__language__(30110),options)
		if idx < 0: return
		elif idx == 0: self.gotoURL()
		elif idx == 1: self.bookmarks()
		elif idx == 2: self.settings()
		
		#handle contextual options
		if etype == PE_LINK:
			if idx == 3: self.linkSelected()
			elif idx == 4: self.downloadLink(element.fullURL())
			elif options[idx] == __language__(30136): self.showImage(fullURL(self.url,element.image))
			elif options[idx] == __language__(30137): self.showImage(element.fullURL())
		elif etype == PE_IMAGE:
			if idx == 3: self.showImage(element.fullURL())
			elif idx == 4: self.downloadLink(element.fullURL())
		elif etype == PE_FORM:
			if idx == 4: self.submitForm(None)		
		
	def settings(self):
		dialog = xbmcgui.Dialog()
		idx = dialog.select(__language__(30110),[__language__(30141),__language__(30142)])
		if idx < 0: return
		
		if idx == 0:
			__addon__.openSettings()
		elif idx == 1:
			setHome(self.page.url)
			xbmcgui.Dialog().ok(__language__(30109),__language__(30143),self.page.getTitle())
	
	def submitForm(self,control):
		self.startProgress()
		page = WR.submitForm(self.form,control,callback=self.setProgress)
		if not page:
			LOG('submitForm() Failure')
			return
		old = HistoryLocation(self.page and self.page.url or self.url,self.pageList.getSelectedPosition())
		new = HistoryLocation(page.url)
		self.history.addURL(old, new)
		self.refreshDo(page)
		self.endProgress()
		self.setFocusId(122)
				
#	def doForms(self):
#		options = []
#		ct = 1
#		for f in self.page.forms:
#			options.append('Form #%s: %s' % (ct,f.form.name or f.form.attrs.get('id')))
#			ct += 1
#		dialog = xbmcgui.Dialog()
#		idx = dialog.select('Forms',options)
#		if idx < 0: return
#		self.doForm(idx)

class ViewerWindowDialog(ViewerWindow,xbmcgui.WindowXMLDialog): IS_DIALOG = True
class ViewerWindowNormal(ViewerWindow,xbmcgui.WindowXML): pass

class BookmarksManager:
	def __init__(self,file=''):
		self.file = file
		self.bookmarks = []
		self.load()
		
	def addBookmark(self,bookmark):
		self.bookmarks.append(bookmark)
		self.save()
		
	def removeBookmark(self,index):
		del self.bookmarks[index]
		self.save()
		
	def getBookmark(self,index):
		return self.bookmarks[index]
	
	def save(self):
		out = ''
		for bm in self.bookmarks:
			out += bm.toString() + '\n'
		bf = open(self.file,'w')
		bf.write(out)
		bf.close()
			
		
	def load(self):
		if not os.path.exists(self.file): return
		bf = open(self.file,'r')
		lines = bf.read().splitlines()
		bf.close()
		self.bookmarks = []
		for line in lines:
			self.addBookmark(Bookmark().fromString(line))
		
class Bookmark:
	def __init__(self,title='',url=''):
		self.title = title
		self.url = url
		
	def toString(self):
		return '%s:=:%s' % (self.title,self.url)
	
	def fromString(self,string):
		if ':=:' in string: self.title,self.url = string.split(':=:',1)
		return self
	
class Downloader:
	def __init__(self,header=__language__(30129),message=''):
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
		
	def downloadURLs(self,targetdir,urllist,ext='',opener=urllib2.urlopen):
		file_list = []
		self.total = len(urllist)
		self.file_pct = (100.0/self.total)
		try:
			for url,i in zip(urllist,range(0,self.total)):
				self.current = i
				if self.prog.iscanceled(): break
				self.display = __language__(30144) % (i+1,self.total)
				self.prog.update(int((i/float(self.total))*100),self.message,self.display)
				fname = os.path.join(targetdir,str(i) + ext)
				file_list.append(fname)
				self.getUrlFile(url,fname,callback=self.progCallback,opener=opener)
		except:
			ERROR('DOWNLOAD URLS ERROR: %s' % url)
			self.prog.close()
			return None
		self.prog.close()
		return file_list
	
	def downloadURL(self,targetdir,url,fname=None,opener=urllib2.urlopen):
		if not fname:
			fname = os.path.basename(urlparse.urlsplit(url)[2])
			if not fname: fname = 'file'
		f,e = os.path.splitext(fname)
		fn = f
		ct=1
		while ct < 1000:
			ct += 1
			path = os.path.join(targetdir,fn + e)
			if not os.path.exists(path): break
			fn = f + '(%s)' % str(ct)
		else:
			raise Exception
		
		try:
			self.current = 0
			self.display = __language__(30145) % os.path.basename(path)
			self.prog.update(0,self.message,self.display)
			t,ftype = self.getUrlFile(url,path,callback=self.progCallback,opener=opener) #@UnusedVariable
		except:
			ERROR('DOWNLOAD URL ERROR: %s' % url)
			self.prog.close()
			return (None,'')
		self.prog.close()
		return (os.path.basename(path),ftype)
		
		
			
	def fakeCallback(self,read,total): return True

	def getUrlFile(self,url,target=None,callback=None,opener=urllib2.urlopen):
		if not target: return #do something else eventually if we need to
		if not callback: callback = self.fakeCallback
		urlObj = opener(url)
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

def doKeyboard(prompt,default='',hidden=False):
	keyboard = xbmc.Keyboard(default,prompt)
	keyboard.setHiddenInput(hidden)
	keyboard.doModal()
	if not keyboard.isConfirmed(): return None
	return keyboard.getText()

def getWebResult(url,autoForms=[],dialog=False):
	if dialog:
		w = ViewerWindowDialog("script-webviewer-page.xml" , __addon__.getAddonInfo('path'), THEME,url=url,autoForms=autoForms)
	else:
		w = ViewerWindowNormal("script-webviewer-page.xml" , __addon__.getAddonInfo('path'), THEME,url=url,autoForms=autoForms)
	w.doModal()
	url = w.page.url
	html = w.page.html
	del w
	return url,html
	
def setHome(url):
	__addon__.setSetting('home_page',url)
		
def getHome():
	return __addon__.getSetting('home_page')
	
WR = WebReader()
HC = HTMLConverter()

if __name__ == '__main__':
	#start_url = 'http://examples.codecharge.com/ExamplePack/MultiSelectSearch/MultiSelectSearch.php'
	#start_url = 'http://www.tizag.com/phpT/examples/formex.php'
	#start_url = 'http://forum.xbmc.org'
	#start_url='http://www.cs.tut.fi/~jkorpela/forms/file.html'
	start_url = getHome() or 'http://wiki.xbmc.org/index.php?title=XBMC_Online_Manual'
	w = ViewerWindowNormal("script-webviewer-page.xml" , __addon__.getAddonInfo('path'), THEME,url=start_url)
	w.doModal()
	del w
	sys.modules.clear()
	