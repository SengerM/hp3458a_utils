import numpy as np
import struct # This is used in parsing bynary data.

reading_memory_bytes = 20480 # This number is returned by command 'MSIZE?'.
read_termination = '\r'

def configure_sub_sampling(HP3458A, samples_per_burst, effective_sampling_frequency, max_input=1000):
	""" 
	Configures the HP3458A in sub sampling mode.
	
	Parameters
	----------
	HP3458A : instance of a visa instrument
		For example: 
		>>> import visa
		>>> rm = visa.ResourceManager()
		>>> HP3458A = rm.open_resource('GPIB0::22::INSTR')
		>>> configure_sub_sampling(HP3458A, ...)
	samples_per_burst : natural number
		The number of samples to record in each burst.
	effective_sampling_frequency : a positive real number
	"""
	HP3458A.write('PRESET FAST') # Configures the multimeter for fast readings, fast transfer to memory, and fast GPIB (see [1], page 218).
	HP3458A.write('MEM FIFO') # ENABLE READING MEMORY, FIFO MODE.
	HP3458A.write('MFORMAT SINT') # SINT READING MEMORY FORMAT.
	HP3458A.write('OFORMAT SINT') # Set the output format when reading the samples in memory.
	HP3458A.write('SSDC 1') # Sub-sampling mode, 10 V range.
	HP3458A.write('SWEEP {},{}'.format(1/effective_sampling_frequency, samples_per_burst)) # Specifies to take "N" samples with an effective spacing of "T" micro seconds.
	HP3458A.write('SSRC EXT') # Set external trigger.
	HP3458A.write('TARM HOLD')

def configure_direct_digitalizing(HP3458A, samples_per_burst, effective_sampling_frequency, t_aper, max_input=1000):
	""" 
	Configures the HP3458A in direct digitalizing mode.
	
	Parameters
	----------
	HP3458A : instance of a visa instrument
		For example: 
		>>> import visa
		>>> rm = visa.ResourceManager()
		>>> HP3458A = rm.open_resource('GPIB0::22::INSTR')
		>>> configure_direct_digitalizing(HP3458A, ...)
	samples_per_burst : natural number
		The number of samples to record in each burst.
	effective_sampling_frequency : a positive real number
	t_aper : a positive real number
	"""
	HP3458A.write('PRESET DIG')
	HP3458A.write('DSDC ' + str(np.abs(max_input)))
	HP3458A.write('MEM LIFO') # ENABLE READING MEMORY, FIFO MODE.
	HP3458A.write('MFORMAT SINT') # SINT READING MEMORY FORMAT.
	HP3458A.write('OFORMAT SINT') # Set the output format when reading the samples in memory.
	HP3458A.write('TIMER ' + str(1/effective_sampling_frequency)) # Specifies sampling frequency.
	HP3458A.write('NRDGS ' + str(samples_per_burst) + ', TIMER') # Specifies the number of samples to be recorded and the event in which to sample (6 is for "timer").
	HP3458A.write('TRIG EXT')
	HP3458A.write('TARM AUTO')

def configure_DCV_digitalizing(HP3458A, samples_per_burst, sampling_frequency, aper_time, max_input=1000):
	""" 
	Configures the HP3458A in direct digitalizing mode.
	
	Parameters
	----------
	HP3458A : instance of a visa instrument
		For example: 
		>>> import visa
		>>> rm = visa.ResourceManager()
		>>> HP3458A = rm.open_resource('GPIB0::22::INSTR')
		>>> configure_DCV_digitalizing(HP3458A, ...)
	samples_per_burst : natural number
		The number of samples to record in each burst.
	effective_sampling_frequency : a positive real number
	t_aper : a positive real number
	"""
	HP3458A.write('PRESET DIG')
	HP3458A.write('MEM LIFO')
	if aper_time > 1.4e-6: # See 'DCV remarks' in http://literature.cdn.keysight.com/litweb/pdf/03458-90014.pdf
		memory_format = 'DINT'
	else:
		memory_format = 'SINT'
	HP3458A.write('MFORMAT ' + memory_format)
	HP3458A.write('OFORMAT ' + memory_format)
	HP3458A.write('TIMER ' + str(1/sampling_frequency)) # Specifies sampling frequency.
	HP3458A.write('APER ' + str(aper_time)) # Set aper time (see http://literature.cdn.keysight.com/litweb/pdf/03458-90014.pdf table 5-2).
	HP3458A.write('NRDGS ' + str(samples_per_burst) + ', TIMER') # Specifies the number of samples to be recorded and the event in which to sample (6 is for "timer").
	HP3458A.write('TRIG EXT')
	HP3458A.write('DCV ' + str(np.abs(max_input)))
	HP3458A.write('TARM AUTO')

def read_binary_mem(HP3458A, N_SAMPLES):
	""" 
	Returns a numpy array containing the samples. Automatically
	handles DINT and SINT memory formats.
	
	Parameters
	----------
	HP3458A : instance of a visa instrument
		For example: 
		>>> import visa
		>>> rm = visa.ResourceManager()
		>>> HP3458A = rm.open_resource('GPIB0::22::INSTR')
		>>> read_binary_mem(HP3458A, ...)
	N_SAMPLES : natural number
		The number of samples to read.
	
	Returns
	-------
	A numpy array containing the samples, already converted from ADC
	units to voltage units.
	"""
	if int(HP3458A.query('MFORMAT?')) == 3:
		conversion_format = 'i'
		bytes_per_sample = 4
	elif int(HP3458A.query('MFORMAT?')) == 2:
		conversion_format = 'h'
		bytes_per_sample = 2
	else:
		raise ValueError('I don\'t know hot to read that memory format!')
	HP3458A.write('RMEM 1,' + str(N_SAMPLES))
	samples = np.asarray(struct.unpack('>'+conversion_format*N_SAMPLES, HP3458A.read_bytes(bytes_per_sample*N_SAMPLES))) 
	samples = samples*float(HP3458A.query('ISCALE?'))
	samples = np.array(samples)
	return np.flipud(samples) # Samples come reversed in time.

def T_aper_check(T_aper):
	if T_aper<500e-9 or T_aper>1: # See http://literature.cdn.keysight.com/litweb/pdf/03458-90014.pdf page 203.
		return False
	else:
		return True

def get_uncertainty_DCV_sampling(HP3458A):
	""" uncertainty[0] is the % of reading and uncertainty[1] is 
	the constant error. Thus if "V0" is the measurement then 
	
		"V0*uncertainty[0] + uncertainty[1]" is its error.
	"""
	uncertainty = [0,0]
	T_aper = float(HP3458A.query('APER?'))
	if T_aper < 1e-6: # See table 5-2 from http://literature.cdn.keysight.com/litweb/pdf/03458-90014.pdf
		cutoff_3dB = 400e3
		bits = 15
	elif T_aper < 3e-6:
		bits = 16
		cutoff_3dB = 206e3
	elif T_aper < 6e-6:
		bits = 17
		cutoff_3dB = 69e3
	elif T_aper < 100e-6:
		bits = 18
		cutoff_3dB = 35e3
	else:
		bits = 21
		cutoff_3dB = 2e3
	DMM_range = float(HP3458A.query('RANGE?'))
	uncertainty = [14e-6, 3e-6+DMM_range/2**bits]
	return uncertainty

def get_uncertainty_direct_sampling(HP3458A):
	""" uncertainty[0] is the % of reading and uncertainty[1] is 
	the constant error. Thus if "V0" is the measurement then 
	
		"V0*uncertainty[0] + uncertainty[1]" is its error.
	"""
	return [0.02/100, float(HP3458A.query('RANGE?'))/2**16]

def get_uncertainty(HP3458A):
	current_mode = HP3458A.query('FUNC?')
	current_mode = int(current_mode[:(current_mode).find(',')])
	if current_mode == 1:
		return get_uncertainty_DCV_sampling(HP3458A)
	elif current_mode == 12:
		return get_uncertainty_direct_sampling(HP3458A)
	elif current_mode == 14: # SSDC (Sub Sampling DC)
		return [1, 1] # FALTA IMPLEMENTAR!!!
	else:
		raise ValueError('Cannot get uncertainty for the current mode of operation.')
