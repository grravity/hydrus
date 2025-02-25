import gc
import hashlib
import os
import psutil
import signal
import sys
import threading
import time
import traceback

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusController
from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusGlobals as HG
from hydrus.core import HydrusNetworking
from hydrus.core import HydrusPaths
from hydrus.core import HydrusSerialisable
from hydrus.core import HydrusThreading
from hydrus.core import HydrusVideoHandling

from hydrus.client import ClientAPI
from hydrus.client import ClientCaches
from hydrus.client import ClientConstants as CC
from hydrus.client import ClientDaemons
from hydrus.client import ClientDefaults
from hydrus.client import ClientDownloading
from hydrus.client import ClientFiles
from hydrus.client import ClientManagers
from hydrus.client import ClientOptions
from hydrus.client import ClientSearch
from hydrus.client import ClientServices
from hydrus.client import ClientThreading
from hydrus.client.db import ClientDB
from hydrus.client.gui import ClientGUI
from hydrus.client.gui import ClientGUIDialogs
from hydrus.client.gui import ClientGUIScrolledPanelsManagement
from hydrus.client.gui import ClientGUISplash
from hydrus.client.gui import ClientGUIStyle
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.lists import ClientGUIListManager
from hydrus.client.importing import ClientImportSubscriptions
from hydrus.client.metadata import ClientTags
from hydrus.client.metadata import ClientTagsHandling
from hydrus.client.networking import ClientNetworking
from hydrus.client.networking import ClientNetworkingBandwidth
from hydrus.client.networking import ClientNetworkingDomain
from hydrus.client.networking import ClientNetworkingLogin
from hydrus.client.networking import ClientNetworkingSessions

if not HG.twisted_is_broke:
    
    from twisted.internet import threads, reactor, defer
    
PubSubEventType = QC.QEvent.Type( QC.QEvent.registerEventType() )

class PubSubEvent( QC.QEvent ):
    
    def __init__( self ):
        
        QC.QEvent.__init__( self, PubSubEventType )
        
    
class PubSubEventCatcher( QC.QObject ):
    
    def __init__( self, parent, pubsub ):
        
        QC.QObject.__init__( self, parent )
        
        self._pubsub = pubsub
        
        self.installEventFilter( self )
        
    
    def eventFilter( self, watched, event ):
        
        if event.type() == PubSubEventType and isinstance( event, PubSubEvent ):
            
            if self._pubsub.WorkToDo():
                
                self._pubsub.Process()
                
            
            event.accept()
            
            return True
            
        
        return False
        
    
def MessageHandler( msg_type, context, text ):
    
    if msg_type not in ( QC.QtDebugMsg, QC.QtInfoMsg ):
        
        # Set a breakpoint here to be able to see where the warnings originate from.
        HydrusData.Print( text )
        

class App( QW.QApplication ):
    
    def __init__( self, pubsub, *args, **kwargs ):
        
        QW.QApplication.__init__( self, *args, **kwargs )
        
        self._pubsub = pubsub
        
        self.setApplicationName( 'Hydrus Client' )
        self.setApplicationVersion( str( HC.SOFTWARE_VERSION ) )
        
        QC.qInstallMessageHandler( MessageHandler )
        
        self.setQuitOnLastWindowClosed( False )
        
        self.call_after_catcher = QP.CallAfterEventCatcher( self )
        
        self.pubsub_catcher = PubSubEventCatcher( self, self._pubsub )
        
        self.aboutToQuit.connect( self.EventAboutToQuit )
        
    
    def EventAboutToQuit( self ):
        
        # If a user log-off causes the OS to call the Qt Application's quit/exit func, we still want to save and close nicely
        # once this lad is done, we are OUT of the mainloop, so if this is called and we are actually waiting on THREADExitEverything, let's wait a bit more
        
        # on Windows, the logoff routine kills the process once all top level windows are dead, so we have no chance to do post-app work lmaooooooooo
        # since splash screen may not appear in some cases, I now keep main gui alive but hidden until the quit call. it is never deleteLater'd
        
        # this is also called explicitly right at the end of the program. I set setQuitonLastWindowClosed False and then call quit explicitly, so it needs to be idempotent on the exit calls
        
        if HG.client_controller is not None:
            
            if HG.client_controller.ProgramIsShuttingDown():
                
                screw_it_time = HydrusData.GetNow() + 30
                
                while not HG.client_controller.ProgramIsShutDown():
                    
                    time.sleep( 0.5 )
                    
                    if HydrusData.TimeHasPassed( screw_it_time ):
                        
                        return
                        
                    
                
            else:
                
                HG.client_controller.SetDoingFastExit( True )
                
                HG.client_controller.Exit()
                
            
        
    
class Controller( HydrusController.HydrusController ):
    
    my_instance = None
    
    def __init__( self, db_dir ):
        
        self._qt_app_running = False
        self._is_booted = False
        self._program_is_shutting_down = False
        self._program_is_shut_down = False
        self._restore_backup_path = None
        
        self._splash = None
        
        self.gui = None
        
        HydrusController.HydrusController.__init__( self, db_dir )
        
        self._name = 'client'
        
        HG.client_controller = self
        
        # just to set up some defaults, in case some db update expects something for an odd yaml-loading reason
        self.options = ClientDefaults.GetClientDefaultOptions()
        self.new_options = ClientOptions.ClientOptions()
        
        HC.options = self.options
        
        self._page_key_lock = threading.Lock()
        
        self._thread_slots[ 'watcher_files' ] = ( 0, 15 )
        self._thread_slots[ 'watcher_check' ] = ( 0, 5 )
        self._thread_slots[ 'gallery_files' ] = ( 0, 15 )
        self._thread_slots[ 'gallery_search' ] = ( 0, 5 )
        
        self._alive_page_keys = set()
        self._closed_page_keys = set()
        
        self._last_last_session_hash = None
        
        self._last_mouse_position = None
        self._previously_idle = False
        self._idle_started = None
        
        self.client_files_manager = None
        self.services_manager = None
        
        Controller.my_instance = self
        
    
    def _InitDB( self ):
        
        return ClientDB.DB( self, self.db_dir, 'client' )
        
    
    def _InitTempDir( self ):
        
        self.temp_dir = HydrusPaths.GetTempDir()
        
    
    def _DestroySplash( self ):
        
        def qt_code( splash ):
            
            if splash and QP.isValid( splash ):
                
                splash.hide()
                
                splash.close()
                
                self.frame_splash_status.Reset()
                
            
        
        if self._splash is not None:
            
            splash = self._splash
            
            self._splash = None
            
            QP.CallAfter( qt_code, splash )
            
        
    
    def _GetPubsubValidCallable( self ):
        
        return QP.isValid
        
    
    def _GetUPnPServices( self ):
        
        return self.services_manager.GetServices( ( HC.LOCAL_BOORU, HC.CLIENT_API_SERVICE ) )
        
    
    def _GetWakeDelayPeriod( self ):
        
        return self.new_options.GetInteger( 'wake_delay_period' )
        
    
    def _PublishShutdownSubtext( self, text ):
        
        self.frame_splash_status.SetSubtext( text )
        
    
    def _ReportShutdownDaemonsStatus( self ):
        
        names = sorted( { daemon.name for daemon in self._daemons if daemon.is_alive() } )
        
        self.frame_splash_status.SetSubtext( ', '.join( names ) )
        
    
    def _ReportShutdownException( self ):
        
        text = 'A serious error occurred while trying to exit the program. Its traceback may be shown next. It should have also been written to client.log. You may need to quit the program from task manager.'
        
        HydrusData.DebugPrint( text )
        
        HydrusData.DebugPrint( traceback.format_exc() )
        
        if not self._doing_fast_exit:
            
            self.SafeShowCriticalMessage( 'shutdown error', text )
            self.SafeShowCriticalMessage( 'shutdown error', traceback.format_exc() )
            
        
        self._doing_fast_exit = True
        
    
    def _ShowJustWokeToUser( self ):
        
        def do_it( job_key: ClientThreading.JobKey ):
            
            while not HG.view_shutdown:
                
                with self._sleep_lock:
                    
                    if job_key.IsCancelled():
                        
                        self._timestamps[ 'now_awake' ] = HydrusData.GetNow()
                        
                        job_key.SetVariable( 'popup_text_1', 'enabling I/O now' )
                        
                        job_key.Delete()
                        
                        return
                        
                    
                    wake_time = self._timestamps[ 'now_awake' ]
                    
                
                if HydrusData.TimeHasPassed( wake_time ):
                    
                    job_key.Delete()
                    
                    return
                    
                else:
                    
                    job_key.SetVariable( 'popup_text_1', 'enabling I/O {}'.format( HydrusData.TimestampToPrettyTimeDelta( wake_time ) ) )
                    
                
                time.sleep( 0.5 )
                
            
        
        job_key = ClientThreading.JobKey( cancellable = True )
        
        job_key.SetVariable( 'popup_title', 'just woke up from sleep' )
        
        self.pub( 'message', job_key )
        
        self.CallToThread( do_it, job_key )
        
    
    
    def _ShutdownManagers( self ):
        
        managers = [ self.subscriptions_manager, self.tag_display_maintenance_manager ]
        
        for manager in managers:
            
            manager.Shutdown()
            
        
        started = HydrusData.GetNow()
        
        while False in ( manager.IsShutdown() for manager in managers ):
            
            time.sleep( 0.1 )
            
            if HydrusData.TimeHasPassed( started + 30 ):
                
                break
                
            
        
    
    @staticmethod
    def instance() -> 'Controller':
        
        if Controller.my_instance is None:
            
            raise Exception( 'Controller is not yet initialised!' )
            
        else:
            
            return Controller.my_instance
            
        
    
    def AcquirePageKey( self ):
        
        with self._page_key_lock:
            
            page_key = HydrusData.GenerateKey()
            
            self._alive_page_keys.add( page_key )
            
            return page_key
            
        
    
    def CallBlockingToQt( self, win, func, *args, **kwargs ):
        
        def qt_code( win: QW.QWidget, job_key: ClientThreading.JobKey ):
            
            try:
                
                if win is not None and not QP.isValid( win ):
                    
                    if HG.view_shutdown:
                        
                        raise HydrusExceptions.ShutdownException( 'Application is shutting down!' )
                        
                    else:
                        
                        raise HydrusExceptions.QtDeadWindowException('Parent Window was destroyed before Qt command was called!')
                        
                    
                
                result = func( *args, **kwargs )
                
                job_key.SetVariable( 'result', result )
                
            except ( HydrusExceptions.QtDeadWindowException, HydrusExceptions.DBCredentialsException, HydrusExceptions.ShutdownException, HydrusExceptions.CancelledException ) as e:
                
                job_key.SetErrorException( e )
                
            except Exception as e:
                
                job_key.SetErrorException( e )
                
                HydrusData.Print( 'CallBlockingToQt just caught this error:' )
                HydrusData.DebugPrint( traceback.format_exc() )
                
            finally:
                
                job_key.Finish()
                
            
        
        job_key = ClientThreading.JobKey( cancel_on_shutdown = False )
        
        job_key.Begin()
        
        QP.CallAfter( qt_code, win, job_key )
        
        while not job_key.IsDone():
            
            if not self._qt_app_running:
                
                raise HydrusExceptions.ShutdownException( 'Application is shutting down!' )
                
            
            time.sleep( 0.02 )
            
        
        if job_key.HasVariable( 'result' ):
            
            # result can be None, for qt_code that has no return variable
            
            result = job_key.GetIfHasVariable( 'result' )
            
            return result
            
        
        if job_key.HadError():
            
            e = job_key.GetErrorException()
            
            raise e
            
        
        raise HydrusExceptions.ShutdownException()
        
    
    def CallAfterQtSafe( self, window, func, *args, **kwargs ) -> ClientThreading.QtAwareJob:
        
        return self.CallLaterQtSafe( window, 0, func, *args, **kwargs )
        
    
    def CallLaterQtSafe( self, window, initial_delay, func, *args, **kwargs ) -> ClientThreading.QtAwareJob:
        
        job_scheduler = self._GetAppropriateJobScheduler( initial_delay )
        
        call = HydrusData.Call( func, *args, **kwargs )
        
        job = ClientThreading.QtAwareJob( self, job_scheduler, window, initial_delay, call )
        
        if job_scheduler is not None:
            
            job_scheduler.AddJob( job )
            
        
        return job
        
    
    def CallRepeatingQtSafe(self, window, initial_delay, period, func, *args, **kwargs):
        
        job_scheduler = self._GetAppropriateJobScheduler( period )
        
        call = HydrusData.Call( func, *args, **kwargs )
        
        job = ClientThreading.QtAwareRepeatingJob(self, job_scheduler, window, initial_delay, period, call)
        
        if job_scheduler is not None:
            
            job_scheduler.AddJob( job )
            
        
        return job
        
    
    def CatchSignal( self, sig, frame ):
        
        if self._program_is_shutting_down:
            
            return
            
        
        if sig == signal.SIGINT:
            
            if self.gui is not None and QP.isValid( self.gui ):
                
                event = QG.QCloseEvent()
                
                QW.QApplication.instance().postEvent( self.gui, event )
                
            else:
                
                QP.CallAfter( QW.QApplication.instance().quit )
                
            
        elif sig == signal.SIGTERM:
            
            QP.CallAfter( QW.QApplication.instance().quit )
            
        
    
    def CheckAlreadyRunning( self ):
        
        while HydrusData.IsAlreadyRunning( self.db_dir, 'client' ):
            
            self.frame_splash_status.SetText( 'client already running' )
            
            def qt_code():
                
                from hydrus.client.gui import ClientGUIDialogsQuick
                
                message = 'It looks like another instance of this client is already running, so this instance cannot start.'
                message += os.linesep * 2
                message += 'If the old instance is closing and does not quit for a _very_ long time, it is usually safe to force-close it from task manager.'
                
                result = ClientGUIDialogsQuick.GetYesNo( self._splash, message, title = 'The client is already running.', yes_label = 'wait a bit, then try again', no_label = 'forget it' )
                
                if result != QW.QDialog.Accepted:
                    
                    raise HydrusExceptions.ShutdownException()
                    
                
            
            self.CallBlockingToQt(self._splash, qt_code)
            
            for i in range( 10, 0, -1 ):
                
                if not HydrusData.IsAlreadyRunning( self.db_dir, 'client' ):
                    
                    break
                    
                
                self.frame_splash_status.SetText( 'waiting {} seconds'.format( i ) )
                
                time.sleep( 1 )
                
            
        
    
    def CheckMouseIdle( self ):
        
        mouse_position = QG.QCursor.pos()
        
        if self._last_mouse_position is None:
            
            self._last_mouse_position = mouse_position
            
        elif mouse_position != self._last_mouse_position:
            
            idle_before_position_update = self.CurrentlyIdle()
            
            self._timestamps[ 'last_mouse_action' ] = HydrusData.GetNow()
            
            self._last_mouse_position = mouse_position
            
            idle_after_position_update = self.CurrentlyIdle()
            
            move_knocked_us_out_of_idle = ( not idle_before_position_update ) and idle_after_position_update
            
            if move_knocked_us_out_of_idle:
                
                self.pub( 'set_status_bar_dirty' )
                
            
        
    
    def ClosePageKeys( self, page_keys ):
        
        with self._page_key_lock:
            
            self._closed_page_keys.update( page_keys )
            
        
    
    def CreateSplash( self, title ):
        
        if self._splash is not None:
            
            self._DestroySplash()
            
        
        try:
            
            self.frame_splash_status.Reset()
            
            self._splash = ClientGUISplash.FrameSplash( self, title, self.frame_splash_status )
            
        except:
            
            HydrusData.Print( 'There was an error trying to start the splash screen!' )
            
            HydrusData.Print( traceback.format_exc() )
            
            raise
            
        
    
    def CurrentlyIdle( self ):
        
        if self._program_is_shutting_down:
            
            return False
            
        
        if HG.force_idle_mode:
            
            self._idle_started = 0
            
            return True
            
        
        if not HydrusData.TimeHasPassed( self._timestamps[ 'boot' ] + 120 ):
            
            return False
            
        
        idle_normal = self.options[ 'idle_normal' ]
        idle_period = self.options[ 'idle_period' ]
        idle_mouse_period = self.options[ 'idle_mouse_period' ]
        
        if idle_normal:
            
            currently_idle = True
            
            if idle_period is not None:
                
                if not HydrusData.TimeHasPassed( self._timestamps[ 'last_user_action' ] + idle_period ):
                    
                    currently_idle = False
                    
                
            
            if idle_mouse_period is not None:
                
                if not HydrusData.TimeHasPassed( self._timestamps[ 'last_mouse_action' ] + idle_mouse_period ):
                    
                    currently_idle = False
                    
                
            
        else:
            
            currently_idle = False
            
        
        turning_idle = currently_idle and not self._previously_idle
        
        self._previously_idle = currently_idle
        
        if turning_idle:
            
            self._idle_started = HydrusData.GetNow()
            
            self.pub( 'wake_daemons' )
            
        
        if not currently_idle:
            
            self._idle_started = None
            
        
        return currently_idle
        
    
    def CurrentlyVeryIdle( self ):
        
        if self._program_is_shutting_down:
            
            return False
            
        
        if self._idle_started is not None and HydrusData.TimeHasPassed( self._idle_started + 3600 ):
            
            return True
            
        
        return False
        
    
    def DoIdleShutdownWork( self ):
        
        self.frame_splash_status.SetSubtext( 'db' )
        
        stop_time = HydrusData.GetNow() + ( self.options[ 'idle_shutdown_max_minutes' ] * 60 )
        
        self.MaintainDB( maintenance_mode = HC.MAINTENANCE_SHUTDOWN, stop_time = stop_time )
        
        if not self.options[ 'pause_repo_sync' ]:
            
            services = self.services_manager.GetServices( HC.REPOSITORIES, randomised = True )
            
            for service in services:
                
                if HydrusData.TimeHasPassed( stop_time ):
                    
                    return
                    
                
                self.frame_splash_status.SetSubtext( '{} processing'.format( service.GetName() ) )
                
                service.SyncProcessUpdates( maintenance_mode = HC.MAINTENANCE_SHUTDOWN, stop_time = stop_time )
                
            
        
        self.Write( 'last_shutdown_work_time', HydrusData.GetNow() )
        
    
    def Exit( self ):
        
        # this is idempotent and does not stop. we are shutting down now or in the very near future
        
        if self._program_is_shutting_down:
            
            return
            
        
        self._program_is_shutting_down = True
        
        if not self._is_booted:
            
            self._doing_fast_exit = True
            
        
        try:
            
            if not self._doing_fast_exit:
                
                self.CreateSplash( 'hydrus client exiting' )
                
                if HG.do_idle_shutdown_work:
                    
                    self._splash.ShowCancelShutdownButton()
                    
                
            
            if self.gui is not None and QP.isValid( self.gui ):
                
                self.gui.SaveAndHide()
                
            
        except Exception:
            
            self._ReportShutdownException()
            
        
        if self._doing_fast_exit:
            
            HydrusData.DebugPrint( 'doing fast shutdown\u2026' )
            
            self.THREADExitEverything()
            
        else:
            
            self.CallToThreadLongRunning( self.THREADExitEverything )
            
        
    
    def GetClipboardText( self ):
        
        clipboard_text = QW.QApplication.clipboard().text()
        
        if not clipboard_text:
            
            raise HydrusExceptions.DataMissing( 'No text on the clipboard!' )
            
        
        return clipboard_text
        
    
    def GetDefaultMPVConfPath( self ):
        
        return os.path.join( HC.STATIC_DIR, 'mpv-conf', 'default_mpv.conf' )
        
    
    def GetIdleShutdownWorkDue( self, time_to_stop ):
        
        work_to_do = []
        
        work_to_do.extend( self.Read( 'maintenance_due', time_to_stop ) )
        
        services = self.services_manager.GetServices( HC.REPOSITORIES )
        
        for service in services:
            
            if service.CanDoIdleShutdownWork():
                
                work_to_do.append( service.GetName() + ' repository processing' )
                
            
        
        return work_to_do
        
    
    def GetMainTLW( self ):
        
        if self.gui is not None:
            
            return self.gui
            
        elif self._splash is not None:
            
            return self._splash
            
        else:
            
            return None
            
        
    
    def GetMPVConfPath( self ):
        
        return os.path.join( self.db_dir, 'mpv.conf' )
        
    
    def GetNewOptions( self ):
        
        return self.new_options
        
    
    def InitClientFilesManager( self ):
        
        def qt_code( missing_locations ):
            
            with ClientGUITopLevelWindowsPanels.DialogManage( None, 'repair file system' ) as dlg:
                
                panel = ClientGUIScrolledPanelsManagement.RepairFileSystemPanel( dlg, missing_locations )
                
                dlg.SetPanel( panel )
                
                if dlg.exec() == QW.QDialog.Accepted:
                    
                    self.client_files_manager = ClientFiles.ClientFilesManager( self )
                    
                    missing_locations = self.client_files_manager.GetMissing()
                    
                else:
                    
                    raise HydrusExceptions.ShutdownException( 'File system failed, user chose to quit.' )
                    
                
            
            return missing_locations
            
        
        self.client_files_manager = ClientFiles.ClientFilesManager( self )
        
        self.files_maintenance_manager = ClientFiles.FilesMaintenanceManager( self )
        
        missing_locations = self.client_files_manager.GetMissing()
        
        while len( missing_locations ) > 0:
            
            missing_locations = self.CallBlockingToQt( self._splash, qt_code, missing_locations )
            
        
    
    def InitModel( self ):
        
        self.frame_splash_status.SetTitleText( 'booting db\u2026' )
        
        HydrusController.HydrusController.InitModel( self )
        
        self.frame_splash_status.SetText( 'initialising managers' )
        
        self.frame_splash_status.SetSubtext( 'services' )
        
        self.services_manager = ClientServices.ServicesManager( self )
        
        self.frame_splash_status.SetSubtext( 'options' )
        
        self.options = self.Read( 'options' )
        self.new_options = self.Read( 'serialisable', HydrusSerialisable.SERIALISABLE_TYPE_CLIENT_OPTIONS )
        
        HC.options = self.options
        
        if self.new_options.GetBoolean( 'use_system_ffmpeg' ):
            
            if HydrusVideoHandling.FFMPEG_PATH.startswith( HC.BIN_DIR ):
                
                HydrusVideoHandling.FFMPEG_PATH = os.path.basename( HydrusVideoHandling.FFMPEG_PATH )
                
            
        
        # important this happens before repair, as repair dialog has a column list lmao
        
        column_list_manager = self.Read( 'serialisable', HydrusSerialisable.SERIALISABLE_TYPE_COLUMN_LIST_MANAGER )
        
        if column_list_manager is None:
            
            column_list_manager = ClientGUIListManager.ColumnListManager()
            
            column_list_manager._dirty = True
            
            self.SafeShowCriticalMessage( 'Problem loading object', 'Your list manager was missing on boot! I have recreated a new empty one with default settings. Please check that your hard drive and client are ok and let the hydrus dev know the details if there is a mystery.' )
            
        
        self.column_list_manager = column_list_manager
        
        self.frame_splash_status.SetSubtext( 'client files' )
        
        self.InitClientFilesManager()
        
        #
        
        self.frame_splash_status.SetSubtext( 'network' )
        
        self.parsing_cache = ClientCaches.ParsingCache()
        
        client_api_manager = self.Read( 'serialisable', HydrusSerialisable.SERIALISABLE_TYPE_CLIENT_API_MANAGER )
        
        if client_api_manager is None:
            
            client_api_manager = ClientAPI.APIManager()
            
            client_api_manager._dirty = True
            
            self.SafeShowCriticalMessage( 'Problem loading object', 'Your client api manager was missing on boot! I have recreated a new empty one. Please check that your hard drive and client are ok and let the hydrus dev know the details if there is a mystery.' )
            
        
        self.client_api_manager = client_api_manager
        
        bandwidth_manager = self.Read( 'serialisable', HydrusSerialisable.SERIALISABLE_TYPE_NETWORK_BANDWIDTH_MANAGER )
        
        if bandwidth_manager is None:
            
            bandwidth_manager = ClientNetworkingBandwidth.NetworkBandwidthManager()
            
            tracker_containers = self.Read( 'serialisable_named', HydrusSerialisable.SERIALISABLE_TYPE_NETWORK_BANDWIDTH_MANAGER_TRACKER_CONTAINER )
            
            bandwidth_manager.SetTrackerContainers( tracker_containers )
            
            ClientDefaults.SetDefaultBandwidthManagerRules( bandwidth_manager )
            
            bandwidth_manager.SetDirty()
            
            self.SafeShowCriticalMessage( 'Problem loading object', 'Your bandwidth manager was missing on boot! I have recreated a new one. It may have your bandwidth record, but some/all may be missing. Your rules have been reset to default. Please check that your hard drive and client are ok and let the hydrus dev know the details if there is a mystery.' )
            
        
        session_manager = self.Read( 'serialisable', HydrusSerialisable.SERIALISABLE_TYPE_NETWORK_SESSION_MANAGER )
        
        if session_manager is None:
            
            session_manager = ClientNetworkingSessions.NetworkSessionManager()
            
            session_containers = self.Read( 'serialisable_named', HydrusSerialisable.SERIALISABLE_TYPE_NETWORK_SESSION_MANAGER_SESSION_CONTAINER )
            
            session_manager.SetSessionContainers( session_containers )
            
            session_manager.SetDirty()
            
            self.SafeShowCriticalMessage( 'Problem loading object', 'Your session manager was missing on boot! I have recreated a new one. It may have your sessions, or some/all may be missing. Please check that your hard drive and client are ok and let the hydrus dev know the details if there is a mystery.' )
            
        
        domain_manager = self.Read( 'serialisable', HydrusSerialisable.SERIALISABLE_TYPE_NETWORK_DOMAIN_MANAGER )
        
        if domain_manager is None:
            
            domain_manager = ClientNetworkingDomain.NetworkDomainManager()
            
            ClientDefaults.SetDefaultDomainManagerData( domain_manager )
            
            domain_manager._dirty = True
            
            self.SafeShowCriticalMessage( 'Problem loading object', 'Your domain manager was missing on boot! I have recreated a new empty one. Please check that your hard drive and client are ok and let the hydrus dev know the details if there is a mystery.' )
            
        
        domain_manager.Initialise()
        
        login_manager = self.Read( 'serialisable', HydrusSerialisable.SERIALISABLE_TYPE_NETWORK_LOGIN_MANAGER )
        
        if login_manager is None:
            
            login_manager = ClientNetworkingLogin.NetworkLoginManager()
            
            ClientDefaults.SetDefaultLoginManagerScripts( login_manager )
            
            login_manager._dirty = True
            
            self.SafeShowCriticalMessage( 'Problem loading object', 'Your login manager was missing on boot! I have recreated a new empty one. Please check that your hard drive and client are ok and let the hydrus dev know the details if there is a mystery.' )
            
        
        login_manager.Initialise()
        
        self.network_engine = ClientNetworking.NetworkEngine( self, bandwidth_manager, session_manager, domain_manager, login_manager )
        
        self.CallToThreadLongRunning( self.network_engine.MainLoop )
        
        #
        
        self.quick_download_manager = ClientDownloading.QuickDownloadManager( self )
        
        self.CallToThreadLongRunning( self.quick_download_manager.MainLoop )
        
        #
        
        self.local_booru_manager = ClientCaches.LocalBooruCache( self )
        
        self.file_viewing_stats_manager = ClientManagers.FileViewingStatsManager( self )
        
        #
        
        self.frame_splash_status.SetSubtext( 'tag display' )
        
        # note that this has to be made before siblings/parents managers, as they rely on it
        
        tag_display_manager = self.Read( 'serialisable', HydrusSerialisable.SERIALISABLE_TYPE_TAG_DISPLAY_MANAGER )
        
        if tag_display_manager is None:
            
            tag_display_manager = ClientTagsHandling.TagDisplayManager()
            
            tag_display_manager._dirty = True
            
            self.SafeShowCriticalMessage( 'Problem loading object', 'Your tag display manager was missing on boot! I have recreated a new empty one. Please check that your hard drive and client are ok and let the hydrus dev know the details if there is a mystery.' )
            
        
        self.tag_display_manager = tag_display_manager
        
        self.tag_display_maintenance_manager = ClientTagsHandling.TagDisplayMaintenanceManager( self )
        
        self.tag_display_maintenance_manager.Start()
        
        #
        
        self.frame_splash_status.SetSubtext( 'favourite searches' )
        
        favourite_search_manager = self.Read( 'serialisable', HydrusSerialisable.SERIALISABLE_TYPE_FAVOURITE_SEARCH_MANAGER )
        
        if favourite_search_manager is None:
            
            favourite_search_manager = ClientSearch.FavouriteSearchManager()
            
            ClientDefaults.SetDefaultFavouriteSearchManagerData( favourite_search_manager )
            
            favourite_search_manager._dirty = True
            
            self.SafeShowCriticalMessage( 'Problem loading object', 'Your favourite searches manager was missing on boot! I have recreated a new empty one. Please check that your hard drive and client are ok and let the hydrus dev know the details if there is a mystery.' )
            
        
        self.favourite_search_manager = favourite_search_manager
        
        #
        
        self._managers[ 'undo' ] = ClientManagers.UndoManager( self )
        
        self.frame_splash_status.SetSubtext( 'image caches' )
        
        # careful: outside of qt since they don't need qt for init, seems ok _for now_
        self._caches[ 'images' ] = ClientCaches.RenderedImageCache( self )
        self._caches[ 'thumbnail' ] = ClientCaches.ThumbnailCache( self )
        self.bitmap_manager = ClientManagers.BitmapManager( self )
        
        self.sub( self, 'ToClipboard', 'clipboard' )
        
    
    def InitView( self ):
        
        if self.options[ 'password' ] is not None:
            
            self.frame_splash_status.SetText( 'waiting for password' )
            
            def qt_code_password():
                
                while True:
                    
                    with ClientGUIDialogs.DialogTextEntry( self._splash, 'Enter your password.', allow_blank = False, password_entry = True, min_char_width = 24 ) as dlg:
                        
                        if dlg.exec() == QW.QDialog.Accepted:
                            
                            password_bytes = bytes( dlg.GetValue(), 'utf-8' )
                            
                            if hashlib.sha256( password_bytes ).digest() == self.options[ 'password' ]:
                                
                                break
                                
                            
                        else:
                            
                            raise HydrusExceptions.DBCredentialsException( 'Bad password check' )
                            
                        
                    
                
            
            self.CallBlockingToQt( self._splash, qt_code_password )
            
        
        self.frame_splash_status.SetTitleText( 'booting gui\u2026' )
        
        subscriptions = HG.client_controller.Read( 'serialisable_named', HydrusSerialisable.SERIALISABLE_TYPE_SUBSCRIPTION )
        
        self.subscriptions_manager = ClientImportSubscriptions.SubscriptionsManager( self, subscriptions )
        
        def qt_code_gui():
            
            shortcut_sets = HG.client_controller.Read( 'serialisable_named', HydrusSerialisable.SERIALISABLE_TYPE_SHORTCUT_SET )
            
            from hydrus.client.gui import ClientGUIShortcuts
            
            ClientGUIShortcuts.ShortcutsManager( shortcut_sets = shortcut_sets )
            
            ClientGUIStyle.InitialiseDefaults()
            
            qt_style_name = self.new_options.GetNoneableString( 'qt_style_name' )
            
            if qt_style_name is not None:
                
                try:
                    
                    ClientGUIStyle.SetStyleFromName( qt_style_name )
                    
                except Exception as e:
                    
                    HydrusData.Print( 'Could not load Qt style: {}'.format( e ) )
                    
                
            
            qt_stylesheet_name = self.new_options.GetNoneableString( 'qt_stylesheet_name' )
            
            if qt_stylesheet_name is None:
                
                ClientGUIStyle.ClearStylesheet()
                
            else:
                
                try:
                    
                    ClientGUIStyle.SetStylesheetFromPath( qt_stylesheet_name )
                    
                except Exception as e:
                    
                    HydrusData.Print( 'Could not load Qt stylesheet: {}'.format( e ) )
                    
                
            
            self.gui = ClientGUI.FrameGUI( self )
            
            self.ResetIdleTimer()
            
        
        self.CallBlockingToQt( self._splash, qt_code_gui )
        
        # ShowText will now popup as a message, as popup message manager has overwritten the hooks
        
        HydrusController.HydrusController.InitView( self )
        
        self._service_keys_to_connected_ports = {}
        
        self.RestartClientServerServices()
        
        if not HG.no_daemons:
            
            self._daemons.append( HydrusThreading.DAEMONForegroundWorker( self, 'MaintainTrash', ClientDaemons.DAEMONMaintainTrash, init_wait = 120 ) )
            
        
        self.files_maintenance_manager.Start()
        
        job = self.CallRepeating( 0.0, 30.0, self.SaveDirtyObjectsImportant )
        job.WakeOnPubSub( 'important_dirt_to_clean' )
        self._daemon_jobs[ 'save_dirty_objects_important' ] = job
        
        job = self.CallRepeating( 0.0, 300.0, self.SaveDirtyObjectsInfrequent )
        self._daemon_jobs[ 'save_dirty_objects_infrequent' ] = job
        
        job = self.CallRepeating( 5.0, 3600.0, self.SynchroniseAccounts )
        job.ShouldDelayOnWakeup( True )
        job.WakeOnPubSub( 'notify_unknown_accounts' )
        self._daemon_jobs[ 'synchronise_accounts' ] = job
        
        job = self.CallRepeating( 5.0, 3600.0 * 4, self.SynchroniseRepositories )
        job.ShouldDelayOnWakeup( True )
        job.WakeOnPubSub( 'notify_restart_repo_sync' )
        job.WakeOnPubSub( 'notify_new_permissions' )
        job.WakeOnPubSub( 'wake_idle_workers' )
        self._daemon_jobs[ 'synchronise_repositories' ] = job
        
        job = self.CallRepeatingQtSafe( self, 10.0, 10.0, self.CheckMouseIdle )
        self._daemon_jobs[ 'check_mouse_idle' ] = job
        
        if self.db.IsFirstStart():
            
            message = 'Hi, this looks like the first time you have started the hydrus client.'
            message += os.linesep * 2
            message += 'Don\'t forget to check out the help if you haven\'t already--it has an extensive \'getting started\' section, including how to update and the importance of backing up your database.'
            message += os.linesep * 2
            message += 'To dismiss popup messages like this, right-click them.'
            
            HydrusData.ShowText( message )
            
        
        if self.db.IsDBUpdated():
            
            HydrusData.ShowText( 'The client has updated to version {}!'.format( HC.SOFTWARE_VERSION ) )
            
        
        for message in self.db.GetInitialMessages():
            
            HydrusData.ShowText( message )
            
        
    
    def IsBooted( self ):
        
        return self._is_booted
        
    
    def MaintainDB( self, maintenance_mode = HC.MAINTENANCE_IDLE, stop_time = None ):
        
        if maintenance_mode == HC.MAINTENANCE_IDLE and not self.GoodTimeToStartBackgroundWork():
            
            return
            
        
        if self.ShouldStopThisWork( maintenance_mode, stop_time = stop_time ):
            
            return
            
        
        tree_stop_time = stop_time
        
        if tree_stop_time is None:
            
            tree_stop_time = HydrusData.GetNow() + 30
            
        
        self.WriteSynchronous( 'maintain_similar_files_tree', maintenance_mode = maintenance_mode, stop_time = tree_stop_time )
        
        if self.ShouldStopThisWork( maintenance_mode, stop_time = stop_time ):
            
            return
            
        
        if self.new_options.GetBoolean( 'maintain_similar_files_duplicate_pairs_during_idle' ):
            
            search_distance = self.new_options.GetInteger( 'similar_files_duplicate_pairs_search_distance' )
            
            search_stop_time = stop_time
            
            if search_stop_time is None:
                
                search_stop_time = HydrusData.GetNow() + 60
                
            
            self.WriteSynchronous( 'maintain_similar_files_search_for_potential_duplicates', search_distance, maintenance_mode = maintenance_mode, stop_time = search_stop_time )
            
            from hydrus.client import ClientDuplicates
            
            ClientDuplicates.DuplicatesManager.instance().RefreshMaintenanceNumbers()
            
        
        if self.ShouldStopThisWork( maintenance_mode, stop_time = stop_time ):
            
            return
            
        
        self.WriteSynchronous( 'vacuum', maintenance_mode = maintenance_mode, stop_time = stop_time )
        
        if self.ShouldStopThisWork( maintenance_mode, stop_time = stop_time ):
            
            return
            
        
        self.WriteSynchronous( 'analyze', maintenance_mode = maintenance_mode, stop_time = stop_time )
        
        if self.ShouldStopThisWork( maintenance_mode, stop_time = stop_time ):
            
            return
            
        
    
    def MaintainMemoryFast( self ):
        
        HydrusController.HydrusController.MaintainMemoryFast( self )
        
        self.parsing_cache.CleanCache()
        
    
    def MaintainMemorySlow( self ):
        
        HydrusController.HydrusController.MaintainMemorySlow( self )
        
        if HydrusData.TimeHasPassed( self._timestamps[ 'last_page_change' ] + 30 * 60 ):
            
            self.pub( 'delete_old_closed_pages' )
            
            self._timestamps[ 'last_page_change' ] = HydrusData.GetNow()
            
        
        def do_gui_refs( gui ):
            
            if self.gui is not None and QP.isValid( self.gui ):
                
                self.gui.MaintainCanvasFrameReferences()
                
            
        
        QP.CallAfter( do_gui_refs, self.gui )
        
    
    def PageAlive( self, page_key ):
        
        with self._page_key_lock:
            
            return page_key in self._alive_page_keys
            
        
    
    def PageClosedButNotDestroyed( self, page_key ):
        
        with self._page_key_lock:
            
            return page_key in self._closed_page_keys
            
        
    
    def PrepStringForDisplay( self, text ):
        
        return text.lower()
        
    
    def ProgramIsShutDown( self ):
        
        return self._program_is_shut_down
        
    
    def ProgramIsShuttingDown( self ):
        
        return self._program_is_shutting_down
        
    
    def pub( self, *args, **kwargs ):
        
        HydrusController.HydrusController.pub( self, *args, **kwargs )
        
        QW.QApplication.instance().postEvent( QW.QApplication.instance().pubsub_catcher, PubSubEvent() )
        
    
    def RefreshServices( self ):
        
        self.services_manager.RefreshServices()
        
    
    def ReleasePageKey( self, page_key ):
        
        with self._page_key_lock:
            
            self._alive_page_keys.discard( page_key )
            self._closed_page_keys.discard( page_key )
            
        
    
    def ReportFirstSessionLoaded( self ):
        
        job = self.CallRepeating( 5.0, 180.0, ClientDaemons.DAEMONCheckImportFolders )
        job.WakeOnPubSub( 'notify_restart_import_folders_daemon' )
        job.WakeOnPubSub( 'notify_new_import_folders' )
        job.ShouldDelayOnWakeup( True )
        self._daemon_jobs[ 'import_folders' ] = job
        
        job = self.CallRepeating( 5.0, 180.0, ClientDaemons.DAEMONCheckExportFolders )
        job.WakeOnPubSub( 'notify_restart_export_folders_daemon' )
        job.WakeOnPubSub( 'notify_new_export_folders' )
        job.ShouldDelayOnWakeup( True )
        self._daemon_jobs[ 'export_folders' ] = job
        
        self.subscriptions_manager.Start()
        
    
    def ResetPageChangeTimer( self ):
        
        self._timestamps[ 'last_page_change' ] = HydrusData.GetNow()
        
    
    def RestartClientServerServices( self ):
        
        services = [ self.services_manager.GetService( service_key ) for service_key in ( CC.LOCAL_BOORU_SERVICE_KEY, CC.CLIENT_API_SERVICE_KEY ) ]
        
        services = [ service for service in services if service.GetPort() is not None ]
        
        self.CallToThreadLongRunning( self.SetRunningTwistedServices, services )
        
    
    def RestoreDatabase( self ):
        
        from hydrus.client.gui import ClientGUIDialogsQuick
        
        with QP.DirDialog( self.gui, 'Select backup location.' ) as dlg:
            
            if dlg.exec() == QW.QDialog.Accepted:
                
                path = dlg.GetPath()
                
                text = 'Are you sure you want to restore a backup from "{}"?'.format( path )
                text += os.linesep * 2
                text += 'Everything in your current database will be deleted!'
                text += os.linesep * 2
                text += 'The gui will shut down, and then it will take a while to complete the restore. Once it is done, the client will restart.'
                
                result = ClientGUIDialogsQuick.GetYesNo( self.gui, text )
                
                if result == QW.QDialog.Accepted:
                    
                    self._restore_backup_path = path
                    self._doing_fast_exit = False
                    HG.do_idle_shutdown_work = False
                    HG.restart = True
                    
                    self.Exit()
                    
                
            
        
    
    def Run( self ):
        
        QP.MonkeyPatchMissingMethods()
        
        from hydrus.client.gui import ClientGUICore
        
        ClientGUICore.GUICore()
        
        self.app = App( self._pubsub, sys.argv )
        
        self.main_qt_thread = self.app.thread()
        
        HydrusData.Print( 'booting controller\u2026' )
        
        self.frame_icon_pixmap = QG.QPixmap( os.path.join( HC.STATIC_DIR, 'hydrus_32_non-transparent.png' ) )
        
        self.frame_splash_status = ClientGUISplash.FrameSplashStatus()
        
        self.CreateSplash( 'hydrus client booting' )
        
        signal.signal( signal.SIGINT, self.CatchSignal )
        signal.signal( signal.SIGTERM, self.CatchSignal )
        
        self.CallToThreadLongRunning( self.THREADBootEverything )
        
        self._qt_app_running = True
        
        try:
            
            self.app.exec_()
            
        finally:
            
            self._qt_app_running = False
            
        
        HydrusData.DebugPrint( 'shutting down controller\u2026' )
        
    
    def SafeShowCriticalMessage( self, title, message ):
        
        HydrusData.DebugPrint( title )
        HydrusData.DebugPrint( message )
        
        if QC.QThread.currentThread() == QW.QApplication.instance().thread():
            
            QW.QMessageBox.critical( None, title, message )
            
        else:
            
            self.CallBlockingToQt( self.app, QW.QMessageBox.critical, None, title, message )
            
        
    
    def SaveDirtyObjectsImportant( self ):
        
        with HG.dirty_object_lock:
            
            dirty_services = [ service for service in self.services_manager.GetServices() if service.IsDirty() ]
            
            if len( dirty_services ) > 0:
                
                self.frame_splash_status.SetSubtext( 'services' )
                
                self.WriteSynchronous( 'dirty_services', dirty_services )
                
            
            if self.client_api_manager.IsDirty():
                
                self.frame_splash_status.SetSubtext( 'client api manager' )
                
                self.WriteSynchronous( 'serialisable', self.client_api_manager )
                
                self.client_api_manager.SetClean()
                
            
            if self.network_engine.domain_manager.IsDirty():
                
                self.frame_splash_status.SetSubtext( 'domain manager' )
                
                self.WriteSynchronous( 'serialisable', self.network_engine.domain_manager )
                
                self.network_engine.domain_manager.SetClean()
                
            
            if self.network_engine.login_manager.IsDirty():
                
                self.frame_splash_status.SetSubtext( 'login manager' )
                
                self.WriteSynchronous( 'serialisable', self.network_engine.login_manager )
                
                self.network_engine.login_manager.SetClean()
                
            
            if self.favourite_search_manager.IsDirty():
                
                self.frame_splash_status.SetSubtext( 'favourite searches manager' )
                
                self.WriteSynchronous( 'serialisable', self.favourite_search_manager )
                
                self.favourite_search_manager.SetClean()
                
            
            if self.tag_display_manager.IsDirty():
                
                self.frame_splash_status.SetSubtext( 'tag display manager' )
                
                self.WriteSynchronous( 'serialisable', self.tag_display_manager )
                
                self.tag_display_manager.SetClean()
                
            
        
    
    def SaveDirtyObjectsInfrequent( self ):
        
        with HG.dirty_object_lock:
            
            if self.column_list_manager.IsDirty():
                
                self.frame_splash_status.SetSubtext( 'column list manager' )
                
                self.WriteSynchronous( 'serialisable', self.column_list_manager )
                
                self.column_list_manager.SetClean()
                
            
            if self.network_engine.bandwidth_manager.IsDirty() or self.network_engine.bandwidth_manager.HasDirtyTrackerContainers():
                
                self.frame_splash_status.SetSubtext( 'bandwidth manager' )
                
                self.WriteSynchronous( 'serialisable', self.network_engine.bandwidth_manager )
                
                self.network_engine.bandwidth_manager.SetClean()
                
            
            if self.network_engine.session_manager.IsDirty() or self.network_engine.session_manager.HasDirtySessionContainers():
                
                self.frame_splash_status.SetSubtext( 'session manager' )
                
                self.WriteSynchronous( 'serialisable', self.network_engine.session_manager )
                
                self.network_engine.session_manager.SetClean()
                
            
        
    
    def SaveGUISession( self, session ):
        
        name = session.GetName()
        
        if name == 'last session':
            
            session_hash = hashlib.sha256( bytes( session.DumpToString(), 'utf-8' ) ).digest()
            
            if session_hash == self._last_last_session_hash:
                
                return
                
            
            self._last_last_session_hash = session_hash
            
        
        self.WriteSynchronous( 'serialisable', session )
        
        self.pub( 'notify_new_sessions' )
        
    
    def SetRunningTwistedServices( self, services ):
        
        def TWISTEDDoIt():
            
            def StartServices( *args, **kwargs ):
                
                HydrusData.Print( 'starting services\u2026' )
                
                for service in services:
                    
                    service_key = service.GetServiceKey()
                    service_type = service.GetServiceType()
                    
                    name = service.GetName()
                    
                    port = service.GetPort()
                    allow_non_local_connections = service.AllowsNonLocalConnections()
                    use_https = service.UseHTTPS()
                    
                    if port is None:
                        
                        continue
                        
                    
                    try:
                        
                        if use_https:
                            
                            import twisted.internet.ssl
                            
                            ( ssl_cert_path, ssl_key_path ) = self.db.GetSSLPaths()
                            
                            sslmethod = twisted.internet.ssl.SSL.TLSv1_2_METHOD
                            
                            context_factory = twisted.internet.ssl.DefaultOpenSSLContextFactory( ssl_key_path, ssl_cert_path, sslmethod )
                            
                        
                        from hydrus.client import ClientLocalServer
                        
                        if service_type == HC.LOCAL_BOORU:
                            
                            http_factory = ClientLocalServer.HydrusServiceBooru( service, allow_non_local_connections = allow_non_local_connections )
                            
                        elif service_type == HC.CLIENT_API_SERVICE:
                            
                            http_factory = ClientLocalServer.HydrusServiceClientAPI( service, allow_non_local_connections = allow_non_local_connections )
                            
                        
                        ipv6_port = None
                        
                        try:
                            
                            if use_https:
                                
                                ipv6_port = reactor.listenSSL( port, http_factory, context_factory, interface = '::' )
                                
                            else:
                                
                                ipv6_port = reactor.listenTCP( port, http_factory, interface = '::' )
                                
                            
                        except Exception as e:
                            
                            HydrusData.Print( 'Could not bind to IPv6:' )
                            
                            HydrusData.Print( str( e ) )
                            
                        
                        ipv4_port = None
                        
                        try:
                            
                            if use_https:
                                
                                ipv4_port = reactor.listenSSL( port, http_factory, context_factory )
                                
                            else:
                                
                                ipv4_port = reactor.listenTCP( port, http_factory )
                                
                            
                        except:
                            
                            if ipv6_port is None:
                                
                                raise
                                
                            
                        
                        self._service_keys_to_connected_ports[ service_key ] = ( ipv4_port, ipv6_port )
                        
                        if not HydrusNetworking.LocalPortInUse( port ):
                            
                            HydrusData.ShowText( 'Tried to bind port {} for "{}" but it failed.'.format( port, name ) )
                            
                        
                    except Exception as e:
                        
                        HydrusData.ShowText( 'Could not start "{}":'.format( name ) )
                        HydrusData.ShowException( e )
                        
                    
                
                HydrusData.Print( 'services started' )
                
            
            if len( self._service_keys_to_connected_ports ) > 0:
                
                HydrusData.Print( 'stopping services\u2026' )
                
                deferreds = []
                
                for ( ipv4_port, ipv6_port ) in self._service_keys_to_connected_ports.values():
                    
                    if ipv4_port is not None:
                        
                        deferred = defer.maybeDeferred( ipv4_port.stopListening )
                        
                        deferreds.append( deferred )
                        
                    
                    if ipv6_port is not None:
                        
                        deferred = defer.maybeDeferred( ipv6_port.stopListening )
                        
                        deferreds.append( deferred )
                        
                    
                
                self._service_keys_to_connected_ports = {}
                
                deferred = defer.DeferredList( deferreds )
                
                if len( services ) > 0:
                    
                    deferred.addCallback( StartServices )
                    
                
            elif len( services ) > 0:
                
                StartServices()
                
            
        
        if HG.twisted_is_broke:
            
            if True in ( service.GetPort() is not None for service in services ):
                
                HydrusData.ShowText( 'Twisted failed to import, so could not start the local booru/client api! Please contact hydrus dev!' )
                
            
        else:
            
            threads.blockingCallFromThread( reactor, TWISTEDDoIt )
            
        
    
    def SetServices( self, services ):
        
        with HG.dirty_object_lock:
            
            previous_services = self.services_manager.GetServices()
            previous_service_keys = { service.GetServiceKey() for service in previous_services }
            
            upnp_services = [ service for service in services if service.GetServiceType() in ( HC.LOCAL_BOORU, HC.CLIENT_API_SERVICE ) ]
            
            self.CallToThreadLongRunning( self.services_upnp_manager.SetServices, upnp_services )
            
            self.WriteSynchronous( 'update_services', services )
            
            self.services_manager.RefreshServices()
            
        
        self.RestartClientServerServices()
        
    
    def ShutdownModel( self ):
        
        self.frame_splash_status.SetText( 'saving and exiting objects' )
        
        if self._is_booted:
            
            self.frame_splash_status.SetSubtext( 'file viewing stats flush' )
            
            self.file_viewing_stats_manager.Flush()
            
            self.frame_splash_status.SetSubtext( '' )
            
            self.SaveDirtyObjectsImportant()
            self.SaveDirtyObjectsInfrequent()
            
        
        HydrusController.HydrusController.ShutdownModel( self )
        
    
    def ShutdownView( self ):
        
        if not self._doing_fast_exit:
            
            self.frame_splash_status.SetText( 'waiting for managers to exit' )
            
            self._ShutdownManagers()
            
            self.frame_splash_status.SetText( 'waiting for daemons to exit' )
            
            self._ShutdownDaemons()
            
            self.frame_splash_status.SetSubtext( '' )
            
            if HG.do_idle_shutdown_work:
                
                self.frame_splash_status.SetText( 'waiting for idle shutdown work' )
                
                try:
                    
                    self.DoIdleShutdownWork()
                    
                    self.frame_splash_status.SetSubtext( '' )
                    
                except:
                    
                    self._ReportShutdownException()
                    
                
            
            self.frame_splash_status.SetSubtext( 'files maintenance manager' )
            
            self.files_maintenance_manager.Shutdown()
            
            self.frame_splash_status.SetSubtext( 'download manager' )
            
            self.quick_download_manager.Shutdown()
            
            self.frame_splash_status.SetSubtext( '' )
            
            try:
                
                self.frame_splash_status.SetText( 'waiting for twisted to exit' )
                
                self.SetRunningTwistedServices( [] )
                
            except:
                
                pass # sometimes this throws a wobbler, screw it
                
            
        
        HydrusController.HydrusController.ShutdownView( self )
        
    
    def SynchroniseAccounts( self ):
        
        services = self.services_manager.GetServices( HC.RESTRICTED_SERVICES, randomised = True )
        
        for service in services:
            
            if HydrusThreading.IsThreadShuttingDown():
                
                return
                
            
            service.SyncAccount()
            
        
    
    def SynchroniseRepositories( self ):
        
        if not self.options[ 'pause_repo_sync' ]:
            
            services = self.services_manager.GetServices( HC.REPOSITORIES, randomised = True )
            
            for service in services:
                
                if HydrusThreading.IsThreadShuttingDown():
                    
                    return
                    
                
                if self.options[ 'pause_repo_sync' ]:
                    
                    return
                    
                
                service.SyncRemote()
                
                service.SyncProcessUpdates( maintenance_mode = HC.MAINTENANCE_IDLE )
                
                if HydrusThreading.IsThreadShuttingDown():
                    
                    return
                    
                
                time.sleep( 1 )
                
            
        
    
    def SystemBusy( self ):
        
        if HG.force_idle_mode:
            
            return False
            
        
        max_cpu = self.options[ 'idle_cpu_max' ]
        
        if max_cpu is None:
            
            self._system_busy = False
            
        else:
            
            if HydrusData.TimeHasPassed( self._timestamps[ 'last_cpu_check' ] + 60 ):
                
                cpu_times = psutil.cpu_percent( percpu = True )
                
                if True in ( cpu_time > max_cpu for cpu_time in cpu_times ):
                    
                    self._system_busy = True
                    
                else:
                    
                    self._system_busy = False
                    
                
                self._timestamps[ 'last_cpu_check' ] = HydrusData.GetNow()
                
            
        
        return self._system_busy
        
    
    def THREADBootEverything( self ):
        
        try:
            
            self.CheckAlreadyRunning()
            
        except HydrusExceptions.ShutdownException:
            
            self._DestroySplash()
            
            QP.CallAfter( QW.QApplication.quit )
            
            return
            
        
        try:
            
            self.RecordRunningStart()
            
            self.InitModel()
            
            self.InitView()
            
            self._is_booted = True
            
        except ( HydrusExceptions.DBCredentialsException, HydrusExceptions.ShutdownException ) as e:
            
            HydrusData.Print( e )
            
            self.CleanRunningFile()
            
            QP.CallAfter( QW.QApplication.quit )
            
        except Exception as e:
            
            text = 'A serious error occurred while trying to start the program. The error will be shown next in a window. More information may have been written to client.log.'
            
            HydrusData.DebugPrint( 'If the db crashed, another error may be written just above ^.' )
            HydrusData.DebugPrint( text )
            
            HydrusData.DebugPrint( traceback.format_exc() )
            
            self.SafeShowCriticalMessage( 'boot error', text )
            
            self.SafeShowCriticalMessage( 'boot error', traceback.format_exc() )
            
            QP.CallAfter( QW.QApplication.exit, 1 )
            
        finally:
            
            self._DestroySplash()
            
        
    
    def THREADExitEverything( self ):
        
        try:
            
            gc.collect()
            
            self.frame_splash_status.SetTitleText( 'shutting down gui\u2026' )
            
            self.ShutdownView()
            
            self.frame_splash_status.SetTitleText( 'shutting down db\u2026' )
            
            self.ShutdownModel()
            
            if self._restore_backup_path is not None:
                
                self.frame_splash_status.SetTitleText( 'restoring backup\u2026' )
                
                self.db.RestoreBackup( self._restore_backup_path )
                
            
            self.frame_splash_status.SetTitleText( 'cleaning up\u2026' )
            
            self.CleanRunningFile()
            
        except ( HydrusExceptions.DBCredentialsException, HydrusExceptions.ShutdownException ):
            
            pass
            
        except:
            
            self._ReportShutdownException()
            
        finally:
            
            QW.QApplication.instance().setProperty( 'exit_complete', True )
            
            self._DestroySplash()
            
            self._program_is_shut_down = True
            
            QP.CallAfter( QW.QApplication.quit )
            
        
    
    def ToClipboard( self, data_type, data ):
        
        # need this cause can't do it in a non-gui thread
        
        if data_type == 'paths':
            
            paths = []
            
            for path in data:
                
                paths.append( QC.QUrl.fromLocalFile( path ) )
                
            
            mime_data = QC.QMimeData()
            
            mime_data.setUrls( paths )
            
            QW.QApplication.clipboard().setMimeData( mime_data )
            
        elif data_type == 'text':
            
            text = data
            
            QW.QApplication.clipboard().setText( text )
            
        elif data_type == 'bmp':
            
            media = data
            
            image_renderer = self.GetCache( 'images' ).GetImageRenderer( media )
            
            def CopyToClipboard():
                
                qt_image = image_renderer.GetQtImage().copy()
                
                QW.QApplication.clipboard().setImage( qt_image )
                
            
            def THREADWait():
                
                start_time = time.time()
                
                while not image_renderer.IsReady():
                    
                    if HydrusData.TimeHasPassed( start_time + 15 ):
                        
                        HydrusData.ShowText( 'The image did not render in fifteen seconds, so the attempt to copy it to the clipboard was abandoned.' )
                        
                        return
                        
                    
                    time.sleep( 0.1 )
                    
                
                QP.CallAfter( CopyToClipboard )
                
            
            self.CallToThreadLongRunning( THREADWait )
            
        
    
    def UnclosePageKeys( self, page_keys ):
        
        with self._page_key_lock:
            
            self._closed_page_keys.difference_update( page_keys )
            
        
    
    def WaitUntilViewFree( self ):
        
        self.WaitUntilModelFree()
        
        self.WaitUntilThumbnailsFree()
        
    
    def WaitUntilThumbnailsFree( self ):
        
        self._caches[ 'thumbnail' ].WaitUntilFree()
        
    
    def Write( self, action, *args, **kwargs ):
        
        if action == 'content_updates':
            
            self._managers[ 'undo' ].AddCommand( 'content_updates', *args, **kwargs )
            
        
        return HydrusController.HydrusController.Write( self, action, *args, **kwargs )
        
    
