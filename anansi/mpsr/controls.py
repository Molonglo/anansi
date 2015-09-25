from threading import Thread
from lxml import etree
from copy import copy
from anansi.xml import XMLMessage,XMLError,gen_element
from anansi.comms import TCPClient
from anansi.config import config
from anansi import log

class MPSRError(Exception):
    def __init__(self,response):
        msg = "MPSR returned failure state with message: %s"%response
        super(MPSRError,self).__init__(msg)

class MPSRMessage(XMLMessage):
    def __init__(self):
        super(MPSRMessage,self).__init__(gen_element('mpsr_tmc_message'))
        self.defaults = copy(config.mpsr_defaults.__dict__)

    def __str__(self):
        return super(MPSRMessage,self).__str__().replace("\n","")+"\r\n"

    def query(self):
        self.root.append(gen_element("command",text="query"))
        return str(self)

    def stop(self):
        self.root.append(gen_element("command",text="stop"))
        return str(self)

    def start(self):
        self.root.append(gen_element("command",text="start"))
        return str(self)

    def prepare(self, **kwargs):
        self.defaults.update(kwargs)
        self.root.append(gen_element("command",text="prepare"))
        self.root.append(self._source_parameters())
        self.root.append(self._signal_parameters())
        self.root.append(self._pfb_parameters())
        self.root.append(self._observation_parameters())
        return str(self)
        
    def _source_parameters(self):
        elem = gen_element('source_parameters')
        _ = self.defaults
        elem.append(gen_element('name',text=_['source_name'],attributes={'epoch':_['epoch']}))
        elem.append(gen_element('ra',text=_['ra'],attributes={'units':_['ra_units']}))
        elem.append(gen_element('dec',text=_['dec'],attributes={'units':_['dec_units']}))
        elem.append(gen_element('ns_tilt',text=_['ns_tilt'],attributes={'units':_['ns_tilt_units']}))
        elem.append(gen_element('md_angle',text=_['md_angle'],attributes={'units':_['md_angle_units']}))
        return elem

    def _signal_parameters(self):
        _ = self.defaults
        elem = gen_element('signal_parameters')
        elem.append(gen_element('nchan',text=_['nchan']))
        elem.append(gen_element('nbit',text=_['nbit']))
        elem.append(gen_element('ndim',text=_['ndim']))
        elem.append(gen_element('npol',text=_['npol']))
        elem.append(gen_element('nant',text=_['nant']))
        elem.append(gen_element('bandwidth',text=_['bw'],attributes={'units':_['bw_units']}))
        elem.append(gen_element('centre_frequency',text=_['cfreq'],attributes={'units':_['cfreq_units']}))
        return elem
    
    def _pfb_parameters(self):
        _ = self.defaults
        elem = gen_element('pfb_parameters')
        elem.append(gen_element('oversampling_ratio',text=_['oversampling_ratio']))
        elem.append(gen_element('sampling_time',text=_['tsamp'],attributes={'units':_['tsamp_units']}))
        elem.append(gen_element('channel_bandwidth',text=_['foff'],attributes={'units':_['foff_units']}))
        elem.append(gen_element('dual_sideband',text=_['dual_sideband']))
        elem.append(gen_element('resolution',text=_['resolution']))
        return elem
    
    def _observation_parameters(self):
        _ = self.defaults
        elem = gen_element('observation_parameters')
        elem.append(gen_element('observer',text=_['observer']))
        elem.append(gen_element('aq_processing_file',text=_['aq_proc_file']))
        elem.append(gen_element('bf_processing_file',text=_['bf_proc_file']))
        elem.append(gen_element('bp_processing_file',text=_['bp_proc_file']))
        elem.append(gen_element('mode',text=_['mode']))
        elem.append(gen_element('project_id',text=_['project_id']))
        elem.append(gen_element('tobs',text=_['tobs']))
        elem.append(gen_element('type',text=_['type']))
        elem.append(gen_element('config',text=_['config']))
        return elem


class MPSRDefaultResponse(XMLMessage):
    def __init__(self,msg):
        try:
            super(MPSRDefaultResponse,self).__init__(etree.fromstring(msg))
        except:
            raise XMLError(msg)
        self._parse()
        
    def _parse(self):
        self.passed = self.root.find('reply').text == "ok"
        self.response = self.root.find('response').text


class MPSRQueryResponse(MPSRDefaultResponse):
    def __init__(self,msg):
        super(MPSRQueryResponse,self).__init__(msg)
    
    def _parse(self):
        super(MPSRQueryResponse,self)._parse()
        node = self.root.find('response')
        self.mpsr_status = node.find("mpsr_status").text


class MPSRControls(object):
    def __init__(self):
        self._ip = config.mpsr_server.ip
        self._port = config.mpsr_server.port
        self._timeout = config.mpsr_server.timeout

    def _send(self,msg,response_class):
        try:
            client = TCPClient(self._ip,self._port,timeout=self._timeout)
        except Exception as error:
            raise error
        client.send(msg)
        response = response_class(client.receive())
        client.close()
        if not response.passed:
            raise MPSRError(response.response)
        return response
    
    def prepare(self,**kwargs):
        msg = MPSRMessage().prepare(**kwargs)
        return self._send(msg,MPSRDefaultResponse)
        
    def start(self):
        msg = MPSRMessage().start()
        return self._send(msg,MPSRDefaultResponse)
    
    def stop(self):
        msg = MPSRMessage().stop()
        return self._send(msg,MPSRDefaultResponse)
    
    def query(self):
        msg = MPSRMessage().query()
        return self._send(msg,MPSRQueryResponse)
