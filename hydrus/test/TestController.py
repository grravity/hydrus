import collections
import os
import threading
import collections
import tempfile
import time
import traceback
import unittest

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusGlobals as HG
from hydrus.core import HydrusPaths
from hydrus.core import HydrusPubSub
from hydrus.core import HydrusSessions
from hydrus.core import HydrusThreading

from hydrus.client import ClientAPI
from hydrus.client import ClientCaches
from hydrus.client import ClientConstants as CC
from hydrus.client import ClientDefaults
from hydrus.client import ClientFiles
from hydrus.client import ClientOptions
from hydrus.client import ClientManagers
from hydrus.client import ClientServices
from hydrus.client import ClientThreading
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui import ClientGUISplash
from hydrus.client.gui.lists import ClientGUIListManager
from hydrus.client.metadata import ClientTags
from hydrus.client.metadata import ClientTagsHandling
from hydrus.client.networking import ClientNetworking
from hydrus.client.networking import ClientNetworkingBandwidth
from hydrus.client.networking import ClientNetworkingDomain
from hydrus.client.networking import ClientNetworkingLogin
from hydrus.client.networking import ClientNetworkingSessions

from hydrus.test import TestClientAPI
from hydrus.test import TestClientConstants
from hydrus.test import TestClientDaemons
from hydrus.test import TestClientData
from hydrus.test import TestClientDB
from hydrus.test import TestClientDBDuplicates
from hydrus.test import TestClientDBTags
from hydrus.test import TestClientImageHandling
from hydrus.test import TestClientImportOptions
from hydrus.test import TestClientImportSubscriptions
from hydrus.test import TestClientListBoxes
from hydrus.test import TestClientMigration
from hydrus.test import TestClientNetworking
from hydrus.test import TestClientParsing
from hydrus.test import TestClientTags
from hydrus.test import TestClientThreading
from hydrus.test import TestDialogs
from hydrus.test import TestFunctions
from hydrus.test import TestHydrusData
from hydrus.test import TestHydrusNATPunch
from hydrus.test import TestHydrusNetworking
from hydrus.test import TestHydrusSerialisable
from hydrus.test import TestHydrusServer
from hydrus.test import TestHydrusSessions
from hydrus.test import TestServerDB

DB_DIR = None

tiniest_gif = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\xFF\x00\x2C\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00\x3B'

LOCAL_RATING_LIKE_SERVICE_KEY = HydrusData.GenerateKey()
LOCAL_RATING_NUMERICAL_SERVICE_KEY = HydrusData.GenerateKey()

def ConvertServiceKeysToContentUpdatesToComparable( service_keys_to_content_updates ):
    
    comparable_dict = {}
    
    for ( service_key, content_updates ) in list(service_keys_to_content_updates.items()):
        
        comparable_dict[ service_key ] = set( content_updates )
        
    
    return comparable_dict
    
class MockController( object ):
    
    def __init__( self ):
        
        self.new_options = ClientOptions.ClientOptions()
        
    
    def CallToThread( self, callable, *args, **kwargs ):
        
        return HG.test_controller.CallToThread( callable, *args, **kwargs )
        
    
    def JustWokeFromSleep( self ):
        
        return False
        
    
    def pub( self, *args, **kwargs ):
        
        pass
        
    
    def sub( self, *args, **kwargs ):
        
        pass
        
    
class MockServicesManager( object ):
    
    def __init__( self, services ):
        
        self._service_keys_to_services = { service.GetServiceKey() : service for service in services }
        
    
    def GetName( self, service_key ):
        
        return self._service_keys_to_services[ service_key ].GetName()
        
    
    def GetService( self, service_key ):
        
        return self._service_keys_to_services[ service_key ]
        
    
    def ServiceExists( self, service_key ):
        
        return service_key in self._service_keys_to_services
        
    
class FakeWebSessionManager():
    
    def EnsureLoggedIn( self, name ):
        
        pass
        
    
    def GetCookies( self, *args, **kwargs ):
        
        return { 'session_cookie' : 'blah' }
        
    
class TestFrame( QW.QWidget ):
    
    def __init__( self ):
        
        QW.QWidget.__init__( self, None )
        
    
    def SetPanel( self, panel ):
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, panel, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.setLayout( vbox )
        
        self.show()
        

only_run = None

class Controller( object ):
    
    def __init__( self, win, only_run ):
        
        self.app = win
        self.win = win
        self.only_run = only_run
        
        self.db_dir = tempfile.mkdtemp()
        
        global DB_DIR
        
        DB_DIR = self.db_dir
        
        self._server_files_dir = os.path.join( self.db_dir, 'server_files' )
        self._updates_dir = os.path.join( self.db_dir, 'test_updates' )
        
        client_files_default = os.path.join( self.db_dir, 'client_files' )
        
        HydrusPaths.MakeSureDirectoryExists( self._server_files_dir )
        HydrusPaths.MakeSureDirectoryExists( self._updates_dir )
        HydrusPaths.MakeSureDirectoryExists( client_files_default )
        
        HG.controller = self
        HG.client_controller = self
        HG.server_controller = self
        HG.test_controller = self
        
        self.db = self
        self.gui = self
        
        self.frame_splash_status = ClientGUISplash.FrameSplashStatus()
        
        self._call_to_threads = []
        
        self._pubsub = HydrusPubSub.HydrusPubSub( self, lambda o: True )
        
        self.new_options = ClientOptions.ClientOptions()
        
        HC.options = ClientDefaults.GetClientDefaultOptions()
        
        self.options = HC.options
        
        def show_text( text ): pass
        
        HydrusData.ShowText = show_text
        
        self._reads = {}
        
        self._reads[ 'local_booru_share_keys' ] = []
        self._reads[ 'messaging_sessions' ] = []
        self._reads[ 'options' ] = ClientDefaults.GetClientDefaultOptions()
        self._reads[ 'file_system_predicates' ] = []
        self._reads[ 'media_results' ] = []
        
        self._param_reads = {}
        
        self.example_tag_repo_service_key = HydrusData.GenerateKey()
        
        services = []
        
        services.append( ClientServices.GenerateService( CC.LOCAL_BOORU_SERVICE_KEY, HC.LOCAL_BOORU, 'local booru' ) )
        services.append( ClientServices.GenerateService( CC.CLIENT_API_SERVICE_KEY, HC.CLIENT_API_SERVICE, 'client api' ) )
        services.append( ClientServices.GenerateService( CC.COMBINED_LOCAL_FILE_SERVICE_KEY, HC.COMBINED_LOCAL_FILE, 'all local files' ) )
        services.append( ClientServices.GenerateService( CC.LOCAL_FILE_SERVICE_KEY, HC.LOCAL_FILE_DOMAIN, 'my files' ) )
        services.append( ClientServices.GenerateService( CC.TRASH_SERVICE_KEY, HC.LOCAL_FILE_TRASH_DOMAIN, 'trash' ) )
        services.append( ClientServices.GenerateService( CC.DEFAULT_LOCAL_TAG_SERVICE_KEY, HC.LOCAL_TAG, 'my tags' ) )
        services.append( ClientServices.GenerateService( self.example_tag_repo_service_key, HC.TAG_REPOSITORY, 'example tag repo' ) )
        services.append( ClientServices.GenerateService( CC.COMBINED_TAG_SERVICE_KEY, HC.COMBINED_TAG, 'all known tags' ) )
        services.append( ClientServices.GenerateService( LOCAL_RATING_LIKE_SERVICE_KEY, HC.LOCAL_RATING_LIKE, 'example local rating like service' ) )
        services.append( ClientServices.GenerateService( LOCAL_RATING_NUMERICAL_SERVICE_KEY, HC.LOCAL_RATING_NUMERICAL, 'example local rating numerical service' ) )
        
        self._reads[ 'services' ] = services
        
        client_files_locations = {}
        
        for prefix in HydrusData.IterateHexPrefixes():
            
            for c in ( 'f', 't' ):
                
                client_files_locations[ c + prefix ] = client_files_default
                
            
        
        self._reads[ 'client_files_locations' ] = client_files_locations
        
        self._reads[ 'sessions' ] = []
        self._reads[ 'tag_parents' ] = {}
        self._reads[ 'tag_siblings_all_ideals' ] = {}
        self._reads[ 'inbox_hashes' ] = set()
        
        self._writes = collections.defaultdict( list )
        
        self._managers = {}
        
        self.column_list_manager = ClientGUIListManager.ColumnListManager()
        
        self.services_manager = ClientServices.ServicesManager( self )
        self.client_files_manager = ClientFiles.ClientFilesManager( self )
        
        self.parsing_cache = ClientCaches.ParsingCache()
        
        bandwidth_manager = ClientNetworkingBandwidth.NetworkBandwidthManager()
        session_manager = ClientNetworkingSessions.NetworkSessionManager()
        domain_manager = ClientNetworkingDomain.NetworkDomainManager()
        
        ClientDefaults.SetDefaultDomainManagerData( domain_manager )
        
        login_manager = ClientNetworkingLogin.NetworkLoginManager()
        
        self.network_engine = ClientNetworking.NetworkEngine( self, bandwidth_manager, session_manager, domain_manager, login_manager )
        
        self.CallToThreadLongRunning( self.network_engine.MainLoop )
        
        self.tag_display_manager = ClientTagsHandling.TagDisplayManager()
        
        self._managers[ 'undo' ] = ClientManagers.UndoManager( self )
        self.server_session_manager = HydrusSessions.HydrusSessionManagerServer()
        
        self.bitmap_manager = ClientManagers.BitmapManager( self )
        
        self.local_booru_manager = ClientCaches.LocalBooruCache( self )
        self.client_api_manager = ClientAPI.APIManager()
        
        self._cookies = {}
        
        self._job_scheduler = HydrusThreading.JobScheduler( self )
        
        self._job_scheduler.start()
        
    
    def _GetCallToThread( self ):
        
        for call_to_thread in self._call_to_threads:
            
            if not call_to_thread.CurrentlyWorking():
                
                return call_to_thread
                
            
        
        if len( self._call_to_threads ) > 100:
            
            raise Exception( 'Too many call to threads!' )
            
        
        call_to_thread = HydrusThreading.THREADCallToThread( self, 'CallToThread' )
        
        self._call_to_threads.append( call_to_thread )
        
        call_to_thread.start()
        
        return call_to_thread
        
    
    def _SetupQt( self ):
        
        self.locale = QC.QLocale() # Very important to init this here and keep it non garbage collected
        
        CC.GlobalPixmaps()
        
        self.frame_icon_pixmap = QG.QPixmap( os.path.join( HC.STATIC_DIR, 'hydrus_32_non-transparent.png' ) )
        
    
    def pub( self, topic, *args, **kwargs ):
        
        pass
        
    
    def pubimmediate( self, topic, *args, **kwargs ):
        
        self._pubsub.pubimmediate( topic, *args, **kwargs )
        
    
    def sub( self, object, method_name, topic ):
        
        self._pubsub.sub( object, method_name, topic )
        
    
    def AcquirePageKey( self ):
        
        return HydrusData.GenerateKey()
        
    
    def CallBlockingToQt( self, win, func, *args, **kwargs ):
        
        def qt_code( win: QW.QWidget, job_key: ClientThreading.JobKey ):
            
            try:
                
                if win is not None and not QP.isValid( win ):
                    
                    raise HydrusExceptions.QtDeadWindowException('Parent Window was destroyed before Qt command was called!')
                    
                
                result = func( *args, **kwargs )
                
                job_key.SetVariable( 'result', result )
                
            except ( HydrusExceptions.QtDeadWindowException, HydrusExceptions.DBCredentialsException, HydrusExceptions.ShutdownException ) as e:
                
                job_key.SetErrorException( e )
                
            except Exception as e:
                
                job_key.SetErrorException( e )
                
                HydrusData.Print( 'CallBlockingToQt just caught this error:' )
                HydrusData.DebugPrint( traceback.format_exc() )
                
            finally:
                
                job_key.Finish()
                
            
        
        job_key = ClientThreading.JobKey()
        
        job_key.Begin()
        
        QP.CallAfter( qt_code, win, job_key )
        
        while not job_key.IsDone():
            
            if HG.model_shutdown:
                
                raise HydrusExceptions.ShutdownException( 'Application is shutting down!' )
                
            
            time.sleep( 0.05 )
            
        
        if job_key.HasVariable( 'result' ):
            
            # result can be None, for qt_code that has no return variable
            
            result = job_key.GetIfHasVariable( 'result' )
            
            return result
            
        
        if job_key.HadError():
            
            e = job_key.GetErrorException()
            
            raise e
            
        
        raise HydrusExceptions.ShutdownException()
        
    
    def CallToThread( self, callable, *args, **kwargs ):
        
        call_to_thread = self._GetCallToThread()
        
        call_to_thread.put( callable, *args, **kwargs )
        
    
    CallToThreadLongRunning = CallToThread
    
    def CallAfterQtSafe( self, window, func, *args, **kwargs ):
        
        self.CallLaterQtSafe( window, 0, func, *args, **kwargs )
        
    
    def CallLater( self, initial_delay, func, *args, **kwargs ):
        
        call = HydrusData.Call( func, *args, **kwargs )
        
        job = HydrusThreading.SingleJob( self, self._job_scheduler, initial_delay, call )
        
        self._job_scheduler.AddJob( job )
        
        return job
        
    
    def CallLaterQtSafe( self, window, initial_delay, func, *args, **kwargs ):
        
        call = HydrusData.Call( func, *args, **kwargs )
        
        job = ClientThreading.QtAwareJob(self, self._job_scheduler, window, initial_delay, call)
        
        self._job_scheduler.AddJob( job )
        
        return job
        
    
    def CallRepeating( self, initial_delay, period, func, *args, **kwargs ):
        
        call = HydrusData.Call( func, *args, **kwargs )
        
        job = HydrusThreading.RepeatingJob( self, self._job_scheduler, initial_delay, period, call )
        
        self._job_scheduler.AddJob( job )
        
        return job
        
    
    def CallRepeatingQtSafe( self, window, initial_delay, period, func, *args, **kwargs ):
        
        call = HydrusData.Call( func, *args, **kwargs )
        
        job = ClientThreading.QtAwareRepeatingJob(self, self._job_scheduler, window, initial_delay, period, call)
        
        self._job_scheduler.AddJob( job )
        
        return job
        
    
    def ClearWrites( self, name ):
        
        if name in self._writes:
            
            del self._writes[ name ]
            
        
    
    def DBCurrentlyDoingJob( self ):
        
        return False
        
    
    def DoingFastExit( self ):
        
        return False
        
    
    def GetCurrentSessionPageAPIInfoDict( self ):
        
        return {
            "name" : "top pages notebook",
            "page_key" : "3b28d8a59ec61834325eb6275d9df012860a1ecfd9e1246423059bc47fb6d5bd",
            "page_type" : 10,
            "selected" : True,
            "pages" : [
                {
                    "name" : "files",
                    "page_key" : "d436ff5109215199913705eb9a7669d8a6b67c52e41c3b42904db083255ca84d",
                    "page_type" : 6,
                    "selected" : False
                },
                {
                    "name" : "thread watcher",
                    "page_key" : "40887fa327edca01e1d69b533dddba4681b2c43e0b4ebee0576177852e8c32e7",
                    "page_type" : 9,
                    "selected" : False
                },
                {
                    "name" : "pages",
                    "page_key" : "2ee7fa4058e1e23f2bd9e915cdf9347ae90902a8622d6559ba019a83a785c4dc",
                    "page_type" : 10,
                    "selected" : True,
                    "pages" : [
                        {
                            "name" : "urls",
                            "page_key" : "9fe22cb760d9ee6de32575ed9f27b76b4c215179cf843d3f9044efeeca98411f",
                            "page_type" : 7,
                            "selected" : True
                        },
                        {
                            "name" : "files",
                            "page_key" : "2977d57fc9c588be783727bcd54225d577b44e8aa2f91e365a3eb3c3f580dc4e",
                            "page_type" : 6,
                            "selected" : False
                        }
                    ]
                }	
            ]
        }
        
    
    def GetFilesDir( self ):
        
        return self._server_files_dir
        
    
    def GetMainTLW( self ):
        
        return self.win
        
    
    def GetNewOptions( self ):
        
        return self.new_options
        
    
    def GetManager( self, manager_type ):
        
        return self._managers[ manager_type ]
        
    
    def GetPageAPIInfoDict( self, page_key, simple ):
        
        return {}
        
    
    def GetWrite( self, name ):
        
        write = self._writes[ name ]
        
        del self._writes[ name ]
        
        return write
        
    
    def ImportURLFromAPI( self, url, filterable_tags, additional_service_keys_to_tags, destination_page_name, destination_page_key, show_destination_page ):
        
        normalised_url = self.network_engine.domain_manager.NormaliseURL( url )
        
        human_result_text = '"{}" URL added successfully.'.format( normalised_url )
        
        self.Write( 'import_url_test', url, filterable_tags, additional_service_keys_to_tags, destination_page_name, destination_page_key, show_destination_page )
        
        return ( normalised_url, human_result_text )
        
    
    def IsBooted( self ):
        
        return True
        
    
    def IsCurrentPage( self, page_key ):
        
        return False
        
    
    def IsFirstStart( self ):
        
        return True
        
    
    def isFullScreen( self ):
        
        return True # hackery for another test
        
    
    def IShouldRegularlyUpdate( self, window ):
        
        return True
        
    
    def JustWokeFromSleep( self ):
        
        return False
        
    
    def PageAlive( self, page_key ):
        
        return False
        
    
    def PageClosedButNotDestroyed( self, page_key ):
        
        return False
        
    
    def PauseAndDisconnect( self, pause_and_disconnect ):
        
        pass
        
    
    def Read( self, name, *args, **kwargs ):
        
        try:
            
            if ( name, args ) in self._param_reads:
                
                return self._param_reads[ ( name, args ) ]
                
            
        except:
            
            pass
            
        
        return self._reads[ name ]
        
    
    def RegisterUIUpdateWindow( self, window ):
        
        pass
        
    
    def ReleasePageKey( self, page_key ):
        
        pass
        
    
    def ReportDataUsed( self, num_bytes ):
        
        pass
        
    
    def ReportRequestUsed( self ):
        
        pass
        
    
    def ResetIdleTimer( self ): pass
    
    def Run( self, window ):
        
        # we are in Qt thread here, we can do this
        self._SetupQt()
        
        if self.only_run is None:
            
            run_all = True
            
        else:
            
            run_all = False
            
        
        # the gui stuff runs fine on its own but crashes in the full test if it is not early, wew
        # something to do with the delayed button clicking stuff
        
        module_lookup = collections.defaultdict( list )
        
        module_lookup[ 'all' ] = [
            TestDialogs,
            TestClientListBoxes,
            TestClientAPI,
            TestClientDaemons,
            TestClientConstants,
            TestClientData,
            TestClientImportOptions,
            TestClientParsing,
            TestClientTags,
            TestClientThreading,
            TestFunctions,
            TestHydrusSerialisable,
            TestHydrusSessions,
            TestClientDB,
            TestServerDB,
            TestClientDBDuplicates,
            TestClientDBTags,
            TestHydrusData,
            TestHydrusNATPunch,
            TestClientNetworking,
            TestHydrusNetworking,
            TestClientImportSubscriptions,
            TestClientImageHandling,
            TestClientMigration,
            TestHydrusServer
        ]
        
        module_lookup[ 'gui' ] = [
            TestDialogs,
            TestClientListBoxes
        ]
         
        module_lookup[ 'client_api' ] = [
            TestClientAPI
        ]
        
        module_lookup[ 'daemons' ] = [
            TestClientDaemons
        ]
        
        module_lookup[ 'data' ] = [
            TestClientConstants,
            TestClientData,
            TestClientImportOptions,
            TestClientParsing,
            TestClientTags,
            TestClientThreading,
            TestFunctions,
            TestHydrusData,
            TestHydrusSerialisable,
            TestHydrusSessions
        ]
        
        module_lookup[ 'tags_fast' ] = [
            TestClientTags
        ]
        
        module_lookup[ 'tags' ] = [
            TestClientTags,
            TestClientDBTags
        ]
        
        module_lookup[ 'db' ] = [
            TestClientDB,
            TestServerDB
        ]
        
        module_lookup[ 'db_duplicates' ] = [
            TestClientDBDuplicates
        ]
        
        module_lookup[ 'nat' ] = [
            TestHydrusNATPunch
        ]
        
        module_lookup[ 'networking' ] = [
            TestClientNetworking,
            TestHydrusNetworking
        ]
        
        module_lookup[ 'import' ] = [
            TestClientImportSubscriptions
        ]
        
        module_lookup[ 'image' ] = [
            TestClientImageHandling
        ]
        
        module_lookup[ 'migration' ] = [
            TestClientMigration
        ]
        
        module_lookup[ 'server' ] = [
            TestHydrusServer
        ]
        
        if run_all:
            
            modules = module_lookup[ 'all' ]
            
        else:
            
            modules = module_lookup[ self.only_run ]
            
        
        suites = [ unittest.TestLoader().loadTestsFromModule( module ) for module in modules ]
        
        suite = unittest.TestSuite( suites )
        
        runner = unittest.TextTestRunner( verbosity = 2 )
        
        runner.failfast = True
        
        def do_it():
            
            try:
                
                runner.run( suite )
                
            finally:
                
                QP.CallAfter( self.win.deleteLater )
                
            
        
        self.win.show()
        
        test_thread = threading.Thread( target = do_it )
        
        test_thread.start()
        
    
    def SetParamRead( self, name, args, value ):
        
        self._param_reads[ ( name, args ) ] = value
        
    
    def SetRead( self, name, value ):
        
        self._reads[ name ] = value
        
    
    def SetStatusBarDirty( self ):
        
        pass
        
    
    def SetWebCookies( self, name, value ):
        
        self._cookies[ name ] = value
        
    
    def ShouldStopThisWork( self, maintenance_mode, stop_time = None ):
        
        return False
        
    
    def ShowPage( self, page_key ):
        
        self.Write( 'show_page', page_key )
        
    
    def TidyUp( self ):
        
        time.sleep( 2 )
        
        HydrusPaths.DeletePath( self.db_dir )
        
    
    def WaitUntilModelFree( self ):
        
        return
        
    
    def WaitUntilViewFree( self ):
        
        return
        
    
    def Write( self, name, *args, **kwargs ):
        
        self._writes[ name ].append( ( args, kwargs ) )
        
    
    def WriteSynchronous( self, name, *args, **kwargs ):
        
        self._writes[ name ].append( ( args, kwargs ) )
        
        if name == 'import_file':
            
            ( file_import_job, ) = args
            
            if file_import_job.GetHash().hex() == 'a593942cb7ea9ffcd8ccf2f0fa23c338e23bfecd9a3e508dfc0bcf07501ead08': # 'blarg' in sha256 hex
                
                raise Exception( 'File failed to import for some reason!' )
                
            else:
                
                return ( CC.STATUS_SUCCESSFUL_AND_NEW, 'test note' )
                
            
        
    
