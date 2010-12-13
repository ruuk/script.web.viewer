from htmltoxbmc import HTMLConverter
import re, os, sys, time, urllib2, urlparse
import xbmc, xbmcgui, xbmcaddon #@UnresolvedImport
import mechanize, threading

__plugin__ = 'Web Viewer'
__author__ = 'ruuk (Rick Phillips)'
__url__ = 'http://code.google.com/p/webviewer-xbmc/'
__date__ = '12-12-2010'
__version__ = '0.7.0'
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
	print 'FORUMBROWSER - %s::%s (%d) - %s' % (message,sys.exc_info()[2].tb_frame.f_code.co_name, sys.exc_info()[2].tb_lineno, errtext)
	return str(errtext)
	
def LOG(message):
	print 'FORUMBROWSER: %s' % message

def clearDirFiles(filepath):
	if not os.path.exists(filepath): return
	for f in os.listdir(filepath):
		f = os.path.join(filepath,f)
		if os.path.isfile(f): os.remove(f)
		
class WebReader:
	def __init__(self,forum,always_login=False):
		self.browser = mechanize.Browser()
		
	def getWebPage(self,url,callback=None):
		if not callback: callback = self.fakeCallback
		html = self.readURL(url, callback)
		return WebPage(html)
	
	def readURL(self,url,callback):
		response = self.browser.open(url)
		return response.read()
		
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
	def __init__(self,html):
		self.html = html
		
	def forDisplay(self):
		return HC.htmlToDisplay(self.html)
		
	def imageURLs(self):
		return HC.imageFilter.findall(self.html,re.S)
		
	def linkImageURLs(self):
		return re.findall('<a.+?href="(http://.+?\.(?:jpg|png|gif|bmp))".+?</a>',self.html,re.S)
		
	def linkURLs(self):
		return HC.linkFilter.finditer(self.html,re.S)
		
	def links(self):
		links = []
		for m in self.linkURLs(): links.append(Link(m))
		return links

class Link:
	def __init__(self,match=None):
		self.url = ''
		self.text = ''
		self._isImage = False
		
		if match:
			self.url = match.group('url')
			text = match.group('text')
			self.text = HC.tagFilter.sub('',text).strip()
		self.processURL()
			
	def processURL(self):
		if not self.url: return
		self._isImage = re.search('http://.+?\.(?:jpg|png|gif|bmp)',self.url) and True or False
		if self._isImage: return
			
	def urlShow(self):
		return self.url
		
	def isImage(self):
		return self._isImage

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
class ImagesDialog(BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.images = kwargs.get('images')
		self.index = 0
		xbmcgui.WindowXML.__init__( self, *args, **kwargs )
	
	def onInit(self):
		self.setTheme()
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
		BaseWindow.__init__( self, *args, **kwargs )
		
	def onInit(self):
		self.refresh()
		
	def refresh(self):
		self.page = WR.getWebPage(self.url)
		self.getImages()
		self.getLinks()
		self.displayPage()
		
	def displayPage(self):
		self.getControl(122).setText(self.page.forDisplay()) 
		
	def getLinks(self):
		ulist = self.getControl(148)
		for link in self.page.links():
			item = xbmcgui.ListItem(link.text or link.url,link.urlShow())
			if link.isImage():
				item.setIconImage(link.url)
			else:
				item.setIconImage('link.png')
			ulist.addItem(item)

	def getImages(self):
		i=0
		for url in self.page.imageURLs():
			i+=1
			item = xbmcgui.ListItem(self.imageReplace % i,iconImage=url)
			item.setProperty('url',url)
			self.getControl(150).addItem(item)
			
	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onClick( self, controlID ):
		if BaseWindow.onClick(self, controlID): return
		if controlID == 148:
			self.linkSelected()
		elif controlID == 150:
			self.showImage(self.getControl(150).getSelectedItem().getProperty('url'))
	
	def linkSelected(self):
		idx = self.getControl(148).getSelectedPosition()
		if idx < 0: return
		links = self.page.links()
		if idx >= len(links): return
		link = links[idx]
		
		if link.isImage():
			self.showImage(link.url)
		else:
			self.url = link.url
			self.refresh()
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
			
	def onAction(self,action):
		if action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		#elif action == ACTION_CONTEXT_MENU:
		#	self.doMenu()
		BaseWindow.onAction(self,action)
		
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
		
WR = WebReader()
HC = HTMLConverter()

w = ViewerWindow("script-webviewer-page.xml" , __addon__.getAddonInfo('path'), THEME,url='http://www.google.com')
w.doModal()
del w
sys.modules.clear()
	