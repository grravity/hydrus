import os
import time
import traceback

from twisted.internet import reactor, defer
from twisted.internet.threads import deferToThread
from twisted.python.failure import Failure
from twisted.web.server import NOT_DONE_YET
from twisted.web.resource import Resource
from twisted.web.static import File as FileResource, NoRangeStaticProducer, SingleRangeStaticProducer, MultipleRangeStaticProducer

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusFileHandling
from hydrus.core import HydrusGlobals as HG
from hydrus.core import HydrusImageHandling
from hydrus.core import HydrusNetworking
from hydrus.core import HydrusPaths
from hydrus.core import HydrusSerialisable

def GenerateEris( service ):
    
    name = service.GetName()
    service_type = service.GetServiceType()
    
    allows_non_local_connections = service.AllowsNonLocalConnections()
    
    welcome_text_1 = 'This is <b>' + name + '</b>,'
    welcome_text_2 = 'a ' + HC.service_string_lookup[ service_type ] + '.'
    welcome_text_3 = 'Software version ' + str( HC.SOFTWARE_VERSION )
    
    if service_type == HC.CLIENT_API_SERVICE:
        
        welcome_text_4 = 'API version ' + str( HC.CLIENT_API_VERSION )
        
    else:
        
        welcome_text_4 = 'Network version ' + str( HC.NETWORK_VERSION )
        
    
    if allows_non_local_connections:
        
        welcome_text_5 = 'It responds to requests from any host.'
        
    else:
        
        welcome_text_5 = 'It only responds to requests from localhost.'
        
    
    return '''<html><head><title>''' + name + '''</title></head><body><pre>
                         <font color="red">8888  8888888</font>
                  <font color="red">888888888888888888888888</font>
               <font color="red">8888</font>:::<font color="red">8888888888888888888888888</font>
             <font color="red">8888</font>::::::<font color="red">8888888888888888888888888888</font>
            <font color="red">88</font>::::::::<font color="red">888</font>:::<font color="red">8888888888888888888888888</font>
          <font color="red">88888888</font>::::<font color="red">8</font>:::::::::::<font color="red">88888888888888888888</font>
        <font color="red">888 8</font>::<font color="red">888888</font>::::::::::::::::::<font color="red">88888888888   888</font>
           <font color="red">88</font>::::<font color="red">88888888</font>::::<font color="gray">m</font>::::::::::<font color="red">88888888888    8</font>
         <font color="red">888888888888888888</font>:<font color="gray">M</font>:::::::::::<font color="red">8888888888888</font>
        <font color="red">88888888888888888888</font>::::::::::::<font color="gray">M</font><font color="red">88888888888888</font>
        <font color="red">8888888888888888888888</font>:::::::::<font color="gray">M</font><font color="red">8888888888888888</font>
         <font color="red">8888888888888888888888</font>:::::::<font color="gray">M</font><font color="red">888888888888888888</font>
        <font color="red">8888888888888888</font>::<font color="red">88888</font>::::::<font color="gray">M</font><font color="red">88888888888888888888</font>
      <font color="red">88888888888888888</font>:::<font color="red">88888</font>:::::<font color="gray">M</font><font color="red">888888888888888   8888</font>
     <font color="red">88888888888888888</font>:::<font color="red">88888</font>::::<font color="gray">M</font>::<font color="black">;o</font><font color="maroon">*</font><font color="green">M</font><font color="maroon">*</font><font color="black">o;</font><font color="red">888888888    88</font>
    <font color="red">88888888888888888</font>:::<font color="red">8888</font>:::::<font color="gray">M</font>:::::::::::<font color="red">88888888    8</font>
   <font color="red">88888888888888888</font>::::<font color="red">88</font>::::::<font color="gray">M</font>:<font color="gray">;</font>:::::::::::<font color="red">888888888</font>
  <font color="red">8888888888888888888</font>:::<font color="red">8</font>::::::<font color="gray">M</font>::<font color="gray">aAa</font>::::::::<font color="gray">M</font><font color="red">8888888888       8</font>
  <font color="red">88   8888888888</font>::<font color="red">88</font>::::<font color="red">8</font>::::<font color="gray">M</font>:::::::::::::<font color="red">888888888888888 8888</font>
 <font color="red">88  88888888888</font>:::<font color="red">8</font>:::::::::<font color="gray">M</font>::::::::::;::<font color="red">88</font><font color="black">:</font><font color="red">88888888888888888</font>
 <font color="red">8  8888888888888</font>:::::::::::<font color="gray">M</font>::<font color="violet">&quot;@@@@@@@&quot;</font>::::<font color="red">8</font><font color="gray">w</font><font color="red">8888888888888888</font>
  <font color="red">88888888888</font>:<font color="red">888</font>::::::::::<font color="gray">M</font>:::::<font color="violet">&quot;@a@&quot;</font>:::::<font color="gray">M</font><font color="red">8</font><font color="gray">i</font><font color="red">888888888888888</font>
 <font color="red">8888888888</font>::::<font color="red">88</font>:::::::::<font color="gray">M</font><font color="red">88</font>:::::::::::::<font color="gray">M</font><font color="red">88</font><font color="gray">z</font><font color="red">88888888888888888</font>
<font color="red">8888888888</font>:::::<font color="red">8</font>:::::::::<font color="gray">M</font><font color="red">88888</font>:::::::::<font color="gray">MM</font><font color="red">888</font><font color="gray">!</font><font color="red">888888888888888888</font>
<font color="red">888888888</font>:::::<font color="red">8</font>:::::::::<font color="gray">M</font><font color="red">8888888</font><font color="gray">MAmmmAMVMM</font><font color="red">888</font><font color="gray">*</font><font color="red">88888888   88888888</font>
<font color="red">888888</font> <font color="gray">M</font>:::::::::::::::<font color="gray">M</font><font color="red">888888888</font>:::::::<font color="gray">MM</font><font color="red">88888888888888   8888888</font>
<font color="red">8888</font>   <font color="gray">M</font>::::::::::::::<font color="gray">M</font><font color="red">88888888888</font>::::::<font color="gray">MM</font><font color="red">888888888888888    88888</font>
 <font color="red">888</font>   <font color="gray">M</font>:::::::::::::<font color="gray">M</font><font color="red">8888888888888</font><font color="gray">M</font>:::::<font color="gray">mM</font><font color="red">888888888888888    8888</font>
  <font color="red">888</font>  <font color="gray">M</font>::::::::::::<font color="gray">M</font><font color="red">8888</font>:<font color="red">888888888888</font>::::<font color="gray">m</font>::<font color="gray">Mm</font><font color="red">88888 888888   8888</font>
   <font color="red">88</font>  <font color="gray">M</font>::::::::::::<font color="red">8888</font>:<font color="red">88888888888888888</font>::::::<font color="gray">Mm</font><font color="red">8   88888   888</font>
   <font color="red">88</font>  <font color="gray">M</font>::::::::::<font color="red">8888</font><font color="gray">M</font>::<font color="red">88888</font>::<font color="red">888888888888</font>:::::::<font color="gray">Mm</font><font color="red">88888    88</font>
   <font color="red">8</font>   <font color="gray">MM</font>::::::::<font color="red">8888</font><font color="gray">M</font>:::<font color="red">8888</font>:::::<font color="red">888888888888</font>::::::::<font color="gray">Mm</font><font color="red">8     4</font>              ''' + welcome_text_1 + '''
       <font color="red">8</font><font color="gray">M</font>:::::::<font color="red">8888</font><font color="gray">M</font>:::::<font color="red">888</font>:::::::<font color="red">88</font>:::<font color="red">8888888</font>::::::::<font color="gray">Mm</font>    <font color="red">2</font>              ''' + welcome_text_2 + '''
      <font color="red">88</font><font color="gray">MM</font>:::::<font color="red">8888</font><font color="gray">M</font>:::::::<font color="red">88</font>::::::::<font color="red">8</font>:::::<font color="red">888888</font>:::<font color="gray">M</font>:::::<font color="gray">M</font>
     <font color="red">8888</font><font color="gray">M</font>:::::<font color="red">888</font><font color="gray">MM</font>::::::::<font color="red">8</font>:::::::::::<font color="gray">M</font>::::<font color="red">8888</font>::::<font color="gray">M</font>::::<font color="gray">M</font>                  ''' + welcome_text_3 + '''
    <font color="red">88888</font><font color="gray">M</font>:::::<font color="red">88</font>:<font color="gray">M</font>::::::::::<font color="red">8</font>:::::::::::<font color="gray">M</font>:::<font color="red">8888</font>::::::<font color="gray">M</font>::<font color="gray">M</font>                  ''' + welcome_text_4 + '''
   <font color="red">88 888</font><font color="gray">MM</font>:::<font color="red">888</font>:<font color="gray">M</font>:::::::::::::::::::::::<font color="gray">M</font>:<font color="red">8888</font>:::::::::<font color="gray">M</font>:
   <font color="red">8 88888</font><font color="gray">M</font>:::<font color="red">88</font>::<font color="gray">M</font>:::::::::::::::::::::::<font color="gray">MM</font>:<font color="red">88</font>::::::::::::<font color="gray">M</font>                 ''' + welcome_text_5 + '''
     <font color="red">88888</font><font color="gray">M</font>:::<font color="red">88</font>::<font color="gray">M</font>::::::::::<font color="thistle">*88*</font>::::::::::<font color="gray">M</font>:<font color="red">88</font>::::::::::::::<font color="gray">M</font>
    <font color="red">888888</font><font color="gray">M</font>:::<font color="red">88</font>::<font color="gray">M</font>:::::::::<font color="thistle">88@@88</font>:::::::::<font color="gray">M</font>::<font color="red">88</font>::::::::::::::<font color="gray">M</font>
    <font color="red">888888</font><font color="gray">MM</font>::<font color="red">88</font>::<font color="gray">MM</font>::::::::<font color="thistle">88@@88</font>:::::::::<font color="gray">M</font>:::<font color="red">8</font>::::::::::::::<font color="thistle">*8</font>
    <font color="red">88888</font>  <font color="gray">M</font>:::<font color="red">8</font>::<font color="gray">MM</font>:::::::::<font color="thistle">*88*</font>::::::::::<font color="gray">M</font>:::::::::::::::::<font color="thistle">88@@</font>
    <font color="red">8888</font>   <font color="gray">MM</font>::::::<font color="gray">MM</font>:::::::::::::::::::::<font color="gray">MM</font>:::::::::::::::::<font color="thistle">88@@</font>
     <font color="red">888</font>    <font color="gray">M</font>:::::::<font color="gray">MM</font>:::::::::::::::::::<font color="gray">MM</font>::<font color="gray">M</font>::::::::::::::::<font color="thistle">*8</font>
     <font color="red">888</font>    <font color="gray">MM</font>:::::::<font color="gray">MMM</font>::::::::::::::::<font color="gray">MM</font>:::<font color="gray">MM</font>:::::::::::::::<font color="gray">M</font>
      <font color="red">88</font>     <font color="gray">M</font>::::::::<font color="gray">MMMM</font>:::::::::::<font color="gray">MMMM</font>:::::<font color="gray">MM</font>::::::::::::<font color="gray">MM</font>
       <font color="red">88</font>    <font color="gray">MM</font>:::::::::<font color="gray">MMMMMMMMMMMMMMM</font>::::::::<font color="gray">MMM</font>::::::::<font color="gray">MMM</font>
        <font color="red">88</font>    <font color="gray">MM</font>::::::::::::<font color="gray">MMMMMMM</font>::::::::::::::<font color="gray">MMMMMMMMMM</font>
         <font color="red">88   8</font><font color="gray">MM</font>::::::::::::::::::::::::::::::::::<font color="gray">MMMMMM</font>
          <font color="red">8   88</font><font color="gray">MM</font>::::::::::::::::::::::<font color="gray">M</font>:::<font color="gray">M</font>::::::::<font color="gray">MM</font>
              <font color="red">888</font><font color="gray">MM</font>::::::::::::::::::<font color="gray">MM</font>::::::<font color="gray">MM</font>::::::<font color="gray">MM</font>
             <font color="red">88888</font><font color="gray">MM</font>:::::::::::::::<font color="gray">MMM</font>:::::::<font color="gray">mM</font>:::::<font color="gray">MM</font>
             <font color="red">888888</font><font color="gray">MM</font>:::::::::::::<font color="gray">MMM</font>:::::::::<font color="gray">MMM</font>:::<font color="gray">M</font>
            <font color="red">88888888</font><font color="gray">MM</font>:::::::::::<font color="gray">MMM</font>:::::::::::<font color="gray">MM</font>:::<font color="gray">M</font>
           <font color="red">88 8888888</font><font color="gray">M</font>:::::::::<font color="gray">MMM</font>::::::::::::::<font color="gray">M</font>:::<font color="gray">M</font>
           <font color="red">8  888888</font> <font color="gray">M</font>:::::::<font color="gray">MM</font>:::::::::::::::::<font color="gray">M</font>:::<font color="gray">M</font>:
              <font color="red">888888</font> <font color="gray">M</font>::::::<font color="gray">M</font>:::::::::::::::::::<font color="gray">M</font>:::<font color="gray">MM</font>
             <font color="red">888888</font>  <font color="gray">M</font>:::::<font color="gray">M</font>::::::::::::::::::::::::<font color="gray">M</font>:<font color="gray">M</font>
             <font color="red">888888</font>  <font color="gray">M</font>:::::<font color="gray">M</font>:::::::::<font color="gray">@</font>::::::::::::::<font color="gray">M</font>::<font color="gray">M</font>
             <font color="red">88888</font>   <font color="gray">M</font>::::::::::::::<font color="gray">@@</font>:::::::::::::::<font color="gray">M</font>::<font color="gray">M</font>
            <font color="red">88888</font>   <font color="gray">M</font>::::::::::::::<font color="gray">@@@</font>::::::::::::::::<font color="gray">M</font>::<font color="gray">M</font>
           <font color="red">88888</font>   <font color="gray">M</font>:::::::::::::::<font color="gray">@@</font>::::::::::::::::::<font color="gray">M</font>::<font color="gray">M</font>
          <font color="red">88888</font>   <font color="gray">M</font>:::::<font color="gray">m</font>::::::::::<font color="gray">@</font>::::::::::<font color="gray">Mm</font>:::::::<font color="gray">M</font>:::<font color="gray">M</font>
          <font color="red">8888</font>   <font color="gray">M</font>:::::<font color="gray">M</font>:::::::::::::::::::::::<font color="gray">MM</font>:::::::<font color="gray">M</font>:::<font color="gray">M</font>
         <font color="red">8888</font>   <font color="gray">M</font>:::::<font color="gray">M</font>:::::::::::::::::::::::<font color="gray">MMM</font>::::::::<font color="gray">M</font>:::<font color="gray">M</font>
        <font color="red">888</font>    <font color="gray">M</font>:::::<font color="gray">Mm</font>::::::::::::::::::::::<font color="gray">MMM</font>:::::::::<font color="gray">M</font>::::<font color="gray">M</font>
      <font color="red">8888</font>    <font color="gray">MM</font>::::<font color="gray">Mm</font>:::::::::::::::::::::<font color="gray">MMMM</font>:::::::::<font color="gray">m</font>::<font color="gray">m</font>:::<font color="gray">M</font>
     <font color="red">888</font>      <font color="gray">M</font>:::::<font color="gray">M</font>::::::::::::::::::::<font color="gray">MMM</font>::::::::::::<font color="gray">M</font>::<font color="gray">mm</font>:::<font color="gray">M</font>
  <font color="red">8888</font>       <font color="gray">MM</font>:::::::::::::::::::::::::<font color="gray">MM</font>:::::::::::::<font color="gray">mM</font>::<font color="gray">MM</font>:::<font color="gray">M</font>:
             <font color="gray">M</font>:::::::::::::::::::::::::<font color="gray">M</font>:::::::::::::::<font color="gray">mM</font>::<font color="gray">MM</font>:::<font color="gray">Mm</font>
            <font color="gray">MM</font>::::::<font color="gray">m</font>:::::::::::::::::::::::::::::::::::<font color="gray">M</font>::<font color="gray">MM</font>:::<font color="gray">MM</font>
            <font color="gray">M</font>::::::::<font color="gray">M</font>:::::::::::::::::::::::::::::::::::<font color="gray">M</font>::<font color="gray">M</font>:::<font color="gray">MM</font>
           <font color="gray">MM</font>:::::::::<font color="gray">M</font>:::::::::::::<font color="gray">M</font>:::::::::::::::::::::<font color="gray">M</font>:<font color="gray">M</font>:::<font color="gray">MM</font>
           <font color="gray">M</font>:::::::::::<font color="gray">M</font><font color="maroon">88</font>:::::::::<font color="gray">M</font>:::::::::::::::::::::::<font color="gray">MM</font>::<font color="gray">MMM</font> 
           <font color="gray">M</font>::::::::::::<font color="maroon">8888888888</font><font color="gray">M</font>::::::::::::::::::::::::<font color="gray">MM</font>::<font color="gray">MM</font> 
           <font color="gray">M</font>:::::::::::::<font color="maroon">88888888</font><font color="gray">M</font>:::::::::::::::::::::::::<font color="gray">M</font>::<font color="gray">MM</font>
           <font color="gray">M</font>::::::::::::::<font color="maroon">888888</font><font color="gray">M</font>:::::::::::::::::::::::::<font color="gray">M</font>::<font color="gray">MM</font>
           <font color="gray">M</font>:::::::::::::::<font color="maroon">88888</font><font color="gray">M</font>:::::::::::::::::::::::::<font color="gray">M</font>:<font color="gray">MM</font>
           <font color="gray">M</font>:::::::::::::::::<font color="maroon">88</font><font color="gray">M</font>::::::::::::::::::::::::::<font color="gray">MMM</font>
           <font color="gray">M</font>:::::::::::::::::::<font color="gray">M</font>::::::::::::::::::::::::::<font color="gray">MMM</font>
           <font color="gray">MM</font>:::::::::::::::::<font color="gray">M</font>::::::::::::::::::::::::::<font color="gray">MMM</font>
            <font color="gray">M</font>:::::::::::::::::<font color="gray">M</font>::::::::::::::::::::::::::<font color="gray">MMM</font>
            <font color="gray">MM</font>:::::::::::::::<font color="gray">M</font>::::::::::::::::::::::::::<font color="gray">MMM</font>
             <font color="gray">M</font>:::::::::::::::<font color="gray">M</font>:::::::::::::::::::::::::<font color="gray">MMM</font>
             <font color="gray">MM</font>:::::::::::::<font color="gray">M</font>:::::::::::::::::::::::::<font color="gray">MMM</font>
              <font color="gray">M</font>:::::::::::::<font color="gray">M</font>::::::::::::::::::::::::<font color="gray">MMM</font>
              <font color="gray">MM</font>:::::::::::<font color="gray">M</font>::::::::::::::::::::::::<font color="gray">MMM</font>
               <font color="gray">M</font>:::::::::::<font color="gray">M</font>:::::::::::::::::::::::<font color="gray">MMM</font>
               <font color="gray">MM</font>:::::::::<font color="gray">M</font>:::::::::::::::::::::::<font color="gray">MMM</font>
                <font color="gray">M</font>:::::::::<font color="gray">M</font>::::::::::::::::::::::<font color="gray">MMM</font>
                <font color="gray">MM</font>:::::::<font color="gray">M</font>::::::::::::::::::::::<font color="gray">MMM</font>
                 <font color="gray">MM</font>::::::<font color="gray">M</font>:::::::::::::::::::::<font color="gray">MMM</font>
                 <font color="gray">MM</font>:::::<font color="gray">M</font>:::::::::::::::::::::<font color="gray">MMM</font>
                  <font color="gray">MM</font>::::<font color="gray">M</font>::::::::::::::::::::<font color="gray">MMM</font> 
                  <font color="gray">MM</font>:::<font color="gray">M</font>::::::::::::::::::::<font color="gray">MMM</font>
                   <font color="gray">MM</font>::<font color="gray">M</font>:::::::::::::::::::<font color="gray">MMM</font>
                   <font color="gray">MM</font>:<font color="gray">M</font>:::::::::::::::::::<font color="gray">MMM</font>
                    <font color="gray">MMM</font>::::::::::::::::::<font color="gray">MMM</font>
                    <font color="gray">MM</font>::::::::::::::::::<font color="gray">MMM</font>
                     <font color="gray">M</font>:::::::::::::::::<font color="gray">MMM</font>
                    <font color="gray">MM</font>::::::::::::::::<font color="gray">MMM</font>
                    <font color="gray">MM</font>:::::::::::::::<font color="gray">MMM</font>
                    <font color="gray">MM</font>::::<font color="gray">M</font>:::::::::<font color="gray">MMM</font>:
                    <font color="gray">mMM</font>::::<font color="gray">MM</font>:::::::<font color="gray">MMMM</font>
                     <font color="gray">MMM</font>:::::::::::<font color="gray">MMM</font>:<font color="gray">M</font>
                     <font color="gray">mMM</font>:::<font color="gray">M</font>:::::::<font color="gray">M</font>:<font color="gray">M</font>:<font color="gray">M</font>
                      <font color="gray">MM</font>::<font color="gray">MMMM</font>:::::::<font color="gray">M</font>:<font color="gray">M</font>
                      <font color="gray">MM</font>::<font color="gray">MMM</font>::::::::<font color="gray">M</font>:<font color="gray">M</font>
                      <font color="gray">mMM</font>::<font color="gray">MM</font>::::::::<font color="gray">M</font>:<font color="gray">M</font>
                       <font color="gray">MM</font>::<font color="gray">MM</font>:::::::::<font color="gray">M</font>:<font color="gray">M</font>
                       <font color="gray">MM</font>::<font color="gray">MM</font>::::::::::<font color="gray">M</font>:<font color="gray">m</font>
                       <font color="gray">MM</font>:::<font color="gray">M</font>:::::::::::<font color="gray">MM</font>
                       <font color="gray">MMM</font>:::::::::::::::<font color="gray">M</font>:
                       <font color="gray">MMM</font>:::::::::::::::<font color="gray">M</font>:
                       <font color="gray">MMM</font>::::::::::::::::<font color="gray">M</font>
                       <font color="gray">MMM</font>::::::::::::::::<font color="gray">M</font>
                       <font color="gray">MMM</font>::::::::::::::::<font color="gray">Mm</font>
                        <font color="gray">MM</font>::::::::::::::::<font color="gray">MM</font>
                        <font color="gray">MMM</font>:::::::::::::::<font color="gray">MM</font>
                        <font color="gray">MMM</font>:::::::::::::::<font color="gray">MM</font>
                        <font color="gray">MMM</font>:::::::::::::::<font color="gray">MM</font>
                        <font color="gray">MMM</font>:::::::::::::::<font color="gray">MM</font>
                         <font color="gray">MM</font>::::::::::::::<font color="gray">MMM</font>
                         <font color="gray">MMM</font>:::::::::::::<font color="gray">MM</font>
                         <font color="gray">MMM</font>:::::::::::::<font color="gray">MM</font>
                         <font color="gray">MMM</font>::::::::::::<font color="gray">MM</font>
                          <font color="gray">MM</font>::::::::::::<font color="gray">MM</font>
                          <font color="gray">MM</font>::::::::::::<font color="gray">MM</font>
                          <font color="gray">MM</font>:::::::::::<font color="gray">MM</font>
                          <font color="gray">MMM</font>::::::::::<font color="gray">MM</font>
                          <font color="gray">MMM</font>::::::::::<font color="gray">MM</font>
                           <font color="gray">MM</font>:::::::::<font color="gray">MM</font>
                           <font color="gray">MMM</font>::::::::<font color="gray">MM</font>
                           <font color="gray">MMM</font>::::::::<font color="gray">MM</font>
                            <font color="gray">MM</font>::::::::<font color="gray">MM</font>
                            <font color="gray">MMM</font>::::::<font color="gray">MM</font>
                            <font color="gray">MMM</font>::::::<font color="gray">MM</font>
                             <font color="gray">MM</font>::::::<font color="gray">MM</font>
                             <font color="gray">MM</font>::::::<font color="gray">MM</font>
                              <font color="gray">MM</font>:::::<font color="gray">MM</font>
                              <font color="gray">MM</font>:::::<font color="gray">MM</font>:
                              <font color="gray">MM</font>:::::<font color="gray">M</font>:<font color="gray">M</font>
                              <font color="gray">MM</font>:::::<font color="gray">M</font>:<font color="gray">M</font>
                              :<font color="gray">M</font>::::::<font color="gray">M</font>:
                             <font color="gray">M</font>:<font color="gray">M</font>:::::::<font color="gray">M</font>
                            <font color="gray">M</font>:::<font color="gray">M</font>::::::<font color="gray">M</font>
                           <font color="gray">M</font>::::<font color="gray">M</font>::::::<font color="gray">M</font>
                          <font color="gray">M</font>:::::<font color="gray">M</font>:::::::<font color="gray">M</font>
                         <font color="gray">M</font>::::::<font color="gray">MM</font>:::::::<font color="gray">M</font>
                         <font color="gray">M</font>:::::::<font color="gray">M</font>::::::::<font color="gray">M</font>
                         <font color="gray">M;</font>:<font color="gray">;</font>::::<font color="gray">M</font>:::::::::<font color="gray">M</font>
                         <font color="gray">M</font>:<font color="gray">m</font>:<font color="gray">;</font>:::<font color="gray">M</font>::::::::::<font color="gray">M</font>
                         <font color="gray">MM</font>:<font color="gray">m</font>:<font color="gray">m</font>::<font color="gray">M</font>::::::::<font color="gray">;</font>:<font color="gray">M</font>
                          <font color="gray">MM</font>:<font color="gray">m</font>::<font color="gray">MM</font>:::::::<font color="gray">;</font>:<font color="gray">;M</font>
                           <font color="gray">MM</font>::<font color="gray">MMM</font>::::::<font color="gray">;</font>:<font color="gray">m</font>:<font color="gray">M</font>
                            <font color="gray">MMMM MM</font>::::<font color="gray">m</font>:<font color="gray">m</font>:<font color="gray">MM</font>
                                  <font color="gray">MM</font>::::<font color="gray">m</font>:<font color="gray">MM</font>
                                   <font color="gray">MM</font>::::<font color="gray">MM</font>
                                    <font color="gray">MM</font>::<font color="gray">MM</font>
                                     <font color="gray">MMMM</font>
</pre></body></html>'''
    
def ParseFileArguments( path, decompression_bombs_ok = False ):
    
    HydrusImageHandling.ConvertToPNGIfBMP( path )
    
    hash = HydrusFileHandling.GetHashFromPath( path )
    
    try:
        
        mime = HydrusFileHandling.GetMime( path )
        
        if mime in HC.DECOMPRESSION_BOMB_IMAGES and not decompression_bombs_ok:
            
            if HydrusImageHandling.IsDecompressionBomb( path ):
                
                raise HydrusExceptions.InsufficientCredentialsException( 'File seemed to be a Decompression Bomb, which you cannot upload!' )
                
            
        
        ( size, mime, width, height, duration, num_frames, has_audio, num_words ) = HydrusFileHandling.GetFileInfo( path, mime )
        
    except Exception as e:
        
        raise HydrusExceptions.BadRequestException( 'File ' + hash.hex() + ' could not parse: ' + str( e ) )
        
    
    args = HydrusNetworking.ParsedRequestArguments()
    
    args[ 'path' ] = path
    args[ 'hash' ] = hash
    args[ 'size' ] = size
    args[ 'mime' ] = mime
    
    if width is not None: args[ 'width' ] = width
    if height is not None: args[ 'height' ] = height
    if duration is not None: args[ 'duration' ] = duration
    if num_frames is not None: args[ 'num_frames' ] = num_frames
    args[ 'has_audio' ] = has_audio
    if num_words is not None: args[ 'num_words' ] = num_words
    
    if mime in HC.MIMES_WITH_THUMBNAILS:
        
        try:
            
            bounding_dimensions = HC.SERVER_THUMBNAIL_DIMENSIONS
            
            target_resolution = HydrusImageHandling.GetThumbnailResolution( ( width, height ), bounding_dimensions )
            
            thumbnail_bytes = HydrusFileHandling.GenerateThumbnailBytes( path, target_resolution, mime, duration, num_frames )
            
        except Exception as e:
            
            tb = traceback.format_exc()
            
            raise HydrusExceptions.BadRequestException( 'Could not generate thumbnail from that file:' + os.linesep + tb )
            
        
        args[ 'thumbnail' ] = thumbnail_bytes
        
    
    return args
    
hydrus_favicon = FileResource( os.path.join( HC.STATIC_DIR, 'hydrus.ico' ), defaultType = 'image/x-icon' )

class HydrusDomain( object ):
    
    def __init__( self, local_only ):
        
        self._local_only = local_only
        
    
    def CheckValid( self, client_ip ):
        
        # >::ffff:127.0.0.1
        #▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓█▓▓▓▓█████▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
        #▒▓▓▓▒▒▒▓▓▓▓▓▓▓▒▒▓▓▓▓▒▒░░░░  ░░▒▒▒▒▒▓▓▓▓▓▓▓▒▒▓▓▓▓▓▓▓▒▒▒▓▓▓
        #▓▓▓▓▓▓▓▒▓▓▓▓▓▓▓▓▒▒░░ ░░░░░       ░▒▒▓▓▓▓▓▓▓▓▒▓▓▓▓▓▒▓▓▓▒▓▓
        #▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒░▒▒▒▒▓▓▓▒▒▒▒▒▒▒▒▒▓▓▓▓▓▒▓▓▓▓▓▓▒▓▓▓▓▓▓▓▓▒▒
        #▒▒▓▓▓▓▓▓▓▒▒▓▓▒▒▒░░░░░▒▒▒▒▒▒▓▓▓▓█▓▓▓█▓▓▓▓▓▓▓▓▓▓▓▒▓▓▓▓▓▓▓▓▒
        #▓▓▓▓▓▓▓▓▓▓▓▒▓▓░         ░░░░▓▓█▓█▓▓▓█▓▓▓▓▓▓▓▓▓▓▓▓▒▓▓▓▓▓▒▓
        #▓▓▓▓▒▓▓▓▓▓▓▓▓░     ░        ▒▓██▓█▓▓▓▓▓▓█▓▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓
        #▓▓▓▓▓▒▓▓▓▓▓█▒   ░ ░░░         ▓████▓▓▓▓▓█▓▒▒▓▓▓▓▓▓▓▒▒▓▓▓▓
        #▓▓▓▓▓▓▓▒▓██▓  ░░░░░░░░░░░░ ░   ▒▓█▓▓▓▓▓▓▓█▓▓▒▓▓▓▓▓▒▓▓▓▒▓▓
        #▒▓▓▓▓▓▓▓▓██░ ░▒▒▒░▒░░░░░░░░░░░  ░▓█▓▓▓███▓█▓▓▓▒▓▓▓▓▓▓▓▓▒▒
        #▒▒▓▓▓▓▓▓▓█▓ ░▒░▒▒▒▒▒░░░░░░░░░░░░ ▒▓█▓█▓███▓▓▓▓▓▒▓▓▓▓▓▓▓▓▒
        #▓▓▓▒▓▓▓▓▓█▓░▒▒▒▒▒▒▒░▒░░░▒░░░░░░░░░▒▓▓▓▓▓█▒ ░▒▓▓▓▓▒▓▓▓▓▓▒▓
        #▓▓▓▓▒▓▓▓▓█▓░▒▓▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░░░░░▒▓▓█▓░░▒▒▓▓▓▓▓▒▓▓▓▓▓▓
        #▓▓▓▓▓▒▓▓▓█▓░▒▒▒▒▒▒▒▒▒▒▒░░░░░░░░░░░░  ▒██▒▒▒░░▓▓▓▓▓▓▒▒▓▓▓▓
        #▓▓▓▓▓▓▓▒▒█▓░░▒▒▒▒▒▒▒▒▒▒▒  ░░░░░░░▒░░ ░█▓ ░▒▒░▓▓▓▓▓▒▓▓▓▒▓▓
        #▒▓▓▓▓▓▓▓▓▓▓▒▒▓▒▒▓▓▓▒▒▒▓▓▓▓▓▒▒▒▒▒▒▒▒░░▒█▓ ▒▒ ▒▓▓▓▓▓▓▓▓▓▓▒▓
        #▒▒▓▓▓▓▓▓▓▓▓▒▒▓▓█▓▓▓▓▓▒▒▓▓██▓▓▓▒▒▒▒░░░░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▒
        #▓▓▓▒▓▓▓▓▓░ ▓▒▓▓▓▓▓▓▒▓▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░░░░▒▒  ▒█▓▓▓▓▓▓▓▒▓
        #▓▓▓▓▒▓▓▓▓▓▒▓▒▒▒▒▓▓▓▓▒░▒▒░░░▒▒▒░░░░░░░░░░░░░▒     ░▓▓████▓
        #▓▓▓▓▓▒▓▓▓▓▓▓▒▒▒▒▒▒▓▓░░░▒▒▒▒▒▒▒░░░░▒▒▒▒░░▒░░░          ▒▒▓
        #▓▓▓▓▓▓▓▒▒▓▓▓▓▒▒▒▒▓▓▒░░░░▒▒▒▒▒▓▒▒▒▒▒▒▒▒░░▒▒▒░   ░         
        #▒▓▓▓▓▓▓▓▓▒▓▓▓▓▓▓▓▓▓▓▓▒▒▒▒▒░░▒▓▓▓▒░▒▒▒▒▒▒▒▒▒   ▒░         
        #▒▒▓▓▓▓▓▓▓▓▒▓▓▓▓▓▓▓▓▓▓▓▒▒▒▒▒▒▒▓▓▓▒▒▒▒▒▒▒▒▒▒   ░▒░   ░░░░  
        #▓▓▓▒▓▓▓▓▓▓▓▓▒▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒▒▒▒▒▒▒▒▒▒▒▓▓▒   ░▓░  ░░░░    
        #▓▓▓▓▓▒▓▓▓▓▓▓▓▓▓▓█▓▓▓▓▓▓▓▒▒▒▒░▒▒▒▒▒▒▒▒▓▓▒ ░ ░▓▒   ░░░░    
        #▓▓▓▓▓▒▒▓▓▓▓▓██▓▒░ ▒▓▓▓▓▒▓▒▒▒▒░░▒▒▒▒▓▓▒░░░ ▒▒▓░       ░▒  
        #▒▓▓▓▓▓▓▓▒▓▓█▓░     ▒▓▓▒▒▒▒░░▒▒▒▒▒▓▓▓▒░░░ ▒▒▒▒░░░░░░░▒▒░  
        #▒▒▓▓▓▓▓▓█▓▒░   ░ ░ ░▒▓▓▓▒▒▒▒▒▒▓▓█▓▒░░░░ ▒▒▒▒ ░░░▒▒░▒▒░░  
        #▒▒▒▓▓▓▓█▓░    ░ ░░ ▒░▒▒▒▒▓██████▓░░░░  ▒▒▒▒░ ░ ▒▒░▒▒░░   
        
        if self._local_only and client_ip not in ( '127.0.0.1', '::1', '::ffff:127.0.0.1' ):
            
            raise HydrusExceptions.InsufficientCredentialsException( 'Only local access allowed!' )
            
        
    
    def IsLocal( self ):
        
        return self._local_only
        
    
class HydrusResource( Resource ):
    
    def __init__( self, service, domain ):
        
        Resource.__init__( self )
        
        self._service = service
        self._service_key = self._service.GetServiceKey()
        self._domain = domain
        
        service_type = self._service.GetServiceType()
        
        self._server_version_string = HC.service_string_lookup[ service_type ] + '/' + str( HC.NETWORK_VERSION )
        
    
    def _callbackCheckAccountRestrictions( self, request ):
        
        return request
        
    
    def _callbackCheckServiceRestrictions( self, request ):
        
        self._domain.CheckValid( request.getClientIP() )
        
        self._checkService( request )
        
        self._checkUserAgent( request )
        
        return request
        
    
    def _callbackDoGETJob( self, request ):
        
        def wrap_thread_result( response_context ):
            
            request.hydrus_response_context = response_context
            
            return request
            
        
        if HG.server_profile_mode:
            
            d = deferToThread( self._profileJob, self._threadDoGETJob, request )
            
        else:
            
            d = deferToThread( self._threadDoGETJob, request )
            
        
        d.addCallback( wrap_thread_result )
        
        return d
        
    
    def _callbackDoOPTIONSJob( self, request ):
        
        def wrap_thread_result( response_context ):
            
            request.hydrus_response_context = response_context
            
            return request
            
        
        if HG.server_profile_mode:
            
            d = deferToThread( self._profileJob, self._threadDoOPTIONSJob, request )
            
        else:
            
            d = deferToThread( self._threadDoOPTIONSJob, request )
            
        
        d.addCallback( wrap_thread_result )
        
        return d
        
    
    def _callbackDoPOSTJob( self, request ):
        
        def wrap_thread_result( response_context ):
            
            request.hydrus_response_context = response_context
            
            return request
            
        
        if HG.server_profile_mode:
            
            d = deferToThread( self._profileJob, self._threadDoPOSTJob, request )
            
        else:
            
            d = deferToThread( self._threadDoPOSTJob, request )
            
        
        d.addCallback( wrap_thread_result )
        
        return d
        
    
    def _callbackEstablishAccountFromHeader( self, request ):
        
        return request
        
    
    def _callbackEstablishAccountFromArgs( self, request ):
        
        return request
        
    
    def _callbackParseGETArgs( self, request ):
        
        return request
        
    
    def _callbackParsePOSTArgs( self, request ):
        
        return request
        
    
    def _callbackRenderResponseContext( self, request ):
        
        self._CleanUpTempFile( request )
        
        if request.channel is None:
            
            # Connection was lost, it seems.
            # no need for request.finish
            
            return
            
        
        if request.requestHeaders.hasHeader( 'Origin' ):
            
            if self._service.SupportsCORS():
                
                request.setHeader( 'Access-Control-Allow-Origin', '*' )
                
            
        
        response_context = request.hydrus_response_context
        
        if response_context.HasPath():
            
            path = response_context.GetPath()
            
            filesize = os.path.getsize( path )
            
            offset_and_block_size_pairs = self._parseRangeHeader( request, filesize )
            
        else:
            
            offset_and_block_size_pairs = []
            
        
        status_code = response_context.GetStatusCode()
        
        if status_code == 200 and response_context.HasPath() and len( offset_and_block_size_pairs ) > 0:
            
            status_code = 206
            
        
        request.setResponseCode( status_code )
        
        for ( k, v, kwargs ) in response_context.GetCookies():
            
            request.addCookie( k, v, **kwargs )
            
        
        do_finish = True
        
        if response_context.HasPath():
            
            path = response_context.GetPath()
            
            filesize = os.path.getsize( path )
            
            mime = response_context.GetMime()
            
            content_type = HC.mime_mimetype_string_lookup[ mime ]
            
            ( base, filename ) = os.path.split( path )
            
            fileObject = open( path, 'rb' )
            
            content_disposition = 'inline; filename="' + filename + '"'
            
            request.setHeader( 'Content-Disposition', str( content_disposition ) )
            
            request.setHeader( 'Expires', time.strftime( '%a, %d %b %Y %H:%M:%S GMT', time.gmtime( time.time() + 86400 * 365 ) ) )
            request.setHeader( 'Cache-Control', 'max-age={}'.format( 86400 * 365 ) )
            
            if len( offset_and_block_size_pairs ) <= 1:
                
                request.setHeader( 'Content-Type', str( content_type ) )
                
                if len( offset_and_block_size_pairs ) == 0:
                    
                    content_length = filesize
                    
                    request.setHeader( 'Content-Length', str( content_length ) )
                    
                    producer = NoRangeStaticProducer( request, fileObject )
                    
                elif len( offset_and_block_size_pairs ) == 1:
                    
                    [ ( range_start, range_end, offset, block_size ) ] = offset_and_block_size_pairs
                    
                    header_range_end = filesize - 1 if range_end is None else range_end
                    
                    content_length = block_size
                    
                    request.setHeader( 'Accept-Ranges', 'bytes' )
                    request.setHeader( 'Content-Range', 'bytes {}-{}/{}'.format( offset, header_range_end, filesize ) )
                    request.setHeader( 'Content-Length', str( content_length ) )
                    
                    producer = SingleRangeStaticProducer( request, fileObject, offset, block_size )
                    
                
            else:
                
                # hey, what a surprise, an http data transmission standard turned out to be a massive PITA
                # MultipleRangeStaticProducer is the lad to use, but you have to figure out your own separation bits, which have even more finicky rules. more than I can deal with with the current time I have
                # if/when you want to do this, check out the FileResource, it does it in its internal gubbins
                
                raise HydrusExceptions.RangeNotSatisfiableException( 'Can only support Single Range requests at the moment!' )
                
            
            producer.start()
            
            do_finish = False
            
        elif response_context.HasBody():
            
            mime = response_context.GetMime()
            
            body_bytes = response_context.GetBodyBytes()
            
            content_type = HC.mime_mimetype_string_lookup[ mime ]
            
            content_length = len( body_bytes )
            
            content_disposition = 'inline'
            
            request.setHeader( 'Content-Type', content_type )
            request.setHeader( 'Content-Length', str( content_length ) )
            request.setHeader( 'Content-Disposition', content_disposition )
            
            request.write( body_bytes )
            
        else:
            
            content_length = 0
            
            if status_code != 204: # 204 is No Content
                
                request.setHeader( 'Content-Length', str( content_length ) )
                
            
        
        self._reportDataUsed( request, content_length )
        self._reportRequestUsed( request )
        
        if do_finish:
            
            request.finish()
            
        
    
    def _checkService( self, request ):
        
        return request
        
    
    def _checkUserAgent( self, request ):
        
        request.is_hydrus_user_agent = False
        
        if request.requestHeaders.hasHeader( 'User-Agent' ):
            
            user_agent_texts = request.requestHeaders.getRawHeaders( 'User-Agent' )
            
            user_agent_text = user_agent_texts[0]
            
            try:
                
                user_agents = user_agent_text.split( ' ' )
                
            except:
                
                return # crazy user agent string, so just assume not a hydrus client
                
            
            for user_agent in user_agents:
                
                if '/' in user_agent:
                    
                    ( client, network_version ) = user_agent.split( '/', 1 )
                    
                    if client == 'hydrus':
                        
                        request.is_hydrus_user_agent = True
                        
                        network_version = int( network_version )
                        
                        if network_version == HC.NETWORK_VERSION:
                            
                            return
                            
                        else:
                            
                            if network_version < HC.NETWORK_VERSION: message = 'Your client is out of date; please download the latest release.'
                            else: message = 'This server is out of date; please ask its admin to update to the latest release.'
                            
                            raise HydrusExceptions.NetworkVersionException( 'Network version mismatch! This server\'s network version is ' + str( HC.NETWORK_VERSION ) + ', whereas your client\'s is ' + str( network_version ) + '! ' + message )
                            
                        
                    
                
            
        
    
    def _profileJob( self, call, request ):
        
        HydrusData.Profile( 'client api {}'.format( request.path ), 'request.result_lmao = call( request )', globals(), locals(), min_duration_ms = 3, show_summary = True )
        
        return request.result_lmao
        
    
    def _DecompressionBombsOK( self, request ):
        
        return False
        
    
    def _errbackDisconnected( self, failure, request_deferred ):
        
        request_deferred.cancel()
        
    
    def _errbackHandleProcessingError( self, failure, request ):
        
        try:
            
            try: self._CleanUpTempFile( request )
            except: pass
            
            default_mime = HC.TEXT_HTML
            default_encoding = str
            
            if failure.type == HydrusExceptions.BadRequestException:
                
                response_context = ResponseContext( 400, mime = default_mime, body = default_encoding( failure.value ) )
                
            elif failure.type in ( HydrusExceptions.MissingCredentialsException, HydrusExceptions.DoesNotSupportCORSException ):
                
                response_context = ResponseContext( 401, mime = default_mime, body = default_encoding( failure.value ) )
                
            elif failure.type == HydrusExceptions.InsufficientCredentialsException:
                
                response_context = ResponseContext( 403, mime = default_mime, body = default_encoding( failure.value ) )
                
            elif failure.type in ( HydrusExceptions.NotFoundException, HydrusExceptions.DataMissing, HydrusExceptions.FileMissingException ):
                
                response_context = ResponseContext( 404, mime = default_mime, body = default_encoding( failure.value ) )
                
            elif failure.type == HydrusExceptions.ConflictException:
                
                response_context = ResponseContext( 409, mime = default_mime, body = default_encoding( failure.value ) )
                
            elif failure.type == HydrusExceptions.RangeNotSatisfiableException:
                
                response_context = ResponseContext( 416, mime = default_mime, body = default_encoding( failure.value ) )
                
            elif failure.type == HydrusExceptions.SessionException:
                
                response_context = ResponseContext( 419, mime = default_mime, body = default_encoding( failure.value ) )
                
            elif failure.type == HydrusExceptions.NetworkVersionException:
                
                response_context = ResponseContext( 426, mime = default_mime, body = default_encoding( failure.value ) )
                
            elif failure.type == HydrusExceptions.ServerBusyException:
                
                response_context = ResponseContext( 503, mime = default_mime, body = default_encoding( failure.value ) )
                
            elif failure.type == HydrusExceptions.BandwidthException:
                
                response_context = ResponseContext( 509, mime = default_mime, body = default_encoding( failure.value ) )
                
            elif failure.type == HydrusExceptions.ServerException:
                
                response_context = ResponseContext( 500, mime = default_mime, body = default_encoding( failure.value ) )
                
            else:
                
                HydrusData.DebugPrint( failure.getTraceback() )
                
                response_context = ResponseContext( 500, mime = default_mime, body = default_encoding( 'The repository encountered an error it could not handle! Here is a dump of what happened, which will also be written to your client.log file. If it persists, please forward it to hydrus.admin@gmail.com:' + os.linesep * 2 + failure.getTraceback() ) )
                
            
            request.hydrus_response_context = response_context
            
            self._callbackRenderResponseContext( request )
            
        except:
            
            try: HydrusData.DebugPrint( failure.getTraceback() )
            except: pass
            
            if hasattr( request, 'channel' ) and request.channel is not None:
                
                try: request.setResponseCode( 500 )
                except: pass
                
                try: request.write( failure.getTraceback() )
                except: pass
                
            
            if not request.finished:
                
                try: request.finish()
                except: pass
                
            
        
        return request
        
    
    def _parseHydrusNetworkAccessKey( self, request, key_required = True ):
        
        if not request.requestHeaders.hasHeader( 'Hydrus-Key' ):
            
            if key_required:
                
                raise HydrusExceptions.MissingCredentialsException( 'No hydrus key header found!' )
                
            else:
                
                return None
                
            
        
        hex_keys = request.requestHeaders.getRawHeaders( 'Hydrus-Key' )
        
        hex_key = hex_keys[0]
        
        try:
            
            access_key = bytes.fromhex( hex_key )
            
        except:
            
            raise HydrusExceptions.BadRequestException( 'Could not parse the hydrus key!' )
            
        
        return access_key
        
    
    def _parseRangeHeader( self, request, filesize ):
        
        offset_and_block_size_pairs = []
        
        if request.requestHeaders.hasHeader( 'Range' ):
            
            range_headers = request.requestHeaders.getRawHeaders( 'Range' )
            
            range_header = range_headers[0]
            
            if '=' not in range_header:
                
                raise HydrusExceptions.BadRequestException( 'Did not understand range header!' )
                
            
            ( unit_gumpf, range_pairs_string ) = range_header.split( '=', 1 )
            
            if unit_gumpf != 'bytes':
                
                raise HydrusExceptions.RangeNotSatisfiableException( 'Do not support anything other than bytes in Range header!' )
                
            
            range_pair_strings = range_pairs_string.split( ',' )
            
            if True in ( '-' not in range_pair_string for range_pair_string in range_pair_strings ):
                
                raise HydrusExceptions.RangeNotSatisfiableException( 'Did not understand the Range header\'s range pair(s)!' )
                
            
            range_pairs = [ range_pair_string.strip().split( '-' ) for range_pair_string in range_pair_strings ]
            
            offset_and_block_size_pairs = []
            
            for ( range_start, range_end ) in range_pairs:
                
                if range_start == '':
                    
                    if range_end == '':
                        
                        raise HydrusExceptions.RangeNotSatisfiableException( 'Undefined Range header pair given!' )
                        
                    
                    range_start = None
                    
                else:
                    
                    range_start = abs( int( range_start ) )
                    
                
                if range_end == '':
                    
                    range_end = None
                    
                else:
                    
                    range_end = abs( int( range_end ) )
                    
                
                if range_start is not None and range_end is not None and range_start > range_end:
                    
                    raise HydrusExceptions.RangeNotSatisfiableException( 'The Range header had an invalid pair!' )
                    
                
                if range_start is None:
                    
                    offset = filesize - range_end
                    block_size = range_end
                    
                elif range_end is None:
                    
                    offset = range_start
                    block_size = filesize - range_start
                    
                else:
                    
                    if range_start > filesize:
                        
                        offset_and_block_size_pairs = []
                        
                        break
                        
                    
                    if range_end > filesize:
                        
                        range_end = filesize - 1
                        
                    
                    offset = range_start
                    block_size = ( range_end + 1 ) - range_start
                    
                
                offset_and_block_size_pairs.append( ( range_start, range_end, offset, block_size ) )
                
            
        
        return offset_and_block_size_pairs
        
    
    def _reportDataUsed( self, request, num_bytes ):
        
        self._service.ReportDataUsed( num_bytes )
        
        HG.controller.ReportDataUsed( num_bytes )
        
    
    def _reportRequestUsed( self, request ):
        
        self._service.ReportRequestUsed()
        
        HG.controller.ReportRequestUsed()
        
    
    def _threadDoGETJob( self, request ):
        
        raise HydrusExceptions.NotFoundException( 'This service does not support that request!' )
        
    
    def _threadDoOPTIONSJob( self, request ):
        
        allowed_methods = []
        
        if self._threadDoGETJob.__func__ is not HydrusResource._threadDoGETJob:
            
            allowed_methods.append( 'GET' )
            
        
        if self._threadDoPOSTJob.__func__ is not HydrusResource._threadDoPOSTJob:
            
            allowed_methods.append( 'POST' )
            
        
        allowed_methods_string = ', '.join( allowed_methods )
        
        if request.requestHeaders.hasHeader( 'Origin' ):
            
            # this is a CORS request
            
            if self._service.SupportsCORS():
                
                request.setHeader( 'Access-Control-Allow-Headers', '*' )
                request.setHeader( 'Access-Control-Allow-Origin', '*' )
                request.setHeader( 'Access-Control-Allow-Methods', allowed_methods_string )
                
            else:
                
                # 401
                raise HydrusExceptions.DoesNotSupportCORSException( 'This service does not support CORS.' )
                
            
        else:
            
            # regular OPTIONS request
            
            request.setHeader( 'Allow', allowed_methods_string )
            
        
        # 204 No Content
        response_context = ResponseContext( 200, mime = HC.TEXT_PLAIN )
        
        return response_context
        
    
    def _threadDoPOSTJob( self, request ):
        
        raise HydrusExceptions.NotFoundException( 'This service does not support that request!' )
        
    
    def _CleanUpTempFile( self, request ):
        
        if hasattr( request, 'temp_file_info' ):
            
            ( os_file_handle, temp_path ) = request.temp_file_info
            
            HydrusPaths.CleanUpTempPath( os_file_handle, temp_path )
            
            del request.temp_file_info
            
        
    
    def render_GET( self, request ):
        
        request.setHeader( 'Server', self._server_version_string )
        
        d = defer.Deferred()
        
        d.addCallback( self._callbackCheckServiceRestrictions )
        
        d.addCallback( self._callbackEstablishAccountFromHeader )
        
        d.addCallback( self._callbackParseGETArgs )
        
        d.addCallback( self._callbackEstablishAccountFromArgs )
        
        d.addCallback( self._callbackCheckAccountRestrictions )
        
        d.addCallback( self._callbackDoGETJob )
        
        d.addCallback( self._callbackRenderResponseContext )
        
        d.addErrback( self._errbackHandleProcessingError, request )
        
        request.notifyFinish().addErrback( self._errbackDisconnected, d )
        
        reactor.callLater( 0, d.callback, request )
        
        return NOT_DONE_YET
        
    
    def render_OPTIONS( self, request ):
        
        request.setHeader( 'Server', self._server_version_string )
        
        d = defer.Deferred()
        
        d.addCallback( self._callbackCheckServiceRestrictions )
        
        d.addCallback( self._callbackDoOPTIONSJob )
        
        d.addCallback( self._callbackRenderResponseContext )
        
        d.addErrback( self._errbackHandleProcessingError, request )
        
        request.notifyFinish().addErrback( self._errbackDisconnected, d )
        
        reactor.callLater( 0, d.callback, request )
        
        return NOT_DONE_YET
        
    
    def render_POST( self, request ):
        
        request.setHeader( 'Server', self._server_version_string )
        
        d = defer.Deferred()
        
        d.addCallback( self._callbackCheckServiceRestrictions )
        
        d.addCallback( self._callbackEstablishAccountFromHeader )
        
        d.addCallback( self._callbackParsePOSTArgs )
        
        d.addCallback( self._callbackEstablishAccountFromArgs )
        
        d.addCallback( self._callbackCheckAccountRestrictions )
        
        d.addCallback( self._callbackDoPOSTJob )
        
        d.addCallback( self._callbackRenderResponseContext )
        
        d.addErrback( self._errbackHandleProcessingError, request )
        
        request.notifyFinish().addErrback( self._errbackDisconnected, d )
        
        reactor.callLater( 0, d.callback, request )
        
        return NOT_DONE_YET
        
    
class HydrusResourceRobotsTXT( HydrusResource ):
    
    def _threadDoGETJob( self, request ):
        
        body = '''User-agent: *
Disallow: /'''
        
        response_context = ResponseContext( 200, mime = HC.TEXT_PLAIN, body = body )
        
        return response_context
        
    
class HydrusResourceWelcome( HydrusResource ):
    
    def _threadDoGETJob( self, request ):
        
        body = GenerateEris( self._service )
        
        response_context = ResponseContext( 200, mime = HC.TEXT_HTML, body = body )
        
        return response_context
        
    
class ResponseContext( object ):
    
    def __init__( self, status_code, mime = HC.APPLICATION_JSON, body = None, path = None, cookies = None ):
        
        if body is None:
            
            body_bytes = None
            
        elif isinstance( body, HydrusSerialisable.SerialisableBase ):
            
            body_bytes = body.DumpToNetworkBytes()
            
        elif isinstance( body, str ):
            
            body_bytes = bytes( body, 'utf-8' )
            
        elif isinstance( body, bytes ):
            
            body_bytes = body
            
        else:
            
            raise Exception( 'Was given an incompatible object to respond with: ' + repr( body ) )
            
        
        
        if cookies is None:
            
            cookies = []
            
        
        self._status_code = status_code
        self._mime = mime
        self._body_bytes = body_bytes
        self._path = path
        self._cookies = cookies
        
    
    def GetBodyBytes( self ):
        
        return self._body_bytes
        
    
    def GetCookies( self ): return self._cookies
    
    def GetMime( self ): return self._mime
    
    def GetPath( self ): return self._path
    
    def GetStatusCode( self ): return self._status_code
    
    def HasBody( self ): return self._body_bytes is not None
    
    def HasPath( self ): return self._path is not None
    
