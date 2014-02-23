import urllib, urllib2,re, sys, os, ast
import xbmc, xbmcaddon #@UnresolvedImport
from htmltoxbmc import convertHTMLCodes

def LOG(text):
	print 'WEBVIEWER: %s' % text
	
def ERROR(message):
	errtext = sys.exc_info()[1]
	print 'WEBVIEWER - %s::%s (%d) - %s' % (message, sys.exc_info()[2].tb_frame.f_code.co_name, sys.exc_info()[2].tb_lineno, errtext)
#	import traceback
#	traceback.print_exc()
	return str(errtext)
try:
	import youtube_dl
except:
	ERROR('Failded to import youtube-dl')
	youtube_dl = None

def getVideoInfo(url):
	return WebVideo().getVideoObject(url)
	
def getVideoPlayable(sourceName,ID):
	if sourceName == 'Vimeo':
		return WebVideo().getVimeoFLV(ID)
	elif sourceName == 'YouTube':
		return WebVideo().getYoutubePluginURL(ID)
	
YTDL = None
DISABLE_DASH_VIDEO = True

class Video():
	def __init__(self,ID=None):
		self.ID = ID
		self.thumbnail = ''
		self.swf = ''
		self.media = ''
		self.embed = ''
		self.page = ''
		self.playable = ''
		self.allPlayable = None
		self.title = ''
		self.sourceName = ''
		self.playableCallback = None
		self.isVideo = True
		
	def playableURL(self):
		return self.playable or self.media
	
	def hasMultiplePlayable(self):
		if not self.allPlayable: return False
		if len(self.allPlayable) > 1: return True
		return False
		
	def getPlayableURL(self):
		if not self.playableCallback: return self.playableURL()
		url = self.playableCallback(self.ID)
		LOG('Video URL: ' + url)
		return url
		
class WebVideo():
	alphabetB58 = '123456789abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ'
	countB58 = len(alphabetB58)
	
	def __init__(self):
		self.modules = {}
		
	def getVideoObject(self,url,just_test=False,just_ID=False,quality=1):
		try:
			video = getYoutubeDLVideo(url,quality)
			if not video: return None
		except:
			ERROR('getYoutubeDLVideo() failed')
			return None
		return video
		if 'youtu.be' in url or 'youtube.com' in url:
			if just_test: return True
			ID = self.extractYoutubeIDFromURL(url)
			if not ID: return None
			if just_ID: return ID
			video = Video(ID)
			video.sourceName = 'YouTube'
			video.thumbnail = self.getYoutubeThumbURL(ID)
			video.playable = self.getYoutubePluginURL(ID)
			video.swf = self.getYoutubeSWFUrl(ID)
		elif 'vimeo.com' in url:
			if just_test: return True
			ID = self.extractVimeoIDFromURL(url)
			if not ID: return None
			if just_ID: return ID
			video = Video(ID)
			video.sourceName = 'Vimeo'
			info = self.getVimeoInfo(ID)
			if not info: return None
			video.thumbnail = info.get('thumbnail','')
			video.title = info.get('title','')
			#video.playableCallback = self.getVimeoFLV
			video.playable = self.getVimeoPluginURL(ID)
			video.isVideo = True
		elif 'dailymotion.com/' in url:
			if just_test: return True
			ID = self.extractDailymotionIDFromURL(url)
			if not ID: return None
			if just_ID: return ID
			video = Video(ID)
			video.sourceName = 'Dailymotion'
			info = self.getDailymotionInfo(ID)
			if not info: return None
			video.thumbnail = info.get('thumbnail','')
			video.title = info.get('title','')
			video.playable = self.getDailymotionPluginURL(ID)
			video.isVideo = True
		elif 'metacafe.com/' in url:
			if just_test: return True
			ID = self.extractMetacafeIDFromURL(url)
			if not ID: return None
			if just_ID: return ID
			video = Video(ID)
			video.sourceName = 'Metacafe'
			info = self.getMetacafeInfo(ID)
			if not info: return None
			video.thumbnail = info.get('thumbnail','')
			video.title = info.get('title','')
			video.playable = info.get('video','')
			if not video.playable: video.playable = 'plugin://plugin.video.metacafe/video/%s' % ID
			if ID.startswith('cb-'):
				if xbmc.getCondVisibility('System.HasAddon(plugin.video.free.cable)'):
					video.playable = 'plugin://plugin.video.free.cable/?url="%s"&mode="cbs"&sitemode="play"' % ID[3:]
			video.isVideo = bool(video.playable)
		elif 'flic.kr/' in url or 'flickr.com/' in url:
			if just_test: return True
			ID = self.getFlickrIDFromURL(url)
			if not ID: return None
			if just_ID: return ID
			info = self.getFlickrInfo(ID)
			if not info: return None
			video = Video(ID)
			video.sourceName = 'flickr'
			video.thumbnail = info.get('thumbnail','')
			video.title = info.get('title','')
			if not info.get('type') == 'video':
				video.isVideo = False
				return video
			video.playable = self.getFlickrPluginURL(ID)
		else:
			try:
				video = getYoutubeDLVideo(url)
				if not video: return None
			except:
				ERROR('getYoutubeDLVideo() failed')
				return None
			
		LOG('Video ID: ' + video.ID)
		return video
	
	def mightBeVideo(self,url):
		ytdl = getYTDL()
		for ies in ytdl._ies:
			if ies.suitable(url) and ies.IE_NAME != 'generic':
				return True
		return False
		#return self.getVideoObject(url, just_test=True)
	
	def getFlickrPluginURL(self,ID):
		return 'plugin://plugin.image.flickr/?video_id=' + ID
	
	def getYoutubePluginURL(self,ID):
		return 'plugin://plugin.video.youtube/?path=/root/video&action=play_video&videoid=' + ID
			
	def getVimeoPluginURL(self,ID):
		return 'plugin://plugin.video.vimeo/?path=/root/video&action=play_video&videoid=' + ID
	
	def getDailymotionPluginURL(self,ID):
		return 'plugin://plugin.video.dailymotion_com/?mode=playVideo&url=' + ID
	
	def getYoutubeThumbURL(self,ID):
		return 'http://i1.ytimg.com/vi/%s/0.jpg' % ID
	
	def getYoutubeSWFUrl(self,ID):
		return 'http://www.youtube.com/v/' + ID
		
	def extractDailymotionIDFromURL(self,url):
		#http://www.dailymotion.com/video/xy0sej_duck-dynasty-martin-s-pet-lizard_tech?search_algo=2#.UT-Ga2Q-v8Y
		m = re.search('/video/(\w+?)_',url)
		if m: return m.group(1)
		
	def extractMetacafeIDFromURL(self,url):
		#http://www.metacafe.com/watch/10061205/stumble_through_yoostar_with_harley_morenstein_and_cousin_dave_from_epic_meal_time/
		m = re.search('/watch/([\w-]+?)/',url)
		if m: return m.group(1)
		
	def extractYoutubeIDFromURL(self,url):
		if '//youtu.be' in url:
			#http://youtu.be/sSMbOuNBV0s
			sp = url.split('.be/',1)
			if len(sp) == 2: return sp[1]
			return ''
		elif 'youtube.com' in url:
			#http://www.youtube.com/watch?v=MuLDUws0Zh8&feature=autoshare
			ID = url.split('v=',1)[-1].split('&',1)[0]
			if 'youtube.com' in ID:
				ID = url.split('/v/',1)[-1].split('&',1)[0].split('?',1)[0]
			if 'youtube.com' in ID: return ''
			return ID
	
	def getFlickrIDFromURL(self,url):
		#try:
		#	longURL = urllib2.urlopen(url).geturl()
		#except:
		#	return ''
		#if longURL.endswith('/'): longURL = longURL[:-1]
		#return longURL.rsplit('/',1)[-1]
		end = url.split('://')[-1]
		if end.endswith('/'): end = end[:-1]
		if not '/' in end: return None
		end = end.rsplit('/',1)[-1]
		if 'flic.kr/' in url:
			ID = str(self.decodeBase58(end))
		else:
			ID = end
		try:
			int(ID)
			return ID
		except:
			return None
		
	def getFlickrInfo(self,ID):
		fImport = self.doImport('plugin.image.flickr', '', 'default')
		if not fImport: return {}
		try:
			fsession = fImport.FlickrSession()
			if not fsession.authenticate(): return {}
			info = fsession.flickr.photos_getInfo(photo_id=ID)
		except:
			ERROR('Could not get flickr info for ID: %s' % ID)
			return None
		photo = info.find('photo')
		title = photo.find('title').text
		media = photo.get('media','')
		thumb = fImport.photoURL(photo.get('farm',''),photo.get('server',''),ID,photo.get('secret',''))
		#<location latitude="47.574433" longitude="-122.640611" accuracy="16" context="0" place_id="pqEP2S9UV7P8W60smQ" woeid="55995994">
		return {'title':title,'type':media,'thumbnail':thumb}
		
	def extractVimeoIDFromURL(self,url):
		#TODO: Finish this :)
		if url.endswith('/'): url = url[:-1]
		url = url.split('://',1)[-1]
		if not '/' in url: return None
		ID = url.rsplit('/',1)[-1]
		return ID
	
	def getVimeoInfo(self,ID):
		infoURL = 'http://vimeo.com/api/v2/video/%s.xml' % ID
		try:
			xml = urllib2.urlopen(urllib2.Request(infoURL,None,{'User-Agent':'Wget/1.9.1'})).read()
		except:
			ERROR('Could not get Vimeo info for ID: %s' % ID)
			return None
		ret = {}
		try:
			ret['title'] = convertHTMLCodes(re.search('<title>([^<]*)</title>',xml).group(1))
		except:
			pass
		
		try:
			ret['thumbnail'] = re.search('<thumbnail_large>([^<]*)</thumbnail_large>',xml).group(1)
		except:
			pass
		return ret
		
	def getDailymotionInfo(self,ID):
		url = 'http://www.dailymotion.com/video/%s' % ID
		html = urllib2.urlopen(urllib2.Request(url,None,{'User-Agent':'Wget/1.9.1'})).read()
		ret = {}
		try:
			title,ret['thumbnail'] = re.search('<meta property="og:title" content="([^"].+?)".*<meta property="og:image" content="([^"].+?)(?is)"',html).groups()
			ret['title'] = convertHTMLCodes(title)
		except:
			pass
		return ret
		
	def getMetacafeInfo(self,ID):
		url = 'http://www.metacafe.com/watch/%s' % ID
		html = urllib2.urlopen(urllib2.Request(url,None,{'User-Agent':'Wget/1.9.1'})).read()
		ret = {}
		try:
			ret['thumbnail'] = re.search('<meta property="og:image" content="([^"].+?)(?is)"',html).group(1)
		except:
			pass
		
		try:
			first = ast.literal_eval(re.search('flashVarsCache =([^;].*?);(?s)',html).group(1).strip().replace('false','False'))
			ret['title'] = urllib.unquote(first['title'])
		except:
			pass
	
		try:
			second = ast.literal_eval(urllib.unquote(first['mediaData']).replace('false','False'))
			#media = urllib.quote(urllib.unquote(second.get('highDefinitionMP4',second.get('MP4'))['mediaURL']).replace('\\',''))
			media = 'http://' + urllib.quote(urllib.unquote(second.get('highDefinitionMP4',second.get('MP4'))['mediaURL']).replace('\\','').split('://',1)[-1])
			ret['video'] = media
		except:
			pass
		return ret
	
	def getVimeoFLV(self,ID):
		#TODO: Make this better
		infoURL = 'http://www.vimeo.com/moogaloop/load/clip:' + ID
		try:
			o = urllib2.urlopen(infoURL)
			info = o.read()
			sig = re.search('<request_signature>([^<]*)</request_signature>',info).group(1)
			exp = re.search('<request_signature_expires>([^<]*)</request_signature_expires>',info).group(1)
			hd_or_sd = int(re.search('isHD>([^<]*)</isHD>',info).group(1)) and 'hd' or 'sd'
		except:
			ERROR('Failed to get vimeo URL')
			return ''
		flvURL = 'http://www.vimeo.com/moogaloop/play/clip:%s/%s/%s/?q=%s' % (ID,sig,exp,hd_or_sd)
		try:
			flvURL = urllib2.urlopen(urllib2.Request(flvURL,None,{'User-Agent':'Wget/1.9.1'})).geturl()
		except:
			ERROR('Failed to get vimeo URL')
			return ''
		#print flvURL
		return flvURL
	
	def decodeBase58(self,s):
		""" Decodes the base58-encoded string s into an integer """
		decoded = 0
		multi = 1
		s = s[::-1]
		for char in s:
			decoded += multi * self.alphabetB58.index(char)
			multi = multi * self.countB58
		return decoded
	
	def doImport(self,addonID,path,module):
		full = '/'.join((addonID,path,module))
		if full in self.modules: return self.modules[full]
		addonPath = xbmcaddon.Addon(addonID).getAddonInfo('path')
		importPath = os.path.join(addonPath,path)
		sys.path.insert(0,importPath)
		try:
			mod = __import__(module)
			reload(mod)
			del sys.path[0]
			self.modules[full] = mod
			return mod
		except ImportError:
			ERROR('Error importing module %s for share target %s.' % (self.importPath,self.addonID))
		except:
			ERROR('ShareTarget.getModule(): Error during target sharing import')
		return
	
def play(path,preview=False):
	xbmc.executebuiltin('PlayMedia(%s,,%s)' % (path,preview and 1 or 0))
	
def pause():
	if isPlaying(): control('play')
	
def resume():
	if not isPlaying(): control('play')
	
def current():
	return xbmc.getInfoLabel('Player.Filenameandpath')

def control(command):
	xbmc.executebuiltin('PlayerControl(%s)' % command)

def isPlaying():
		return xbmc.getCondVisibility('Player.Playing') and xbmc.getCondVisibility('Player.HasVideo')
	
def playAt(path,h=0,m=0,s=0,ms=0):
	xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Player.Open", "params": {"item":{"file":"%s"},"options":{"resume":{"hours":%s,"minutes":%s,"seconds":%s,"milliseconds":%s}}}, "id": 1}' % (path,h,m,s,ms)) #@UnusedVariable

def disableDashVideo(disable):
	global DISABLE_DASH_VIDEO
	DISABLE_DASH_VIDEO = disable
	
def getYoutubeDLVideo(url,quality=1):
	ytdl = getYTDL()
	r = ytdl.extract_info(url,download=False)
	userAgent = 'Mozilla/5.0+(Windows+NT+6.2;+Win64;+x64;+rv:16.0.1)+Gecko/20121011+Firefox/16.0.1'
	urls =  selectVideoQuality(r,userAgent, quality)
	if not urls: return None
	video = Video(r.get('id',''))
	video.playable = urls[0]['url']
	video.allPlayable = urls
	video.title = r.get('title',urls[0]['title'])
	video.thumbnail = r.get('thumbnail',urls[0]['thumbnail'])
	return video
	
def selectVideoQuality(r, user_agent,quality=1):
		if 'entries' in r and not 'formats' in r:
			entries = r['entries']
		elif 'formats' in r and r['formats']:
			entries = [r]
		elif 'url' in r:
			return [{'url':r['url'],'title':r.get('title',''),'thumbnail':r.get('thumbnail','')}]
		minHeight = 0
		maxHeight = 480
		if quality > 1:
			minHeight = 721
			maxHeight = 1080
		elif quality > 0:
			minHeight = 481
			maxHeight = 720
		LOG('Quality: {0}'.format(quality))
		urls = []
		for entry in entries:
			defFormat = None
			defMax = 0
			defPref = -1000
			prefFormat = None
			prefMax = 0
			prefPref = -1000
			index = {}
			formats = entry['formats']
			for i in range(0,len(formats)): index[formats[i]['format_id']] = i
			keys = sorted(index.keys())
			fallback = formats[index[keys[0]]]
			for fmt in keys:
				fdata = formats[index[fmt]]
				if not 'height' in fdata: continue
				if DISABLE_DASH_VIDEO and 'dash' in fdata.get('format_note','').lower(): continue
				h = fdata['height']
				p = fdata.get('preference',1)
				if h >= minHeight and h <= maxHeight:
					if (h >= prefMax and p > prefPref) or (h > prefMax and p >= prefPref):
						prefMax = h
						prefPref = p
						prefFormat = fdata
				elif(h >= defMax and h <= maxHeight and p > defPref) or (h > defMax and h <= maxHeight and p >= defPref):
						defMax = h
						defFormat = fdata
						defPref = p
			if prefFormat:
				LOG('[{3}] Using Preferred Format: {0} ({1}x{2})'.format(prefFormat['format'],prefFormat.get('width','?'),prefMax,entry.get('title','').encode('ascii','replace')))
				url = prefFormat['url']
			elif defFormat:
				LOG('[{3}] Using Default Format: {0} ({1}x{2})'.format(defFormat['format'],defFormat.get('width','?'),defMax,entry.get('title','').encode('ascii','replace')))
				url = defFormat['url']
			else:
				LOG('[{3}] Using Fallback Format: {0} ({1}x{2})'.format(fallback['format'],fallback.get('width','?'),fallback.get('height','?'),entry.get('title','').encode('ascii','replace')))
				url = fallback['url']
			if url.find("rtmp") == -1:
				url += '|' + urllib.urlencode({'User-Agent':entry.get('user_agent') or user_agent})
			else:
				url += ' playpath='+fdata['play_path']
			urls.append({'url':url,'title':entry.get('title',''),'thumbnail':entry.get('thumbnail','')})
		return urls

class YoutubeDLWrapper(youtube_dl.YoutubeDL):
	def __init__(self, params=None,blacklist=None):
		self._blacklist = blacklist or []
		youtube_dl.YoutubeDL.__init__(self,params)
		
	def add_info_extractor(self, ie):
		if ie.IE_NAME in self._blacklist: return
		youtube_dl.YoutubeDL.add_info_extractor(self,ie)

def getYTDL():
	if YTDL: return YTDL
	global YTDL
	blacklist = ['youtube:playlist', 'youtube:toplist', 'youtube:channel', 'youtube:user', 'youtube:search', 'youtube:show', 'youtube:favorites', 'youtube:truncated_url','vimeo:channel', 'vimeo:user', 'vimeo:album', 'vimeo:group', 'vimeo:review','generic']
	YTDL = YoutubeDLWrapper({'quiet':True},blacklist)
	#YTDL = youtube_dl.YoutubeDL({'verbose':True,'noplaylist':True,'playlistend':10})
	YTDL.add_default_info_extractors()
	return YTDL
	
	
def getVideoURL(url,quality):
	ytdl = getYTDL()
	r = ytdl.extract_info(url,download=False)
	userAgent = 'Mozilla/5.0+(Windows+NT+6.2;+Win64;+x64;+rv:16.0.1)+Gecko/20121011+Firefox/16.0.1'
	return selectVideoQuality(r,userAgent,quality)
							
	
#http://vimeo.com/moogaloop.swf?clip_id=38759453
#http://vimeo.com/api/v2/video/38759453.json

#http://www.vimeo.com/moogaloop/load/clip:82739
#http://www.vimeo.com/moogaloop/play/clip:82739/38c7be0cecb92a0a3623c2769bccf73b/1221451200/?q=sd