import collections
import json
import os
import threading
import time

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusImageHandling
from hydrus.core import HydrusThreading
from hydrus.core import HydrusData
from hydrus.core import HydrusGlobals as HG

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientFiles
from hydrus.client import ClientImageHandling
from hydrus.client import ClientParsing
from hydrus.client import ClientRendering

class DataCache( object ):
    
    def __init__( self, controller, cache_size, timeout = 1200 ):
        
        self._controller = controller
        self._cache_size = cache_size
        self._timeout = timeout
        
        self._keys_to_data = {}
        self._keys_fifo = collections.OrderedDict()
        
        self._total_estimated_memory_footprint = 0
        
        self._lock = threading.Lock()
        
        self._controller.sub( self, 'MaintainCache', 'memory_maintenance_pulse' )
        
    
    def _Delete( self, key ):
        
        if key not in self._keys_to_data:
            
            return
            
        
        del self._keys_to_data[ key ]
        
        self._RecalcMemoryUsage()
        
    
    def _DeleteItem( self ):
        
        ( deletee_key, last_access_time ) = self._keys_fifo.popitem( last = False )
        
        self._Delete( deletee_key )
        
    
    def _RecalcMemoryUsage( self ):
        
        self._total_estimated_memory_footprint = sum( ( data.GetEstimatedMemoryFootprint() for data in self._keys_to_data.values() ) )
        
    
    def _TouchKey( self, key ):
        
        # have to delete first, rather than overwriting, so the ordereddict updates its internal order
        if key in self._keys_fifo:
            
            del self._keys_fifo[ key ]
            
        
        self._keys_fifo[ key ] = HydrusData.GetNow()
        
    
    def Clear( self ):
        
        with self._lock:
            
            self._keys_to_data = {}
            self._keys_fifo = collections.OrderedDict()
            
            self._total_estimated_memory_footprint = 0
            
        
    
    def AddData( self, key, data ):
        
        with self._lock:
            
            if key not in self._keys_to_data:
                
                while self._total_estimated_memory_footprint > self._cache_size:
                    
                    self._DeleteItem()
                    
                
                self._keys_to_data[ key ] = data
                
                self._TouchKey( key )
                
                self._RecalcMemoryUsage()
                
            
        
    
    def DeleteData( self, key ):
        
        with self._lock:
            
            self._Delete( key )
            
        
    
    def GetData( self, key ):
        
        with self._lock:
            
            if key not in self._keys_to_data:
                
                raise Exception( 'Cache error! Looking for {}, but it was missing.'.format( key ) )
                
            
            self._TouchKey( key )
            
            return self._keys_to_data[ key ]
            
        
    
    def GetIfHasData( self, key ):
        
        with self._lock:
            
            if key in self._keys_to_data:
                
                self._TouchKey( key )
                
                return self._keys_to_data[ key ]
                
            else:
                
                return None
                
            
        
    
    def HasData( self, key ):
        
        with self._lock:
            
            return key in self._keys_to_data
            
        
    
    def MaintainCache( self ):
        
        with self._lock:
            
            while True:
                
                if len( self._keys_fifo ) == 0:
                    
                    break
                    
                else:
                    
                    ( key, last_access_time ) = next( iter( self._keys_fifo.items() ) )
                    
                    if HydrusData.TimeHasPassed( last_access_time + self._timeout ):
                        
                        self._DeleteItem()
                        
                    else:
                        
                        break
                        
                    
                
            
        
    
class LocalBooruCache( object ):
    
    def __init__( self, controller ):
        
        self._controller = controller
        
        self._lock = threading.Lock()
        
        self._RefreshShares()
        
        self._controller.sub( self, 'RefreshShares', 'refresh_local_booru_shares' )
        self._controller.sub( self, 'RefreshShares', 'restart_client_server_service' )
        
    
    def _CheckDataUsage( self ):
        
        if not self._local_booru_service.BandwidthOK():
            
            raise HydrusExceptions.InsufficientCredentialsException( 'This booru has used all its monthly data. Please try again next month.' )
            
        
    
    def _CheckFileAuthorised( self, share_key, hash ):
        
        self._CheckShareAuthorised( share_key )
        
        info = self._GetInfo( share_key )
        
        if hash not in info[ 'hashes_set' ]:
            
            raise HydrusExceptions.NotFoundException( 'That file was not found in that share.' )
            
        
    
    def _CheckShareAuthorised( self, share_key ):
        
        self._CheckDataUsage()
        
        info = self._GetInfo( share_key )
        
        timeout = info[ 'timeout' ]
        
        if timeout is not None and HydrusData.TimeHasPassed( timeout ):
            
            raise HydrusExceptions.NotFoundException( 'This share has expired.' )
            
        
    
    def _GetInfo( self, share_key ):
        
        try: info = self._keys_to_infos[ share_key ]
        except: raise HydrusExceptions.NotFoundException( 'Did not find that share on this booru.' )
        
        if info is None:
            
            info = self._controller.Read( 'local_booru_share', share_key )
            
            hashes = info[ 'hashes' ]
            
            info[ 'hashes_set' ] = set( hashes )
            
            media_results = self._controller.Read( 'media_results', hashes )
            
            info[ 'media_results' ] = media_results
            
            hashes_to_media_results = { media_result.GetHash() : media_result for media_result in media_results }
            
            info[ 'hashes_to_media_results' ] = hashes_to_media_results
            
            self._keys_to_infos[ share_key ] = info
            
        
        return info
        
    
    def _RefreshShares( self ):
        
        self._local_booru_service = self._controller.services_manager.GetService( CC.LOCAL_BOORU_SERVICE_KEY )
        
        self._keys_to_infos = {}
        
        share_keys = self._controller.Read( 'local_booru_share_keys' )
        
        for share_key in share_keys:
            
            self._keys_to_infos[ share_key ] = None
            
        
    
    def CheckShareAuthorised( self, share_key ):
        
        with self._lock: self._CheckShareAuthorised( share_key )
        
    
    def CheckFileAuthorised( self, share_key, hash ):
        
        with self._lock: self._CheckFileAuthorised( share_key, hash )
        
    
    def GetGalleryInfo( self, share_key ):
        
        with self._lock:
            
            self._CheckShareAuthorised( share_key )
            
            info = self._GetInfo( share_key )
            
            name = info[ 'name' ]
            text = info[ 'text' ]
            timeout = info[ 'timeout' ]
            media_results = info[ 'media_results' ]
            
            return ( name, text, timeout, media_results )
            
        
    
    def GetMediaResult( self, share_key, hash ):
        
        with self._lock:
            
            info = self._GetInfo( share_key )
            
            media_result = info[ 'hashes_to_media_results' ][ hash ]
            
            return media_result
            
        
    
    def GetPageInfo( self, share_key, hash ):
        
        with self._lock:
            
            self._CheckFileAuthorised( share_key, hash )
            
            info = self._GetInfo( share_key )
            
            name = info[ 'name' ]
            text = info[ 'text' ]
            timeout = info[ 'timeout' ]
            media_result = info[ 'hashes_to_media_results' ][ hash ]
            
            return ( name, text, timeout, media_result )
            
        
    
    def RefreshShares( self, *args, **kwargs ):
        
        with self._lock:
            
            self._RefreshShares()
            
        
    
class ParsingCache( object ):
    
    def __init__( self ):
        
        self._next_clean_cache_time = HydrusData.GetNow()
        
        self._html_to_soups = {}
        self._json_to_jsons = {}
        
        self._lock = threading.Lock()
        
    
    def _CleanCache( self ):
        
        if HydrusData.TimeHasPassed( self._next_clean_cache_time ):
            
            for cache in ( self._html_to_soups, self._json_to_jsons ):
                
                dead_datas = set()
                
                for ( data, ( last_accessed, parsed_object ) ) in cache.items():
                    
                    if HydrusData.TimeHasPassed( last_accessed + 10 ):
                        
                        dead_datas.add( data )
                        
                    
                
                for dead_data in dead_datas:
                    
                    del cache[ dead_data ]
                    
                
            
            self._next_clean_cache_time = HydrusData.GetNow() + 5
            
        
    
    def CleanCache( self ):
        
        with self._lock:
            
            self._CleanCache()
            
        
    
    def GetJSON( self, json_text ):
        
        with self._lock:
            
            now = HydrusData.GetNow()
            
            if json_text not in self._json_to_jsons:
                
                json_object = json.loads( json_text )
                
                self._json_to_jsons[ json_text ] = ( now, json_object )
                
            
            ( last_accessed, json_object ) = self._json_to_jsons[ json_text ]
            
            if last_accessed != now:
                
                self._json_to_jsons[ json_text ] = ( now, json_object )
                
            
            if len( self._json_to_jsons ) > 10:
                
                self._CleanCache()
                
            
            return json_object
            
        
    
    def GetSoup( self, html ):
        
        with self._lock:
            
            now = HydrusData.GetNow()
            
            if html not in self._html_to_soups:
                
                soup = ClientParsing.GetSoup( html )
                
                self._html_to_soups[ html ] = ( now, soup )
                
            
            ( last_accessed, soup ) = self._html_to_soups[ html ]
            
            if last_accessed != now:
                
                self._html_to_soups[ html ] = ( now, soup )
                
            
            if len( self._html_to_soups ) > 10:
                
                self._CleanCache()
                
            
            return soup
            
        
    
class RenderedImageCache( object ):
    
    def __init__( self, controller ):
        
        self._controller = controller
        
        cache_size = self._controller.options[ 'fullscreen_cache_size' ]
        cache_timeout = self._controller.new_options.GetInteger( 'image_cache_timeout' )
        
        self._data_cache = DataCache( self._controller, cache_size, timeout = cache_timeout )
        
    
    def Clear( self ):
        
        self._data_cache.Clear()
        
    
    def GetImageRenderer( self, media ):
        
        hash = media.GetHash()
        
        key = hash
        
        result = self._data_cache.GetIfHasData( key )
        
        if result is None:
            
            image_renderer = ClientRendering.ImageRenderer( media )
            
            self._data_cache.AddData( key, image_renderer )
            
        else:
            
            image_renderer = result
            
        
        return image_renderer
        
    
    def HasImageRenderer( self, hash ):
        
        key = hash
        
        return self._data_cache.HasData( key )
        
    
class ThumbnailCache( object ):
    
    def __init__( self, controller ):
        
        self._controller = controller
        
        cache_size = self._controller.options[ 'thumbnail_cache_size' ]
        cache_timeout = self._controller.new_options.GetInteger( 'thumbnail_cache_timeout' )
        
        self._data_cache = DataCache( self._controller, cache_size, timeout = cache_timeout )
        
        self._magic_mime_thumbnail_ease_score_lookup = {}
        
        self._InitialiseMagicMimeScores()
        
        self._lock = threading.Lock()
        
        self._thumbnail_error_occurred = False
        
        self._waterfall_queue_quick = set()
        self._waterfall_queue = []
        
        self._waterfall_queue_empty_event = threading.Event()
        
        self._delayed_regeneration_queue_quick = set()
        self._delayed_regeneration_queue = []
        
        self._waterfall_event = threading.Event()
        
        self._special_thumbs = {}
        
        self.Clear()
        
        self._controller.CallToThreadLongRunning( self.MainLoop )
        
        self._controller.sub( self, 'Clear', 'reset_thumbnail_cache' )
        self._controller.sub( self, 'ClearThumbnails', 'clear_thumbnails' )
        
    
    def _GetThumbnailHydrusBitmap( self, display_media ):
        
        bounding_dimensions = self._controller.options[ 'thumbnail_dimensions' ]
        
        hash = display_media.GetHash()
        mime = display_media.GetMime()
        
        locations_manager = display_media.GetLocationsManager()
        
        try:
            
            path = self._controller.client_files_manager.GetThumbnailPath( display_media )
            
        except HydrusExceptions.FileMissingException as e:
            
            if locations_manager.IsLocal():
                
                summary = 'Unable to get thumbnail for file {}.'.format( hash.hex() )
                
                self._HandleThumbnailException( e, summary )
                
            
            return self._special_thumbs[ 'hydrus' ]
            
        
        try:
            
            numpy_image = ClientImageHandling.GenerateNumPyImage( path, mime )
            
        except Exception as e:
            
            try:
                
                # file is malformed, let's force a regen
                self._controller.files_maintenance_manager.RunJobImmediately( [ display_media ], ClientFiles.REGENERATE_FILE_DATA_JOB_FORCE_THUMBNAIL, pub_job_key = False )
                
            except Exception as e:
                
                summary = 'The thumbnail for file {} was not loadable. An attempt to regenerate it failed.'.format( hash.hex() )
                
                self._HandleThumbnailException( e, summary )
                
                return self._special_thumbs[ 'hydrus' ]
                
            
            try:
                
                numpy_image = ClientImageHandling.GenerateNumPyImage( path, mime )
                
            except Exception as e:
                
                summary = 'The thumbnail for file {} was not loadable. It was regenerated, but that file would not render either. Your image libraries or hard drive connection are unreliable. Please inform the hydrus developer what has happened.'.format( hash.hex() )
                
                self._HandleThumbnailException( e, summary )
                
                return self._special_thumbs[ 'hydrus' ]
                
            
        
        ( current_width, current_height ) = HydrusImageHandling.GetResolutionNumPy( numpy_image )
        
        ( media_width, media_height ) = display_media.GetResolution()
        
        ( expected_width, expected_height ) = HydrusImageHandling.GetThumbnailResolution( ( media_width, media_height ), bounding_dimensions )
        
        exactly_as_expected = current_width == expected_width and current_height == expected_height
        
        rotation_exception = current_width == expected_height and current_height == expected_width
        
        correct_size = exactly_as_expected or rotation_exception
        
        if not correct_size:
            
            it_is_definitely_too_big = current_width >= expected_width and current_height >= expected_height
            
            if it_is_definitely_too_big:
                
                if HG.file_report_mode:
                    
                    HydrusData.ShowText( 'Thumbnail {} too big.'.format( hash.hex() ) )
                    
                
                # the thumb we have is larger than desired. we can use it to generate what we actually want without losing significant data
                
                # this is _resize_, not _thumbnail_, because we already know the dimensions we want
                # and in some edge cases, doing getthumbresolution on existing thumb dimensions results in float/int conversion imprecision and you get 90px/91px regen cycles that never get fixed
                numpy_image = HydrusImageHandling.ResizeNumPyImage( numpy_image, ( expected_width, expected_height ) )
                
                if locations_manager.IsLocal():
                    
                    # we have the master file, so it is safe to save our resized thumb back to disk since we can regen from source if needed
                    
                    if HG.file_report_mode:
                        
                        HydrusData.ShowText( 'Thumbnail {} too big, saving back to disk.'.format( hash.hex() ) )
                        
                    
                    try:
                        
                        try:
                            
                            thumbnail_bytes = HydrusImageHandling.GenerateThumbnailBytesNumPy( numpy_image, mime )
                            
                        except HydrusExceptions.CantRenderWithCVException:
                            
                            thumbnail_bytes = HydrusImageHandling.GenerateThumbnailBytesFromStaticImagePath( path, ( expected_width, expected_height ), mime )
                            
                        
                    except:
                        
                        summary = 'The thumbnail for file {} was too large, but an attempt to shrink it failed.'.format( hash.hex() )
                        
                        self._HandleThumbnailException( e, summary )
                        
                        return self._special_thumbs[ 'hydrus' ]
                        
                    
                    try:
                        
                        self._controller.client_files_manager.AddThumbnailFromBytes( hash, thumbnail_bytes, silent = True )
                        
                        self._controller.files_maintenance_manager.ClearJobs( { hash }, ClientFiles.REGENERATE_FILE_DATA_JOB_REFIT_THUMBNAIL )
                        
                    except:
                        
                        summary = 'The thumbnail for file {} was too large, but an attempt to save back the shrunk file failed.'.format( hash.hex() )
                        
                        self._HandleThumbnailException( e, summary )
                        
                        return self._special_thumbs[ 'hydrus' ]
                        
                    
                
            else:
                
                # the thumb we have is either too small or completely messed up due to a previous ratio misparse
                
                media_is_same_size_as_current_thumb = current_width == media_width and current_height == media_height
                
                if media_is_same_size_as_current_thumb:
                    
                    # the thumb is smaller than expected, but this is a 32x32 pixilart image or whatever, so no need to scale
                    
                    if HG.file_report_mode:
                        
                        HydrusData.ShowText( 'Thumbnail {} too small due to small source file.'.format( hash.hex() ) )
                        
                    
                    pass
                    
                else:
                    
                    numpy_image = HydrusImageHandling.ResizeNumPyImage( numpy_image, ( expected_width, expected_height ) )
                    
                    if locations_manager.IsLocal():
                        
                        # we have the master file, so we should regen the thumb from source
                        
                        if HG.file_report_mode:
                            
                            HydrusData.ShowText( 'Thumbnail {} too small, scheduling regeneration from source.'.format( hash.hex() ) )
                            
                        
                        delayed_item = display_media.GetMediaResult()
                        
                        with self._lock:
                            
                            if delayed_item not in self._delayed_regeneration_queue_quick:
                                
                                self._delayed_regeneration_queue_quick.add( delayed_item )
                                
                                self._delayed_regeneration_queue.append( delayed_item )
                                
                            
                        
                    else:
                        
                        # we do not have the master file, so we have to scale up from what we have
                        
                        if HG.file_report_mode:
                            
                            HydrusData.ShowText( 'Thumbnail {} was too small, only scaling up due to no local source.'.format( hash.hex() ) )
                            
                        
                    
                
            
        
        hydrus_bitmap = ClientRendering.GenerateHydrusBitmapFromNumPyImage( numpy_image )
        
        return hydrus_bitmap
        
    
    def _HandleThumbnailException( self, e, summary ):
        
        if self._thumbnail_error_occurred:
            
            HydrusData.Print( summary )
            
        else:
            
            self._thumbnail_error_occurred = True
            
            message = 'A thumbnail error has occurred. The problem thumbnail will appear with the default \'hydrus\' symbol. You may need to take hard drive recovery actions, and if the error is not obviously fixable, you can contact hydrus dev for additional help. Specific information for this first error follows. Subsequent thumbnail errors in this session will be silently printed to the log.'
            message += os.linesep * 2
            message += str( e )
            message += os.linesep * 2
            message += summary
            
            HydrusData.ShowText( message )
            
        
    
    def _InitialiseMagicMimeScores( self ):
        
        # let's render our thumbs in order of ease of regeneration, so we rush what we can to screen as fast as possible and leave big vids until the end
        
        for mime in HC.ALLOWED_MIMES:
            
            self._magic_mime_thumbnail_ease_score_lookup[ mime ] = 5
            
        
        # default filetype thumbs are easiest
        
        self._magic_mime_thumbnail_ease_score_lookup[ None ] = 0
        self._magic_mime_thumbnail_ease_score_lookup[ HC.APPLICATION_UNKNOWN ] = 0
        
        for mime in HC.APPLICATIONS:
            
            self._magic_mime_thumbnail_ease_score_lookup[ mime ] = 0
            
        
        for mime in HC.AUDIO:
            
            self._magic_mime_thumbnail_ease_score_lookup[ mime ] = 0
            
        
        # images a little trickier
        
        for mime in HC.IMAGES:
            
            self._magic_mime_thumbnail_ease_score_lookup[ mime ] = 1
            
        
        # override because these are a bit more
        self._magic_mime_thumbnail_ease_score_lookup[ HC.IMAGE_APNG ] = 2
        self._magic_mime_thumbnail_ease_score_lookup[ HC.IMAGE_GIF ] = 2
        
        # ffmpeg hellzone
        
        for mime in HC.VIDEO:
            
            self._magic_mime_thumbnail_ease_score_lookup[ mime ] = 3
            
        
        for mime in HC.ANIMATIONS:
            
            self._magic_mime_thumbnail_ease_score_lookup[ mime ] = 3
            
        
    
    def _RecalcQueues( self ):
        
        # here we sort by the hash since this is both breddy random and more likely to access faster on a well defragged hard drive!
        # and now with the magic mime order
        
        def sort_waterfall( item ):
            
            ( page_key, media ) = item
            
            display_media = media.GetDisplayMedia()
            
            if display_media is None:
                
                magic_score = self._magic_mime_thumbnail_ease_score_lookup[ None ]
                hash = ''
                
            else:
                
                magic_score = self._magic_mime_thumbnail_ease_score_lookup[ display_media.GetMime() ]
                hash = display_media.GetHash()
                
            
            return ( magic_score, hash )
            
        
        self._waterfall_queue = list( self._waterfall_queue_quick )
        
        # we pop off the end, so reverse
        self._waterfall_queue.sort( key = sort_waterfall, reverse = True )
        
        if len( self._waterfall_queue ) == 0:
            
            self._waterfall_queue_empty_event.set()
            
        else:
            
            self._waterfall_queue_empty_event.clear()
            
        
        def sort_regen( item ):
            
            media_result = item
            
            hash = media_result.GetHash()
            mime = media_result.GetMime()
            
            magic_score = self._magic_mime_thumbnail_ease_score_lookup[ mime ]
            
            return ( magic_score, hash )
            
        
        self._delayed_regeneration_queue = list( self._delayed_regeneration_queue_quick )
        
        # we pop off the end, so reverse
        self._delayed_regeneration_queue.sort( key = sort_regen, reverse = True )
        
    
    def CancelWaterfall( self, page_key: bytes, medias: list ):
        
        with self._lock:
            
            self._waterfall_queue_quick.difference_update( ( ( page_key, media ) for media in medias ) )
            
            cancelled_display_medias = { media.GetDisplayMedia() for media in medias }
            
            cancelled_display_medias.discard( None )
            
            cancelled_media_results = { media.GetMediaResult() for media in cancelled_display_medias }
            
            outstanding_delayed_hashes = { media_result.GetHash() for media_result in cancelled_media_results if media_result in self._delayed_regeneration_queue_quick }
            
            if len( outstanding_delayed_hashes ) > 0:
                
                self._controller.files_maintenance_manager.ScheduleJob( outstanding_delayed_hashes, ClientFiles.REGENERATE_FILE_DATA_JOB_FORCE_THUMBNAIL )
                
            
            self._delayed_regeneration_queue_quick.difference_update( cancelled_media_results )
            
            self._RecalcQueues()
            
        
    
    def Clear( self ):
        
        with self._lock:
            
            self._data_cache.Clear()
            
            self._special_thumbs = {}
            
            names = [ 'hydrus', 'pdf', 'psd', 'clip', 'audio', 'video', 'zip' ]
            
            bounding_dimensions = self._controller.options[ 'thumbnail_dimensions' ]
            
            for name in names:
                
                path = os.path.join( HC.STATIC_DIR, name + '.png' )
                
                numpy_image = ClientImageHandling.GenerateNumPyImage( path, HC.IMAGE_PNG )
                
                numpy_image_resolution = HydrusImageHandling.GetResolutionNumPy( numpy_image )
                
                target_resolution = HydrusImageHandling.GetThumbnailResolution( numpy_image_resolution, bounding_dimensions )
                
                numpy_image = HydrusImageHandling.ResizeNumPyImage( numpy_image, target_resolution )
                
                hydrus_bitmap = ClientRendering.GenerateHydrusBitmapFromNumPyImage( numpy_image )
                
                self._special_thumbs[ name ] = hydrus_bitmap
                
            
            self._controller.pub( 'notify_complete_thumbnail_reset' )
            
            self._waterfall_queue_quick = set()
            self._delayed_regeneration_queue_quick = set()
            
            self._RecalcQueues()
            
        
    
    def ClearThumbnails( self, hashes ):
        
        with self._lock:
            
            for hash in hashes:
                
                self._data_cache.DeleteData( hash )
                
            
        
    
    def WaitUntilFree( self ):
        
        while True:
            
            if HG.view_shutdown:
                
                raise HydrusExceptions.ShutdownException( 'Application shutting down!' )
                
            
            queue_is_empty = self._waterfall_queue_empty_event.wait( 1 )
            
            if queue_is_empty:
                
                return
                
            
        
    
    def GetThumbnail( self, media ):
        
        display_media = media.GetDisplayMedia()
        
        if display_media is None:
            
            # sometimes media can get switched around during a collect event, and if this happens during waterfall, we have a problem here
            # just return for now, we'll see how it goes
            
            return self._special_thumbs[ 'hydrus' ]
            
        
        locations_manager = display_media.GetLocationsManager()
        
        if locations_manager.ShouldIdeallyHaveThumbnail():
            
            mime = display_media.GetMime()
            
            if mime in HC.MIMES_WITH_THUMBNAILS:
                
                hash = display_media.GetHash()
                
                result = self._data_cache.GetIfHasData( hash )
                
                if result is None:
                    
                    try:
                        
                        hydrus_bitmap = self._GetThumbnailHydrusBitmap( display_media )
                        
                    except:
                        
                        hydrus_bitmap = self._special_thumbs[ 'hydrus' ]
                        
                    
                    self._data_cache.AddData( hash, hydrus_bitmap )
                    
                else:
                    
                    hydrus_bitmap = result
                    
                
                return hydrus_bitmap
                
            elif mime in HC.AUDIO: return self._special_thumbs[ 'audio' ]
            elif mime in HC.VIDEO: return self._special_thumbs[ 'video' ]
            elif mime == HC.APPLICATION_PDF: return self._special_thumbs[ 'pdf' ]
            elif mime == HC.APPLICATION_PSD: return self._special_thumbs[ 'psd' ]
            elif mime == HC.APPLICATION_CLIP: return self._special_thumbs[ 'clip' ]
            elif mime in HC.ARCHIVES: return self._special_thumbs[ 'zip' ]
            else: return self._special_thumbs[ 'hydrus' ]
            
        else:
            
            return self._special_thumbs[ 'hydrus' ]
            
        
    
    def HasThumbnailCached( self, media ):
        
        display_media = media.GetDisplayMedia()
        
        if display_media is None:
            
            return True
            
        
        mime = display_media.GetMime()
        
        if mime in HC.MIMES_WITH_THUMBNAILS:
            
            hash = display_media.GetHash()
            
            return self._data_cache.HasData( hash )
            
        else:
            
            return True
            
        
    
    def Waterfall( self, page_key, medias ):
        
        with self._lock:
            
            self._waterfall_queue_quick.update( ( ( page_key, media ) for media in medias ) )
            
            self._RecalcQueues()
            
        
        self._waterfall_event.set()
        
    
    def MainLoop( self ):
        
        while not HydrusThreading.IsThreadShuttingDown():
            
            time.sleep( 0.00001 )
            
            with self._lock:
                
                do_wait = len( self._waterfall_queue ) == 0 and len( self._delayed_regeneration_queue ) == 0
                
            
            if do_wait:
                
                self._waterfall_event.wait( 1 )
                
                self._waterfall_event.clear()
                
            
            start_time = HydrusData.GetNowPrecise()
            stop_time = start_time + 0.005 # a bit of a typical frame
            
            page_keys_to_rendered_medias = collections.defaultdict( list )
            
            num_done = 0
            max_at_once = 16
            
            while not HydrusData.TimeHasPassedPrecise( stop_time ) and num_done <= max_at_once:
                
                with self._lock:
                    
                    if len( self._waterfall_queue ) == 0:
                        
                        break
                        
                    
                    result = self._waterfall_queue.pop()
                    
                    if len( self._waterfall_queue ) == 0:
                        
                        self._waterfall_queue_empty_event.set()
                        
                    
                    self._waterfall_queue_quick.discard( result )
                    
                
                ( page_key, media ) = result
                
                if media.GetDisplayMedia() is not None:
                    
                    self.GetThumbnail( media )
                    
                    page_keys_to_rendered_medias[ page_key ].append( media )
                    
                
                num_done += 1
                
            
            if len( page_keys_to_rendered_medias ) > 0:
                
                for ( page_key, rendered_medias ) in page_keys_to_rendered_medias.items():
                    
                    self._controller.pub( 'waterfall_thumbnails', page_key, rendered_medias )
                    
                
                time.sleep( 0.00001 )
                
            
            # now we will do regen if appropriate
            
            with self._lock:
                
                # got more important work or no work to do
                if len( self._waterfall_queue ) > 0 or len( self._delayed_regeneration_queue ) == 0 or HG.client_controller.CurrentlyPubSubbing():
                    
                    continue
                    
                
                media_result = self._delayed_regeneration_queue.pop()
                
                self._delayed_regeneration_queue_quick.discard( media_result )
                
            
            if HG.file_report_mode:
                
                hash = media_result.GetHash()
                
                HydrusData.ShowText( 'Thumbnail {} now regenerating from source.'.format( hash.hex() ) )
                
            
            try:
                
                self._controller.files_maintenance_manager.RunJobImmediately( [ media_result ], ClientFiles.REGENERATE_FILE_DATA_JOB_FORCE_THUMBNAIL, pub_job_key = False )
                
            except HydrusExceptions.FileMissingException:
                
                pass
                
            except Exception as e:
                
                hash = media_result.GetHash()
                
                summary = 'The thumbnail for file {} was incorrect, but a later attempt to regenerate it or load the new file back failed.'.format( hash.hex() )
                
                self._HandleThumbnailException( e, summary )
                
            
        
    
