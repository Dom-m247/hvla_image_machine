from pre_calibration.options_class import Options
import pprint

class Image:
  def __init__(self,options:Options,image_data):
    '''
    convert the output of imstat into an obj for easy use
    '''
    #note: they are weird numpy data
    if image_data is None: 
      return
    self.blc = image_data['blc'] 
    self.blcf = image_data['blcf'] 
    self.flux = image_data['flux']
    self.max = image_data['max']
    self.maxposf = image_data['maxposf']
    self.mean = image_data['mean']
    self.medabsdevmed = image_data['medabsdevmed']
    self.median = image_data['median']
    self.min = image_data['min']
    self.minpos = image_data['minpos']
    self.minposf = image_data['minposf']
    self.npts = image_data['npts']
    self.q1 = image_data['q1']
    self.q3 = image_data['q3']
    self.quartile = image_data['quartile']
    self.rms = image_data['rms']
    self.sigma = image_data['sigma']
    self.sum = image_data['sum']
    self.sumsq = image_data['sumsq']
    self.trc = image_data['trc']
    self.trcf = image_data['trcf']


